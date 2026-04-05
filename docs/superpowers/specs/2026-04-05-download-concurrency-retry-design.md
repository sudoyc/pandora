# P1: 下载并发+重试+image_service 集成

> 日期：2026-04-05（v2 更新）
> 范围：`pandora_daemon/download.py`（重构）、`pandora_daemon/config.py`（修改）、`pandora_daemon/routes/downloads.py`（修改）、`pandora_daemon/app.py`（修改）
> 依赖：P0 异常体系（已完成）、P0 数据库层（已完成）

---

## 1. 问题

当前 `pandora_daemon/download.py` 存在 5 个核心问题：

1. **页面下载串行**：`_download_gallery` 中 for 循环逐页下载，无并发。1000 页画廊需要串行请求 2000 次（viewer page + image）
2. **失败页跳过不重试**：page 下载失败只 `except: pass`，整个画廊仍标记 `completed`，实际缺页
3. **状态保存过频**：每下完一页就全量序列化 `_save_state()`，1000 页画廊写 1000 次 JSON
4. **缺少页面级状态追踪**：无法知道哪些页成功、哪些失败、哪些未开始
5. **直接访问 client.session**：`_fetch_image` 绕过 `ImageService`，重复了缓存逻辑
6. **部分写入风险**：页面图片直接 `write_bytes`，中断时留下不完整文件，断点续传误判为已完成

## 2. 设计概览

### 2.1 改动范围

| 文件 | 操作 | 说明 |
|------|------|------|
| `pandora_daemon/download.py` | 重构 | 并发下载、即时重试、页面状态、原子写入、debounce 保存、image_service 集成 |
| `pandora_daemon/config.py` | 修改 | `concurrency` → `gallery_concurrency`，新增 `page_concurrency`、`max_retry`、`retry_base_delay` |
| `pandora_daemon/routes/downloads.py` | 修改 | 新增 3 个端点 |
| `pandora_daemon/app.py` | 修改 | DownloadManager 构造传入 image_service，移除 cache 参数 |

### 2.2 不改动的部分

- `exhentai_api/` — 异常体系已完成，不需要改动
- `image_service.py` — 只作为依赖被调用，自身不改
- `cache.py` — 不改（P1 缓存淘汰是独立任务）
- `ws.py` — 不改
- TUI — 不改（TUI 通过 HTTP/WS 状态码判断）

## 3. DownloadTask 模型变更

### 3.1 新增字段

```python
@dataclass
class DownloadTask:
    # ... 现有字段保持不变 ...

    # 新增：页面级状态追踪
    page_states: dict[int, str] = field(default_factory=dict)
    # key: 页码 (1-based), value: "pending" | "downloading" | "done" | "failed"
    failed_pages: list[int] = field(default_factory=list)
```

### 3.2 新增状态值

```python
# 现有状态
"queued" | "downloading" | "completed" | "failed" | "cancelled"

# 新增
"completed_with_errors"   # 即时重试耗尽后仍有失败页
"paused"                  # ImageLimitError (509) 触发暂停
```

注意：不再需要 `"retrying"` 状态。即时重试发生在单页下载函数内部，对外仍表现为 `"downloading"`。

### 3.3 状态转换图

```
queued → downloading → completed
                     → completed_with_errors (有失败页)
                     → failed (不可恢复错误)
                     → paused (ImageLimitError)
                     → cancelled

paused → queued → downloading (用户 resume)
completed_with_errors → queued → downloading (用户 retry，仅重新下载失败页)
```

## 4. DownloadManager 改动

### 4.1 构造函数变更

```python
class DownloadManager:
    def __init__(self, api, config, ws, image_service, state_file: Path) -> None:
        self._api = api
        self._config = config
        self._ws = ws
        self._image_service = image_service  # 替代原来的 cache
        self._state_file = state_file
        self._download_path = Path(config.path).expanduser()
        self._tasks: dict[str, DownloadTask] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._workers: list[asyncio.Task] = []
        self._cancelled: set[str] = set()
        # 新增：debounce 状态保存
        self._save_dirty: bool = False
        self._save_task: asyncio.Task | None = None
```

移除 `cache` 参数。`image_service` 内部已处理缓存。

### 4.2 _fetch_image 改为使用 image_service

