# P1: 下载并发+重试+image_service 集成

> 日期：2026-04-05
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

## 2. 设计概览

### 2.1 改动范围

| 文件 | 操作 | 说明 |
|------|------|------|
| `pandora_daemon/download.py` | 重构 | 并发下载、异常重试、页面状态、debounce 保存、image_service 集成 |
| `pandora_daemon/config.py` | 修改 | 新增 `page_concurrency` 参数 |
| `pandora_daemon/routes/downloads.py` | 修改 | 新增 3 个端点 |
| `pandora_daemon/app.py` | 修改 | DownloadManager 构造传入 image_service |

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
"completed_with_errors"   # 重试后仍有失败页
"paused"                  # ImageLimitError (509) 触发暂停
"retrying"                # 正在重试失败页
```

### 3.3 状态转换图

```
queued → downloading → completed
                     → completed_with_errors (有失败页)
                     → failed (不可恢复错误)
                     → paused (ImageLimitError)
                     → cancelled

paused → downloading (用户 resume)
completed_with_errors → retrying → completed / completed_with_errors
```

## 4. DownloadManager 改动

### 4.1 构造函数变更

```python
class DownloadManager:
    def __init__(self, api, config, ws, cache, image_service, state_file: Path) -> None:
        self._api = api
        self._config = config
        self._ws = ws
        self._cache = cache
        self._image_service = image_service  # 新增
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

注意：`image_service` 参数插入在 `cache` 和 `state_file` 之间。`app.py` 中构造 DownloadManager 时需要传入 `image_service`。

### 4.2 _fetch_image 改为使用 image_service

删除现有的 `_fetch_image` 方法，替换为：

```python
async def _fetch_image(self, url: str) -> bytes:
    """Fetch image bytes via ImageService (cache-first)."""
    return await self._image_service.proxy_image(url)
```

所有图片获取（包括 `_download_thumbs` 中的 sprite 图片）都通过 `_fetch_image` → `image_service.proxy_image()` 路径。`_crop_sprite` 是纯计算的 `@staticmethod`，接收 bytes 输入，不涉及网络。

**结果**：移除构造函数中的 `cache` 参数。`image_service` 内部已处理缓存。

### 4.3 并发页面下载

将 `_download_gallery` 中的串行页面下载循环替换为并发版本：

```python
async def _download_pages(self, task: DownloadTask) -> None:
    """并发下载全部页面图片。使用 stop_reason 标志优雅停止。"""
    semaphore = asyncio.Semaphore(self._config.page_concurrency)
    pages_dir = Path(task.output_dir) / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    stop_reason: Exception | None = None

    for i in range(1, task.total_pages + 1):
        if i not in task.page_states or task.page_states[i] != "done":
            task.page_states[i] = "pending"

    async def _download_one_page(page_num: int) -> None:
        nonlocal stop_reason
        if stop_reason is not None:
            return
        if task.page_states.get(page_num) == "done":
            return
        existing = list(pages_dir.glob(f"{page_num:04d}.*"))
        if existing:
            task.page_states[page_num] = "done"
            return

        async with semaphore:
            if stop_reason is not None or task.gid in self._cancelled:
                return
            task.page_states[page_num] = "downloading"

            idx = page_num - 1
            if idx >= len(task.preview_urls):
                task.page_states[page_num] = "failed"
                task.failed_pages.append(page_num)
                return

            viewer_url = task.preview_urls[idx]
            try:
                html = await self._api.client.get_html(viewer_url)
                image_url, _ = parse_image_viewer(html)
                if not image_url:
                    raise ParseError(f"No image URL for page {page_num}")
                data = await self._fetch_image(image_url)
                ext = _ext_from_url(image_url)
                (pages_dir / f"{page_num:04d}{ext}").write_bytes(data)
                task.page_states[page_num] = "done"
                task.downloaded_pages += 1
            except (AuthenticationError, ImageLimitError, GalleryNotFoundError) as e:
                stop_reason = e
                task.page_states[page_num] = "failed"
                return
            except Exception:
                task.page_states[page_num] = "failed"
                task.failed_pages.append(page_num)

            await self._ws.broadcast({
                "event": "download_progress", "gid": task.gid,
                "phase": "pages", "page": page_num, "total": task.total_pages,
            })
            self._mark_dirty()

    coros = [_download_one_page(p) for p in range(1, task.total_pages + 1)]
    await asyncio.gather(*coros)

    if stop_reason is not None:
        raise stop_reason
```

