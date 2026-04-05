# P0: 异常体系设计

> 日期：2026-04-05  
> 范围：`exhentai_api/exceptions.py`（新建）、`exhentai_api/client.py`（修改）、`pandora_daemon/app.py`（修改）  
> 不改动：parsers、download.py、routes、TUI

---

## 1. 问题

- `exhentai_api` 只有 3 个 raise 语句，全用裸 `Exception` / `ValueError`
- daemon 的 `app.py` 用字符串匹配 `"Sad Panda" in str(exc)` 区分错误类型
- 下载管理器无法区分可重试 / 不可重试错误（为 P1 下载改进做基础）
- HTTP 509（图片限额）、kokomade（画廊删除）、offensive content 等场景没有语义化异常

## 2. 异常层级

新建 `exhentai_api/exceptions.py`：

```python
class ExhentaiError(Exception):
    """所有 exhentai_api 异常的基类。"""

class AuthenticationError(ExhentaiError):
    """Sad Panda / Cookie 失效。不重试。"""

class ImageLimitError(ExhentaiError):
    """HTTP 509 图片限额耗尽。暂停等待恢复。"""

class GalleryNotFoundError(ExhentaiError):
    """画廊不存在 / 已删除 (kokomade / pining)。永久失败。"""

class GalleryOffensiveError(ExhentaiError):
    """攻击性内容警告。需用户确认。"""

class ParseError(ExhentaiError):
    """解析结果异常。可重试 1-2 次。"""

class NetworkError(ExhentaiError):
    """网络请求失败（超时/连接重置）。指数退避重试。"""
```

同时在 `exhentai_api/__init__.py` 中导出所有异常类。

## 3. client.py 修改

### 3.1 get_html()

```python
async def get_html(self, url, params=None, retries=3, backoff_factor=0.1):
    last_exception = None
    for attempt in range(retries):
        try:
            response = await self.session.get(url, params=params)

            # Sad Panda 检测 → AuthenticationError（不重试）
            if 'inline; filename="sadpanda.jpg"' in response.headers.get("Content-Disposition", ""):
                raise AuthenticationError("Sad Panda: cookies invalid or IP blocked")

            # HTTP 状态码检测
            response.raise_for_status()

            html = response.text

            # HTML 内容检测（在返回前）
            if "kokomade" in html or "This gallery has been removed" in html:
                raise GalleryNotFoundError("Gallery removed or unavailable")
            if "offensive" in html and "Content Warning" in html:
                raise GalleryOffensiveError("Offensive content warning")

            return html

        except (AuthenticationError, GalleryNotFoundError, GalleryOffensiveError):
            raise  # 语义化异常不重试，直接抛出

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 509:
                raise ImageLimitError("Image viewing limit exceeded") from e
            last_exception = NetworkError(str(e))
            # 其他 HTTP 错误走重试

        except (httpx.TimeoutException, httpx.ConnectError) as e:
            last_exception = NetworkError(str(e))

        except Exception as e:
            last_exception = e

        if attempt < retries - 1:
            await asyncio.sleep(backoff_factor * (2 ** attempt))

    if last_exception:
        if isinstance(last_exception, ExhentaiError):
            raise last_exception
        raise NetworkError(str(last_exception)) from last_exception
    return ""
```

### 3.2 post_json()

同样的模式：
- 捕获 `httpx.HTTPStatusError`，509 → `ImageLimitError`
- 捕获 `httpx.TimeoutException` / `httpx.ConnectError` → `NetworkError`
- 最终未恢复的异常包装为 `NetworkError`

### 3.3 post_form()

与 post_json() 相同的异常包装逻辑。

### 3.4 不重试的异常

以下异常检测到后立即抛出，不进入重试循环：
- `AuthenticationError`（Sad Panda）
- `GalleryNotFoundError`（kokomade / removed）
- `GalleryOffensiveError`（offensive content）
- `ImageLimitError`（509）

### 3.5 kokomade / offensive 检测细节

参考 EhViewer 的检测逻辑：

| 检测条件 | 异常 |
|----------|------|
| HTML 包含 `"kokomade"` | `GalleryNotFoundError` |
| HTML 包含 `"This gallery has been removed"` | `GalleryNotFoundError` |
| HTML 包含 `"pining for the fjords"` | `GalleryNotFoundError` |
| HTML 包含 `"Content Warning"` 且包含 `"offensive"` | `GalleryOffensiveError` |
| Content-Disposition 包含 `sadpanda.jpg` | `AuthenticationError` |
| HTTP 509 | `ImageLimitError` |

注意：这些检测只在 `get_html()` 中进行。`post_json()` 和 `post_form()` 不检测 HTML 内容（它们处理的是 JSON/form 响应）。

## 4. daemon app.py 修改

替换现有的两个 exception handler：