```python
async def _fetch_image(self, url: str) -> bytes:
    """Fetch image bytes via ImageService (cache-first)."""
    return await self._image_service.proxy_image(url)
```

### 4.3 原子写入辅助函数

```python
def _atomic_write(path: Path, data: bytes) -> None:
    """先写临时文件，完成后原子重命名。防止中断导致不完整文件。"""
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_bytes(data)
    tmp_path.rename(path)
```

所有图片写入（cover、thumbs、pages）都通过此函数。断点续传检测时，`glob(f"{page_num:04d}.*")` 自然排除 `.tmp` 后缀的文件（因为 `.jpg.tmp` 不匹配 `0001.*` 的模式——实际上会匹配，需要显式排除）。

修正：断点续传检测逻辑：

```python
existing = [f for f in pages_dir.glob(f"{page_num:04d}.*") if not f.suffix.endswith(".tmp")]
```

### 4.4 并发页面下载（即时重试）

将 `_download_gallery` 中的串行页面下载循环替换为并发版本。核心变化：重试逻辑内聚在单页下载函数中，不再有后置重试循环。

```python
async def _download_pages(self, task: DownloadTask) -> None:
    """并发下载全部页面图片。每页失败时即时重试。"""
    semaphore = asyncio.Semaphore(self._config.page_concurrency)
    pages_dir = Path(task.output_dir) / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    stop_event = asyncio.Event()  # 不可恢复错误的中止信号
    stop_reason: Exception | None = None

    for i in range(1, task.total_pages + 1):
        if task.page_states.get(i) != "done":
            task.page_states[i] = "pending"

    async def _download_single_page(page_num: int) -> None:
        nonlocal stop_reason

        # 检查中止信号
        if stop_event.is_set():
            return
        # 跳过已完成页（断点续传）
        if task.page_states.get(page_num) == "done":
            return
        # 文件系统检测（排除 .tmp）
        existing = [f for f in pages_dir.glob(f"{page_num:04d}.*")
                     if not f.name.endswith(".tmp")]
        if existing:
            task.page_states[page_num] = "done"
            return

        async with semaphore:
            if stop_event.is_set() or task.gid in self._cancelled:
                return

            idx = page_num - 1
            if idx >= len(task.preview_urls):
                task.page_states[page_num] = "failed"
                task.failed_pages.append(page_num)
                return

            viewer_url = task.preview_urls[idx]

            # 即时重试循环
            last_exc = None
            for attempt in range(self._config.max_retry + 1):
                if stop_event.is_set() or task.gid in self._cancelled:
                    return

                try:
                    task.page_states[page_num] = "downloading"
                    html = await self._api.client.get_html(viewer_url)
                    image_url, _ = parse_image_viewer(html)
                    if not image_url:
                        raise ParseError(f"No image URL for page {page_num}")
                    data = await self._fetch_image(image_url)
                    ext = _ext_from_url(image_url)
                    _atomic_write(pages_dir / f"{page_num:04d}{ext}", data)
                    task.page_states[page_num] = "done"
                    task.downloaded_pages += 1
                    last_exc = None
                    break  # 成功，退出重试循环

                except (AuthenticationError, ImageLimitError, GalleryNotFoundError) as e:
                    # 不可恢复错误：设置中止信号，停止所有并发页面
                    stop_reason = e
                    stop_event.set()
                    task.page_states[page_num] = "failed"
                    return

                except (NetworkError, ParseError) as e:
                    last_exc = e
                    if attempt < self._config.max_retry:
                        delay = self._config.retry_base_delay * (2 ** attempt)
                        await asyncio.sleep(delay)
                    # 继续重试循环

                except Exception as e:
                    # 未知异常：不重试
                    last_exc = e
                    break

            # 重试耗尽仍失败
            if last_exc is not None:
                task.page_states[page_num] = "failed"
                task.failed_pages.append(page_num)

            await self._ws.broadcast({
                "event": "download_progress", "gid": task.gid,
                "phase": "pages", "page": page_num, "total": task.total_pages,
            })
            self._mark_dirty()

    coros = [_download_single_page(p) for p in range(1, task.total_pages + 1)]
    await asyncio.gather(*coros)

    if stop_reason is not None:
        raise stop_reason
```

