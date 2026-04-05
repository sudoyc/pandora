# P2 网络代理 + P3 变量重命名 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add network proxy/timeout config support and rename `preview_urls` → `viewer_urls` globally.

**Architecture:** Task 1 adds `NetworkConfig` to config system + wires proxy/timeout into `ExhentaiClient` and `_build_state()`. Task 2 is a mechanical global rename of `preview_urls` → `viewer_urls` across models, parsers, daemon code, tests, and docs.

**Tech Stack:** Python dataclasses, httpx, TOML config

**Spec:** `docs/superpowers/specs/2026-04-05-proxy-and-rename-design.md`

---

## File Structure

**Task 1 (P2 网络代理):**
- Modify: `pandora_daemon/config.py` — add `NetworkConfig`, wire into `PandoraConfig`
- Modify: `exhentai_api/client.py` — accept `proxy`/`timeout` params
- Modify: `pandora_daemon/app.py` — pass network config to client
- Modify: `tests/pandora_daemon/test_config.py` — add network config tests
- Modify: `tests/exhentai_api/test_client.py` — add proxy/timeout tests
- Modify: `tests/pandora_daemon/test_app_lifespan.py` — verify _build_state passes network config

**Task 2 (P3 rename):**
- Modify: `exhentai_api/models/gallery.py` — field rename
- Modify: `exhentai_api/parsers/gallery_detail.py` — variable rename
- Modify: `pandora_daemon/download.py` — reference rename
- Modify: `pandora_daemon/image_service.py` — reference rename
- Modify: `docs/api_reference.md` — doc update
- Modify: 5 test files — reference rename

---

### Task 1: P2 网络代理配置

**Files:**
- Modify: `pandora_daemon/config.py:1-179`
- Modify: `exhentai_api/client.py:19-38`
- Modify: `pandora_daemon/app.py:48-51`
- Modify: `tests/pandora_daemon/test_config.py`
- Modify: `tests/exhentai_api/test_client.py`
- Modify: `tests/pandora_daemon/test_app_lifespan.py`

- [ ] **Step 1: Write failing config tests**

Add to `tests/pandora_daemon/test_config.py`:

In the import block, add `NetworkConfig`:

```python
from pandora_daemon.config import (
    CacheConfig,
    CredentialsConfig,
    DownloadConfig,
    NetworkConfig,
    PandoraConfig,
    ServerConfig,
    load_config,
    save_config,
)
```

Add these test classes:

```python
class TestNetworkConfig:
    def test_default_network_config(self):
        net = NetworkConfig()
        assert net.proxy == ""
        assert net.timeout == 30

    def test_pandora_config_has_network(self):
        cfg = PandoraConfig()
        assert isinstance(cfg.network, NetworkConfig)

    def test_pandora_config_network_none_gets_default(self):
        cfg = PandoraConfig(network=None)
        assert isinstance(cfg.network, NetworkConfig)


class TestLoadConfigNetwork:
    def test_load_config_with_network_section(self, tmp_path):
        config_path = tmp_path / "config.toml"
        import tomli_w
        data = {
            "credentials": {"igneous": "", "ipb_member_id": ""},
            "server": {"host": "127.0.0.1", "port": 7860},
            "download": {"path": "~/Downloads/pandora", "gallery_concurrency": 2, "page_concurrency": 4, "max_retry": 3, "retry_base_delay": 2.0},
            "cache": {"image_dir": "~/.cache/pandora/images", "image_max_size_mb": 2048, "gallery_ttl_seconds": 300, "prefetch_ahead": 3, "prefetch_behind": 1, "eviction_interval_seconds": 600},
            "network": {"proxy": "socks5://127.0.0.1:1080", "timeout": 60},
        }
        config_path.write_bytes(tomli_w.dumps(data).encode())
        cfg = load_config(config_path)
        assert cfg.network.proxy == "socks5://127.0.0.1:1080"
        assert cfg.network.timeout == 60

    def test_load_config_without_network_section(self, tmp_path):
        config_path = tmp_path / "config.toml"
        import tomli_w
        data = {
            "credentials": {"igneous": "", "ipb_member_id": ""},
            "server": {"host": "127.0.0.1", "port": 7860},
            "download": {"path": "~/Downloads/pandora", "gallery_concurrency": 2, "page_concurrency": 4, "max_retry": 3, "retry_base_delay": 2.0},
            "cache": {"image_dir": "~/.cache/pandora/images", "image_max_size_mb": 2048, "gallery_ttl_seconds": 300, "prefetch_ahead": 3, "prefetch_behind": 1, "eviction_interval_seconds": 600},
        }
        config_path.write_bytes(tomli_w.dumps(data).encode())
        cfg = load_config(config_path)
        assert cfg.network.proxy == ""
        assert cfg.network.timeout == 30

    def test_to_public_dict_includes_network(self):
        cfg = PandoraConfig(network=NetworkConfig(proxy="http://proxy:8080", timeout=45))
        d = cfg.to_public_dict()
        assert "network" in d
        assert d["network"]["proxy"] == "http://proxy:8080"
        assert d["network"]["timeout"] == 45
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/pandora_daemon/test_config.py -v -k "Network or network"`
Expected: FAIL — `cannot import name 'NetworkConfig'`