**设计要点**：不使用 `asyncio.gather(return_exceptions=False)` 让异常直接取消其他协程（会中断正在写入的页面）。而是用 `stop_reason` 共享标志，让其他协程在获取 semaphore 前检查并优雅退出。gather 完成后，如果有 stop_reason 则向上抛出。

### 4.4 异常驱动的重试策略

在 `_download_gallery` 中处理异常和重试：

```python
MAX_PAGE_RETRY = 2

async def _download_gallery(self, task: DownloadTask) -> None:
    task.status = "downloading"
    output_dir = Path(task.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Phase 1: metadata (不变)
        # Phase 2: cover (不变)
        # Phase 3: thumbs (不变，但 _fetch_image 已走 image_service)

        # Phase 4: pages — 并发下载
        await self._download_pages(task)

        # Phase 5: 重试失败页
        for attempt in range(MAX_PAGE_RETRY):
            if not task.failed_pages:
                break
            task.status = "retrying"
            retry_pages = task.failed_pages.copy()
            task.failed_pages.clear()
            await self._retry_pages(task, retry_pages)

        # 最终状态
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
        # 暂停所有其他任务
        await self._pause_all_tasks()

    except ImageLimitError as e:
        task.status = "paused"
        task.error = str(e)
        await self._ws.broadcast(
            {"event": "download_paused", "gid": task.gid, "error": str(e)}
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

### 4.5 _retry_pages 方法

```python
async def _retry_pages(self, task: DownloadTask, pages: list[int]) -> None:
    """重试指定的失败页面，使用与 _download_pages 相同的并发逻辑。"""
    semaphore = asyncio.Semaphore(self._config.page_concurrency)
    pages_dir = Path(task.output_dir) / "pages"
    stop_reason: Exception | None = None

    async def _retry_one(page_num: int) -> None:
        nonlocal stop_reason
        if stop_reason is not None or task.gid in self._cancelled:
            return
        # 与 _download_one_page 相同的逻辑
        # ...（省略，实现与 4.3 中的 _download_one_page 相同）

    coros = [_retry_one(p) for p in pages]
    await asyncio.gather(*coros)
    if stop_reason is not None:
        raise stop_reason