**设计要点**：
- 使用 `asyncio.Event` 作为中止信号，比 `stop_reason is not None` 检查更可靠（Event.set() 是线程安全的，且 `is_set()` 是 O(1)）
- 即时重试在 semaphore 内部进行，重试期间占用一个并发槽位。这是有意为之——避免重试请求和新请求竞争导致更多失败
- 指数退避：`retry_base_delay * 2^attempt`（默认 2s, 4s, 8s）

### 4.5 _download_gallery 改造

```python
async def _download_gallery(self, task: DownloadTask) -> None:
    is_retry = bool(task.failed_pages) and task.downloaded_pages > 0
    task.status = "downloading"
    output_dir = Path(task.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        if not is_retry:
            # Phase 1: metadata（不变，但写入用 _atomic_write）
            # Phase 2: cover（不变，但写入用 _atomic_write）
            # Phase 3: thumbs（不变，但 _fetch_image 已走 image_service，写入用 _atomic_write）

        # Phase 4: pages — 并发下载（含即时重试）
        await self._download_pages(task)

        # 最终状态（不再有后置重试循环）
        if task.failed_pages:
            task.status = "completed_with_errors"
            task.error = f"{len(task.failed_pages)} pages failed: {task.failed_pages[:10]}"
        else:
            task.status = "completed"

        await self._ws.broadcast(
            {"event": "download_complete", "gid": task.gid, "path": task.output_dir}
        )

    except AuthenticationError as e:
        task.status = "failed"
        task.error = str(e)
        await self._ws.broadcast(
            {"event": "download_auth_failed", "gid": task.gid, "error": str(e)}
        )
        await self._pause_all_tasks()

    except ImageLimitError as e:
        task.status = "paused"
        task.error = str(e)
        await self._ws.broadcast(
            {"event": "download_paused", "gid": task.gid, "reason": "image_limit"}
        )

    except GalleryNotFoundError as e:
        task.status = "failed"
        task.error = str(e)
        await self._ws.broadcast(
            {"event": "download_error", "gid": task.gid, "error": str(e)}
        )

    except Exception as e:
        task.status = "failed"
        task.error = str(e)
        await self._ws.broadcast(
            {"event": "download_error", "gid": task.gid, "error": str(e)}
        )

    self._save_state()
```

**is_retry 模式**：当用户对 `completed_with_errors` 任务调用 retry 时，任务重新入队。`_download_gallery` 检测到 `is_retry=True`，跳过 metadata/cover/thumbs 阶段，直接进入 `_download_pages`。`_download_pages` 内部会跳过 `page_states == "done"` 的页面，只下载失败页。

### 4.6 _pause_all_tasks 方法

```python
async def _pause_all_tasks(self) -> None:
    """AuthenticationError 时暂停所有正在下载的任务。"""
    for task in self._tasks.values():
        if task.status in ("queued", "downloading"):
            task.status = "paused"
            await self._ws.broadcast(
                {"event": "download_paused", "gid": task.gid, "reason": "auth_failed"}
            )
    self._save_state()
```

### 4.7 resume 方法

```python
async def resume(self, gid: str) -> bool:
    """恢复暂停的任务。"""
    task = self._tasks.get(gid)
    if task is None or task.status != "paused":
        return False
    task.status = "queued"
    await self._queue.put(gid)
    self._save_state()
    return True
```

### 4.8 retry_failed 方法

```python
async def retry_failed(self, gid: str) -> bool:
    """重试 completed_with_errors 任务的失败页。"""
    task = self._tasks.get(gid)
    if task is None or task.status != "completed_with_errors":
        return False
    if not task.failed_pages:
        return False
    task.status = "queued"
    await self._queue.put(gid)
    self._save_state()
    return True
```

### 4.9 Debounce 状态保存

```python
def _mark_dirty(self) -> None:
    """标记状态为脏，启动延迟保存。"""
    self._save_dirty = True
    if self._save_task is None or self._save_task.done():
        self._save_task = asyncio.create_task(self._debounced_save())

async def _debounced_save(self) -> None:
    """延迟 5 秒后保存，合并多次写入。"""
    await asyncio.sleep(5)
    if self._save_dirty:
        self._save_state()
        self._save_dirty = False
```