```python
from exhentai_api.exceptions import (
    ExhentaiError, AuthenticationError, ImageLimitError,
    GalleryNotFoundError, GalleryOffensiveError, ParseError, NetworkError,
)

@app.exception_handler(AuthenticationError)
async def auth_error_handler(request, exc):
    return JSONResponse(status_code=401, content={"error": "auth", "detail": str(exc)})

@app.exception_handler(GalleryNotFoundError)
async def not_found_handler(request, exc):
    return JSONResponse(status_code=404, content={"error": "gallery_not_found", "detail": str(exc)})

@app.exception_handler(ImageLimitError)
async def limit_handler(request, exc):
    return JSONResponse(status_code=429, content={"error": "image_limit", "detail": str(exc)})

@app.exception_handler(GalleryOffensiveError)
async def offensive_handler(request, exc):
    return JSONResponse(status_code=451, content={"error": "offensive", "detail": str(exc)})

@app.exception_handler(ParseError)
async def parse_handler(request, exc):
    return JSONResponse(status_code=502, content={"error": "parse", "detail": str(exc)})

@app.exception_handler(NetworkError)
async def network_handler(request, exc):
    return JSONResponse(status_code=502, content={"error": "network", "detail": str(exc)})

# 兜底：未分类的 ExhentaiError
@app.exception_handler(ExhentaiError)
async def exhentai_error_handler(request, exc):
    return JSONResponse(status_code=500, content={"error": "exhentai", "detail": str(exc)})

# 兜底：其他未预期异常
@app.exception_handler(Exception)
async def generic_error_handler(request, exc):
    return JSONResponse(status_code=500, content={"detail": str(exc)})
```

## 5. 响应格式

所有 ExhentaiError 子类的 HTTP 响应统一格式：

```json
{
    "error": "<error_type>",
    "detail": "<human-readable message>"
}
```

| error_type | HTTP 状态码 | 含义 |
|------------|------------|------|
| `auth` | 401 | 认证失败 |
| `gallery_not_found` | 404 | 画廊不存在 |
| `image_limit` | 429 | 图片限额 |
| `offensive` | 451 | 攻击性内容 |
| `parse` | 502 | 解析失败 |
| `network` | 502 | 网络错误 |
| `exhentai` | 500 | 未分类 |

## 6. 不改动的部分

- **parsers/**：保持防御性编程，返回默认值。不引入异常。
- **download.py**：不改重试逻辑。留给 P1 下载系统改进。
- **routes/**：不改。异常由 FastAPI exception handler 统一处理。
- **TUI**：不改。TUI 通过 HTTP 状态码判断错误类型。
- **api.py**：不改。api.py 调用 client 方法，异常自然传播。
- **utils.py**：`extract_gallery_token()` 的 `ValueError` 保持不变（这是参数校验，不是网络错误）。

## 7. 测试计划

### 7.1 exhentai_api/exceptions.py 测试

- 异常继承关系：所有子类都是 `ExhentaiError` 的子类
- 异常可以携带消息
- `isinstance` 检查正确

### 7.2 client.py 测试

用 `respx` mock httpx 请求：

| 测试用例 | 模拟条件 | 预期异常 |
|----------|----------|----------|
| Sad Panda | Content-Disposition 包含 sadpanda.jpg | `AuthenticationError` |
| HTTP 509 | 响应状态码 509 | `ImageLimitError` |
| kokomade | HTML 包含 "kokomade" | `GalleryNotFoundError` |
| Gallery removed | HTML 包含 "This gallery has been removed" | `GalleryNotFoundError` |
| Pining | HTML 包含 "pining for the fjords" | `GalleryNotFoundError` |
| Offensive content | HTML 包含 "Content Warning" + "offensive" | `GalleryOffensiveError` |
| 超时 | `httpx.TimeoutException` | `NetworkError` |
| 连接失败 | `httpx.ConnectError` | `NetworkError` |
| 正常响应 | 200 + 正常 HTML | 无异常 |
| 不重试语义异常 | Sad Panda | 只请求 1 次（不重试） |
| 重试网络错误 | 前 2 次超时，第 3 次成功 | 无异常，请求 3 次 |
| post_json 509 | 响应状态码 509 | `ImageLimitError` |
| post_form 超时 | `httpx.TimeoutException` | `NetworkError` |

### 7.3 daemon app.py 测试

用 FastAPI TestClient + mock：

| 测试用例 | 模拟条件 | 预期 HTTP 状态码 | 预期 error 字段 |
|----------|----------|-----------------|----------------|
| 认证失败 | 路由抛出 `AuthenticationError` | 401 | `auth` |
| 画廊不存在 | 路由抛出 `GalleryNotFoundError` | 404 | `gallery_not_found` |
| 图片限额 | 路由抛出 `ImageLimitError` | 429 | `image_limit` |
| 攻击性内容 | 路由抛出 `GalleryOffensiveError` | 451 | `offensive` |
| 解析失败 | 路由抛出 `ParseError` | 502 | `parse` |
| 网络错误 | 路由抛出 `NetworkError` | 502 | `network` |
| 未分类 | 路由抛出 `ExhentaiError` | 500 | `exhentai` |
| 兜底 | 路由抛出 `RuntimeError` | 500 | 无 error 字段 |

## 8. 文件变更清单

| 文件 | 操作 | 预估行数 |
|------|------|----------|
| `exhentai_api/exceptions.py` | 新建 | ~30 行 |
| `exhentai_api/__init__.py` | 修改（添加导出） | +3 行 |
| `exhentai_api/client.py` | 修改（异常分类 + 内容检测） | ~+40 行 |
| `pandora_daemon/app.py` | 修改（exception handlers） | ~+20 行 |
| `tests/test_exceptions.py` | 新建 | ~30 行 |
| `tests/test_client_exceptions.py` | 新建 | ~120 行 |
| `tests/test_daemon_exception_handlers.py` | 新建 | ~80 行 |
