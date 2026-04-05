# P2 网络代理 + P3 变量重命名 Design Spec

**日期:** 2026-04-05
**状态:** 已批准
**范围:** P2 网络代理配置 + P3 preview_urls → viewer_urls 重命名

## 1. P2 网络代理配置

### 1.1 现状

`ExhentaiClient` 硬编码 `timeout=30.0`，无代理支持。用户部署到服务器后无法通过配置文件指定代理。

### 1.2 改进方案

#### config.py

新增 `NetworkConfig`：

```python
@dataclass
class NetworkConfig:
    proxy: str = ""
    timeout: int = 30
```

`PandoraConfig` 新增字段：

```python
@dataclass
class PandoraConfig:
    # ... 现有 ...
    network: NetworkConfig = field(default_factory=NetworkConfig)
```

`load_config()` 解析 `[network]` section。`to_public_dict()` 和 `_to_dict()` 包含 network section。`__post_init__` 处理 `network is None`。

config.toml 新增：

```toml
[network]
proxy = ""
timeout = 30
```

#### exhentai_api/client.py

`ExhentaiClient.__init__` 接受 `proxy` 和 `timeout`：

```python
def __init__(self, igneous="", ipb_member_id="",
             proxy: str = "", timeout: int = 30):
    # ... cookies/headers 不变 ...
    client_kwargs: dict = {
        "cookies": self.cookies,
        "headers": self.headers,
        "timeout": float(timeout),
        "follow_redirects": True,
    }
    if proxy:
        client_kwargs["proxy"] = proxy
    self.session = httpx.AsyncClient(**client_kwargs)
```

#### app.py

`_build_state()` 构建 client 时传入：

```python
client = ExhentaiClient(
    igneous=config.credentials.igneous,
    ipb_member_id=config.credentials.ipb_member_id,
    proxy=config.network.proxy,
    timeout=config.network.timeout,
)
```

### 1.3 改动文件

| 文件 | 改动 |
|------|------|
| `pandora_daemon/config.py` | 新增 `NetworkConfig`，`PandoraConfig` 加 `network` 字段，更新 `load_config`/`to_public_dict`/`_to_dict`/`__post_init__` |
| `exhentai_api/client.py` | `__init__` 接受 `proxy`/`timeout` 参数 |
| `pandora_daemon/app.py` | `_build_state()` 传入 proxy/timeout |

---

## 2. P3 preview_urls → viewer_urls

### 2.1 现状

`GalleryDetail.preview_urls` 存储的是 viewer page URL（`/s/xxx/gid-page`），不是预览图 URL。与 `thumb_urls`（真正的缩略图 URL）容易混淆。

### 2.2 改进方案

全局重命名 `preview_urls` → `viewer_urls`。纯机械替换。

### 2.3 改动文件

| 文件 | 改动 |
|------|------|
| `exhentai_api/models/gallery.py` | 字段定义 `preview_urls` → `viewer_urls` |
| `exhentai_api/parsers/gallery_detail.py` | 赋值 |
| `pandora_daemon/download.py` | 引用 |
| `pandora_daemon/image_service.py` | 引用 |
| `pandora_daemon/routes/gallery.py` | 序列化 |
| `docs/api_reference.md` | API 文档 |
| `tests/` (约 5 个文件) | 测试中的引用和断言 |

不改 TUI（Rust 端独立项目）。

---

## 3. 测试计划

### P2 网络代理

| 测试 | 验证点 |
|------|--------|
| `test_network_config_defaults` | NetworkConfig 默认值 proxy=""、timeout=30 |
| `test_load_config_with_network_section` | TOML 中 [network] 正确解析 |
| `test_load_config_without_network_section` | 缺少 [network] 时使用默认值 |
| `test_to_public_dict_includes_network` | to_public_dict 包含 network |
| `test_client_with_proxy` | ExhentaiClient 传入 proxy 后 session 配置正确 |
| `test_client_without_proxy` | 不传 proxy 时行为不变 |
| `test_client_custom_timeout` | 自定义 timeout 生效 |
| `test_build_state_passes_network_config` | _build_state 将 network config 传给 client |

### P3 重命名

| 测试 | 验证点 |
|------|--------|
| 现有测试全部通过 | rename 后无遗漏引用 |
| grep 确认无残留 `preview_urls` | 代码中不再有旧名称 |