**即时保存的场景**（直接调用 `_save_state()`）：
- `submit()` — 新任务入队
- `cancel()` — 用户取消
- `shutdown()` — daemon 关闭
- 任务最终状态变更（completed / failed / completed_with_errors / paused）

**延迟保存的场景**（调用 `_mark_dirty()`）：
- 每页下载完成后的进度更新

### 4.10 shutdown 变更

```python
async def shutdown(self) -> None:
    for worker in self._workers:
        worker.cancel()
    await asyncio.gather(*self._workers, return_exceptions=True)
    self._workers.clear()
    # 取消 debounce 任务并立即保存
    if self._save_task and not self._save_task.done():
        self._save_task.cancel()
    self._save_state()
```

### 4.11 start 变更

worker 数量改为使用 `gallery_concurrency`：

```python
async def start(self) -> None:
    self._load_state()
    for task in list(self._tasks.values()):
        if task.status in ("queued", "downloading"):
            task.status = "queued"
            await self._queue.put(task.gid)

    for _ in range(self._config.gallery_concurrency):
        worker = asyncio.create_task(self._worker())
        self._workers.append(worker)
```

### 4.12 .tmp 文件清理

在 `_download_pages` 开始前，清理上次中断留下的 `.tmp` 文件：

```python
# 清理残留的 .tmp 文件
for tmp_file in pages_dir.glob("*.tmp"):
    tmp_file.unlink(missing_ok=True)
```

同样在 cover 和 thumbs 目录中执行。

## 5. 配置变更

### 5.1 DownloadConfig 修改

```python
@dataclass
class DownloadConfig:
    path: str = "~/Downloads/pandora"
    gallery_concurrency: int = 2    # 同时下载的画廊数（worker 数）
    page_concurrency: int = 4       # 单画廊内页面并发数
    max_retry: int = 3              # 单页最大重试次数
    retry_base_delay: float = 2.0   # 重试基础延迟（秒），指数退避
```

### 5.2 向后兼容

`load_config` 中处理旧的 `concurrency` 字段：

```python
dl_data = data.get("download", {})
# 向后兼容：旧的 concurrency 映射为 gallery_concurrency
gallery_concurrency = dl_data.get("gallery_concurrency",
                                   dl_data.get("concurrency", 2))
download = DownloadConfig(
    path=dl_data.get("path", "~/Downloads/pandora"),
    gallery_concurrency=gallery_concurrency,
    page_concurrency=dl_data.get("page_concurrency", 4),
    max_retry=dl_data.get("max_retry", 3),
    retry_base_delay=dl_data.get("retry_base_delay", 2.0),
)
```

### 5.3 to_public_dict / _to_dict 修改

```python
"download": {
    "path": self.download.path,
    "gallery_concurrency": self.download.gallery_concurrency,
    "page_concurrency": self.download.page_concurrency,
    "max_retry": self.download.max_retry,
    "retry_base_delay": self.download.retry_base_delay,
},
```

## 6. REST 端点变更

### 6.1 新增端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/downloads/{gid}/retry` | 重试 completed_with_errors 的失败页 |
| POST | `/api/downloads/{gid}/resume` | 恢复 paused 的任务 |
| GET | `/api/downloads/{gid}/pages` | 获取页面级状态详情 |

```python
@router.post("/{gid}/retry")
async def retry_download(gid: str, downloads: DownloadManager = Depends(get_downloads)):
    result = await downloads.retry_failed(gid)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found or not in completed_with_errors state")
    return {"success": True}

@router.post("/{gid}/resume")
async def resume_download(gid: str, downloads: DownloadManager = Depends(get_downloads)):
    result = await downloads.resume(gid)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found or not paused")
    return {"success": True}

@router.get("/{gid}/pages")
async def get_page_status(gid: str, downloads: DownloadManager = Depends(get_downloads)):
    tasks = {t.gid: t for t in downloads.status()}
    task = tasks.get(gid)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "gid": task.gid,
        "total_pages": task.total_pages,
        "downloaded_pages": task.downloaded_pages,
        "failed_pages": task.failed_pages,
        "page_states": task.page_states,
    }
```

## 7. WebSocket 事件变更

### 7.1 新增事件

```json
{"event": "download_paused", "gid": "123", "reason": "image_limit"}
{"event": "download_paused", "gid": "123", "reason": "auth_failed"}
{"event": "download_auth_failed", "gid": "123", "error": "Sad Panda: cookies invalid"}
```