- [ ] **Step 3: Implement NetworkConfig in config.py**

Add `NetworkConfig` dataclass after `CacheConfig` (after line 55):

```python
@dataclass
class NetworkConfig:
    """Network settings (proxy, timeout)."""

    proxy: str = ""
    timeout: int = 30
```

Add `network` field to `PandoraConfig` (after `cache` field, line 64):

```python
    network: NetworkConfig = field(default_factory=NetworkConfig)
```

Add to `__post_init__` (after the cache None check):

```python
        if self.network is None:
            self.network = NetworkConfig()
```

Add to `to_public_dict()` return dict (after cache section):

```python
            "network": {
                "proxy": self.network.proxy,
                "timeout": self.network.timeout,
            },
```

Add to `_to_dict()` — it calls `to_public_dict()` so network is already included. No change needed.

Add to `load_config()` (after cache parsing, before the return):

```python
    net_data = data.get("network", {})
    network = NetworkConfig(
        proxy=net_data.get("proxy", ""),
        timeout=net_data.get("timeout", 30),
    )
```

Add `network=network` to the `PandoraConfig(...)` return call.

- [ ] **Step 4: Run config tests to verify they pass**

Run: `uv run pytest tests/pandora_daemon/test_config.py -v`
Expected: ALL PASS

- [ ] **Step 5: Write failing client tests**

Add to `tests/exhentai_api/test_client.py`:

```python
@pytest.mark.asyncio
async def test_client_default_timeout():
    client = ExhentaiClient()
    assert client.session.timeout.connect == 30.0
    await client.aclose()

@pytest.mark.asyncio
async def test_client_custom_timeout():
    client = ExhentaiClient(timeout=60)
    assert client.session.timeout.connect == 60.0
    await client.aclose()

@pytest.mark.asyncio
async def test_client_with_proxy():
    client = ExhentaiClient(proxy="http://127.0.0.1:8080")
    # httpx stores proxy config in transport
    # Just verify construction doesn't raise
    assert not client.session.is_closed
    await client.aclose()

@pytest.mark.asyncio
async def test_client_without_proxy():
    client = ExhentaiClient()
    assert not client.session.is_closed
    await client.aclose()
```

- [ ] **Step 6: Run client tests to verify they fail**

Run: `uv run pytest tests/exhentai_api/test_client.py -v -k "timeout or proxy"`
Expected: FAIL — `__init__() got an unexpected keyword argument 'timeout'` (for custom_timeout) and `'proxy'`

- [ ] **Step 7: Implement proxy/timeout in ExhentaiClient**

Replace `ExhentaiClient.__init__` in `exhentai_api/client.py`:

```python
    def __init__(self, igneous: str = "", ipb_member_id: str = "",
                 proxy: str = "", timeout: int = 30):
        self.cookies = {}
        if igneous:
            self.cookies["igneous"] = igneous
        if ipb_member_id:
            self.cookies["ipb_member_id"] = ipb_member_id

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        }

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

- [ ] **Step 8: Run client tests to verify they pass**

Run: `uv run pytest tests/exhentai_api/test_client.py -v`
Expected: ALL PASS

- [ ] **Step 9: Update _build_state to pass network config**

In `pandora_daemon/app.py`, change the `ExhentaiClient(...)` call in `_build_state()` (lines 48-51):

```python
    client = ExhentaiClient(
        igneous=config.credentials.igneous,
        ipb_member_id=config.credentials.ipb_member_id,
        proxy=config.network.proxy,
        timeout=config.network.timeout,
    )