```

为避免代码重复，`_download_one_page` 应提取为 `_download_single_page` 实例方法，被 `_download_pages` 和 `_retry_pages` 共用。

### 4.6 _pause_all_tasks 方法

```python
async def _pause_all_tasks(self) -> None:
    """AuthenticationError 时暂停所有正在下载的任务。"""
    for task in self._tasks.values():
        if task.status in ("queued", "downloading", "retrying"):
            task.status = "paused"
            await self._ws.broadcast(
                {"event": "download_paused", "gid": task.gid, "error": "Authentication failed"}
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

当 worker 从队列取出一个 `completed_with_errors` 的任务时，`_download_gallery` 需要检测这种情况，跳过 metadata/cover/thumbs 阶段，直接进入重试失败页。

修改 `_download_gallery` 开头：

```python
async def _download_gallery(self, task: DownloadTask) -> None:
    is_retry = bool(task.failed_pages) and task.downloaded_pages > 0
    task.status = "downloading" if not is_retry else "retrying"

    if is_retry:
        # 直接重试失败页，跳过其他阶段
        retry_pages = task.failed_pages.copy()
        task.failed_pages.clear()
        try:
            await self._retry_pages(task, retry_pages)
        except ...:
            # 同样的异常处理
            ...
        # 最终状态判定
        ...
        return

    # 正常流程：metadata → cover → thumbs → pages → retry
    ...
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

## 5. 配置变更

### 5.1 DownloadConfig 新增字段

```python
@dataclass
class DownloadConfig:
    path: str = "~/Downloads/pandora"
    concurrency: int = 3          # 画廊级 worker 数
    page_concurrency: int = 5     # 页面级并发数（每个画廊内）
```

### 5.2 load_config 修改

```python
dl_data = data.get("download", {})
download = DownloadConfig(
    path=dl_data.get("path", "~/Downloads/pandora"),
    concurrency=dl_data.get("concurrency", 3),
    page_concurrency=dl_data.get("page_concurrency", 5),  # 新增
)
```

### 5.3 to_public_dict 修改

```python
"download": {
    "path": self.download.path,
    "concurrency": self.download.concurrency,
    "page_concurrency": self.download.page_concurrency,  # 新增
},
```

## 6. REST 端点变更

### 6.1 新增端点

在 `routes/downloads.py` 中新增 3 个端点：

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
{"event": "download_paused", "gid": "123", "error": "Image viewing limit exceeded"}
{"event": "download_auth_failed", "gid": "123", "error": "Sad Panda: cookies invalid"}
```

### 7.2 现有事件不变

`download_queued`、`download_progress`、`download_complete`、`download_error`、`download_cancelled` 保持不变。

## 8. app.py 集成变更

### 8.1 DownloadManager 构造修改

```python
# 现有
downloads = DownloadManager(api, config.download, ws, cache, state_file)

# 改为
downloads = DownloadManager(api, config.download, ws, cache, image_service, state_file)
```

注意：虽然 4.2 节提到可以移除 `cache` 参数，但为了最小化改动和保持向后兼容，保留 `cache` 参数。`_fetch_image` 不再使用它，但其他代码路径可能仍需要。

**最终决定**：检查 download.py 中 `self._cache` 的所有使用点：
- `_fetch_image` — 改为走 image_service，不再需要 `self._cache`
- `_download_thumbs` 中的 sprite 获取 — 调用 `self._fetch_image`，间接走 image_service

结论：`self._cache` 在 download.py 中不再被直接使用。移除 `cache` 参数。

```python
# 最终
downloads = DownloadManager(api, config.download, ws, image_service, state_file)
```

## 9. 测试计划

### 9.1 download.py 单元测试 (`tests/pandora_daemon/test_download_concurrency.py`)

使用 mock API、mock ImageService、mock WS，测试核心逻辑：

| 测试组 | 用例数 | 覆盖 |
|--------|--------|------|
| 并发下载 | 4 | 基本并发、semaphore 限制、断点续传跳过已完成页、cancelled 中断 |
| 异常重试 | 5 | NetworkError 重试成功、ParseError 重试、重试耗尽 → completed_with_errors、ImageLimitError → paused、AuthenticationError → failed + pause_all |
| 页面状态 | 3 | page_states 初始化、下载后更新、failed_pages 记录 |
| debounce 保存 | 3 | _mark_dirty 触发延迟保存、即时保存场景、shutdown 取消 debounce |
| resume/retry | 3 | resume paused 任务、retry_failed 任务、非法状态返回 False |
| image_service 集成 | 2 | _fetch_image 调用 image_service.proxy_image、不再直接访问 client.session |

共约 20 个测试。

### 9.2 路由测试 (`tests/pandora_daemon/test_routes_downloads.py`)

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

### 9.3 config 测试

验证 `page_concurrency` 的加载和默认值。

共约 2 个测试。

## 10. 文件变更清单

| 文件 | 操作 | 预估行数 |
|------|------|----------|
| `pandora_daemon/download.py` | 重构 | ~380 行（从 ~340 行增长） |
| `pandora_daemon/config.py` | 修改 | +5 行 |
| `pandora_daemon/routes/downloads.py` | 修改 | +35 行 |
| `pandora_daemon/app.py` | 修改 | +2 行（构造参数变更） |
| `tests/pandora_daemon/test_download_concurrency.py` | 新建 | ~350 行 |
| `tests/pandora_daemon/test_routes_downloads.py` | 修改 | +80 行 |
| `tests/pandora_daemon/test_config.py` | 修改 | +20 行 |