### 7.2 现有事件不变

`download_queued`、`download_progress`、`download_complete`、`download_error`、`download_cancelled` 保持不变。

## 8. app.py 集成变更

```python
# 现有
downloads = DownloadManager(api, config.download, ws, cache, state_file)

# 改为（移除 cache，新增 image_service）
downloads = DownloadManager(api, config.download, ws, image_service, state_file)
```

## 9. 异常分类重试策略总结

| 异常类型 | 单页行为 | 画廊行为 | 重试 |
|----------|----------|----------|------|
| `NetworkError` | 即时指数退避重试 | 继续其他页 | 最多 max_retry 次 |
| `ParseError` | 即时指数退避重试 | 继续其他页 | 最多 max_retry 次 |
| `ImageLimitError` | 设置 stop_event | 画廊暂停 (paused) | 不重试，等用户 resume |
| `AuthenticationError` | 设置 stop_event | 画廊失败 + 暂停所有任务 | 不重试 |
| `GalleryNotFoundError` | 设置 stop_event | 画廊失败 (failed) | 不重试 |
| 其他 Exception | 不重试，标记失败 | 继续其他页 | 不重试 |

## 10. 测试计划

### 10.1 download.py 单元测试 (`tests/pandora_daemon/test_download_concurrency.py`)

使用 mock API、mock ImageService、mock WS，测试核心逻辑：

| 测试组 | 用例数 | 覆盖 |
|--------|--------|------|
| 并发下载 | 4 | 基本并发、semaphore 限制、断点续传跳过已完成页、cancelled 中断 |
| 即时重试 | 5 | NetworkError 重试成功、ParseError 重试、重试耗尽 → failed_pages、指数退避延迟验证、未知异常不重试 |
| 不可恢复错误 | 3 | ImageLimitError → paused + stop_event、AuthenticationError → failed + pause_all、GalleryNotFoundError → failed |
| 原子写入 | 3 | _atomic_write 正常写入、.tmp 清理、断点续传排除 .tmp 文件 |
| 页面状态 | 3 | page_states 初始化、下载后更新、failed_pages 记录 |
| debounce 保存 | 3 | _mark_dirty 触发延迟保存、即时保存场景、shutdown 取消 debounce |
| resume/retry | 3 | resume paused 任务、retry_failed 任务、非法状态返回 False |
| image_service 集成 | 2 | _fetch_image 调用 image_service.proxy_image、不再直接访问 client.session |
| is_retry 模式 | 2 | retry 跳过 metadata/cover/thumbs、只下载失败页 |

共约 28 个测试。

### 10.2 路由测试 (`tests/pandora_daemon/test_routes_downloads.py`)

扩展现有测试文件，新增 3 个端点的测试：

| 测试用例 | 预期 |
|----------|------|
| POST /retry — completed_with_errors 任务 | 200, {"success": true} |
| POST /retry — 不存在的任务 | 404 |
| POST /retry — 非 completed_with_errors 状态 | 404 |
| POST /resume — paused 任务 | 200, {"success": true} |
| POST /resume — 非 paused 状态 | 404 |
| GET /pages — 存在的任务 | 200, 包含 page_states |
| GET /pages — 不存在的任务 | 404 |

共约 7 个测试。

### 10.3 config 测试

验证 `gallery_concurrency`、`page_concurrency`、`max_retry`、`retry_base_delay` 的加载、默认值和向后兼容（旧 `concurrency` 字段映射）。

共约 4 个测试。

## 11. 文件变更清单

| 文件 | 操作 | 预估行数 |
|------|------|----------|
| `pandora_daemon/download.py` | 重构 | ~400 行（从 ~340 行增长） |
| `pandora_daemon/config.py` | 修改 | +15 行 |
| `pandora_daemon/routes/downloads.py` | 修改 | +35 行 |
| `pandora_daemon/app.py` | 修改 | +2 行（构造参数变更） |
| `tests/pandora_daemon/test_download_concurrency.py` | 新建 | ~450 行 |
| `tests/pandora_daemon/test_routes_downloads.py` | 修改 | +80 行 |
| `tests/pandora_daemon/test_config.py` | 修改 | +40 行 |