```

- [ ] **Step 10: Update _build_state test**

In `tests/pandora_daemon/test_app_lifespan.py`, add a test to `TestBuildState`:

```python
    @pytest.mark.asyncio
    async def test_build_state_passes_network_config(self):
        """_build_state passes proxy and timeout from config to ExhentaiClient."""
        with (
            patch("pandora_daemon.app.load_config") as mock_load,
            patch("pandora_daemon.app.PandoraDB") as mock_db_cls,
            patch("pandora_daemon.app.ExhentaiClient") as mock_client_cls,
            patch("pandora_daemon.app.ExhentaiAPI") as mock_api_cls,
            patch("pandora_daemon.app.CacheManager") as mock_cache_cls,
            patch("pandora_daemon.app.ImageService") as mock_img_cls,
            patch("pandora_daemon.app.WebSocketManager") as mock_ws_cls,
            patch("pandora_daemon.app.TagDatabase") as mock_tag_cls,
            patch("pandora_daemon.app.DownloadManager") as mock_dl_cls,
        ):
            mock_config = MagicMock()
            mock_config.credentials.igneous = "test"
            mock_config.credentials.ipb_member_id = "test"
            mock_config.network.proxy = "socks5://127.0.0.1:1080"
            mock_config.network.timeout = 60
            mock_load.return_value = mock_config

            mock_db = AsyncMock()
            mock_db.initialize = AsyncMock()
            mock_db_cls.return_value = mock_db

            mock_tag = MagicMock()
            mock_tag.download_and_load = AsyncMock()
            mock_tag_cls.return_value = mock_tag

            await _build_state()

            mock_client_cls.assert_called_once_with(
                igneous="test",
                ipb_member_id="test",
                proxy="socks5://127.0.0.1:1080",
                timeout=60,
            )
```

- [ ] **Step 11: Run all tests**

Run: `uv run pytest --tb=short -q`
Expected: ALL PASS

- [ ] **Step 12: Commit**

```bash
git add pandora_daemon/config.py exhentai_api/client.py pandora_daemon/app.py tests/pandora_daemon/test_config.py tests/exhentai_api/test_client.py tests/pandora_daemon/test_app_lifespan.py
git commit -m "feat(config): add network proxy and timeout configuration"
```

---

### Task 2: P3 preview_urls → viewer_urls 全局重命名

**Files:**
- Modify: `exhentai_api/models/gallery.py:50`
- Modify: `exhentai_api/parsers/gallery_detail.py:82-92,251`
- Modify: `pandora_daemon/download.py:52,112,120,133,272,277`
- Modify: `pandora_daemon/image_service.py:61-68,94,101,106`
- Modify: `docs/api_reference.md:150`
- Modify: `tests/pandora_daemon/test_download_concurrency.py` (19 occurrences)
- Modify: `tests/pandora_daemon/test_download.py` (4 occurrences)
- Modify: `tests/pandora_daemon/test_routes_gallery.py:33`
- Modify: `tests/pandora_daemon/test_auto_triggers.py:33`
- Modify: `tests/pandora_daemon/test_image_service.py` (3 occurrences)

- [ ] **Step 1: Rename in model**

In `exhentai_api/models/gallery.py:50`, change:

```python
    preview_urls: List[str] = field(default_factory=list)
```

to:

```python
    viewer_urls: List[str] = field(default_factory=list)
```

- [ ] **Step 2: Rename in parser**

In `exhentai_api/parsers/gallery_detail.py`, change all occurrences of `preview_urls` to `viewer_urls`:

Line 82: `viewer_urls = []`
Line 86: `viewer_urls.append(a_tag.get("href"))`
Line 87: `if not viewer_urls:`
Line 92: `viewer_urls.append(a_tag.get("href"))`
Line 251: `preview_urls=viewer_urls,` → `viewer_urls=viewer_urls,`

- [ ] **Step 3: Rename in download.py**

In `pandora_daemon/download.py`, change all `preview_urls` to `viewer_urls`:

Line 52: `viewer_urls: list[str] = field(default_factory=list)`
Line 112: `viewer_urls = list(detail.viewer_urls)`
Line 120: `viewer_urls.extend(page_detail.viewer_urls)`
Line 133: `viewer_urls=viewer_urls,`
Line 272: `if idx >= len(task.viewer_urls):`
Line 277: `viewer_url = task.viewer_urls[idx]`

- [ ] **Step 4: Rename in image_service.py**

In `pandora_daemon/image_service.py`, change all `preview_urls` to `viewer_urls`:

Line 61: comment `# If page is beyond currently loaded viewer_urls, fetch the needed preview page`
Line 62: `if page_idx >= len(detail.viewer_urls):`
Line 65: `if page_idx >= len(detail.viewer_urls):`
Line 68: `viewer_url = detail.viewer_urls[page_idx]`
Line 94: `items_per_page = len(detail.viewer_urls) if detail.viewer_urls else 20`
Line 101: `if len(detail.viewer_urls) > target_page_idx:`
Line 106: `detail.viewer_urls.extend(page_detail.viewer_urls)`

- [ ] **Step 5: Rename in docs**

In `docs/api_reference.md:150`, change:

```
- `preview_urls` (List[str]): Viewer page URLs (`/s/{imgkey}/{gid}-{page}`).
```

to:

```
- `viewer_urls` (List[str]): Viewer page URLs (`/s/{imgkey}/{gid}-{page}`).
```

- [ ] **Step 6: Rename in all test files**

Global find-and-replace `preview_urls` → `viewer_urls` in:

- `tests/pandora_daemon/test_download_concurrency.py` (19 occurrences)
- `tests/pandora_daemon/test_download.py` (4 occurrences)
- `tests/pandora_daemon/test_routes_gallery.py` (1 occurrence, line 33)
- `tests/pandora_daemon/test_auto_triggers.py` (1 occurrence, line 33)
- `tests/pandora_daemon/test_image_service.py` (3 occurrences)

- [ ] **Step 7: Run full test suite**

Run: `uv run pytest --tb=short -q`
Expected: ALL PASS

- [ ] **Step 8: Verify no remaining preview_urls in source code**

Run: `grep -rn "preview_urls" exhentai_api/ pandora_daemon/ tests/ docs/api_reference.md`
Expected: No matches (only docs/superpowers/ plan/spec files may still reference it, which is fine)

- [ ] **Step 9: Commit**

```bash
git add exhentai_api/models/gallery.py exhentai_api/parsers/gallery_detail.py pandora_daemon/download.py pandora_daemon/image_service.py docs/api_reference.md tests/
git commit -m "refactor: rename preview_urls to viewer_urls globally"
```

---

### Task 3: 更新文档

**Files:**
- Modify: `IMPROVEMENTS.md`
- Modify: `CLAUDE.md` (not committed, in .gitignore)

- [ ] **Step 1: Update IMPROVEMENTS.md**

In the priority table (~line 830-831), change:

```
| **P2** | 网络代理配置 (第 6 章) | 用户便利性 | 修改 `config.py` + `client.py` | 待实施 |
| **P3** | 杂项修正 (第 7 章) | 代码质量 | 全局 rename + 逻辑统一 | 待实施 |
```

to:

```
| **P2** | 网络代理配置 (第 6 章) | 用户便利性 | 修改 `config.py` + `client.py` | ✅ 已完成 |
| **P3** | 杂项修正 (第 7 章) | 代码质量 | 全局 rename + 逻辑统一 | ✅ 已完成 |
```

- [ ] **Step 2: Update CLAUDE.md**

Update the IMPROVEMENTS ROADMAP table:

```
| P2 | 网络代理配置 — `config.py` + `client.py`: NetworkConfig(proxy, timeout) | ✅ 已完成 |
| P3 | 杂项修正 — preview_urls → viewer_urls 全局重命名 | ✅ 已完成 |
```

Update NEXT STEPS — remove P3 reference, point to next milestone (Web Frontend or TUI improvements).

- [ ] **Step 3: Commit**

```bash
git add IMPROVEMENTS.md
git commit -m "docs: mark P2 proxy and P3 rename as complete"
```
