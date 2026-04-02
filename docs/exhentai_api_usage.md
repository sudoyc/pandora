# Exhentai API (`exhentai_api`) 使用说明文档

## 概述
`exhentai_api` 是一个专为 Exhentai/E-Hentai 设计的数据抓取与解析层，由之前的单体 `parser.py` 和 `client.py` 重构而来。此包旨在提供清晰、强类型、且易于维护的高层级 API，供 TUI 界面或其他前端调用。它底层依赖于 `httpx` (异步) 进行网络请求，以及 `BeautifulSoup4` 进行 HTML 解析。

## 包结构
```text
exhentai_api/
├── __init__.py        # 暴露核心类：ExhentaiAPI, ExhentaiClient, GalleryListItem
├── api.py             # 高层 API 封装 (目前实现: get_homepage)
├── client.py          # 核心异步 HTTP 客户端 (负责请求头、Cookies、Sad Panda 处理、重试机制)
├── constants.py       # 全局常量 (URL、分类枚举)
├── utils.py           # 辅助工具 (例如解析图库 url 提取 gid 和 token)
├── models/            # Pydantic/Dataclass 数据模型 (强类型数据)
│   ├── gallery.py     # GalleryListItem, GalleryDetail
│   ├── image.py       # ImageDetail
│   └── tags.py        # Tag, WatchedTag
└── parsers/           # 纯函数 HTML 解析器
    └── gallery.py     # 解析画廊列表
```

## 核心功能与使用示例

### 1. 初始化客户端与高层 API
为了使用该包，通常我们只需要初始化 `ExhentaiAPI`。可以传入自定义的 Cookie（如 `igneous`, `ipb_member_id`）来避免访客限制或访问 Exhentai (表站限制)。

```python
import asyncio
from exhentai_api import ExhentaiAPI, ExhentaiClient

async def main():
    # 方式一：默认初始化 (适用于公开访问)
    api = ExhentaiAPI()

    # 方式二：传入带有凭证的 Client (适用于 ExHentai 或 避免被Ban)
    client = ExhentaiClient(
        igneous="your_igneous_cookie",
        ipb_member_id="your_member_id"
    )
    api = ExhentaiAPI(client=client)

    # ... 执行其他操作

    # 务必在程序结束时关闭资源
    await api.aclose()

# 更好的方式：使用异步上下文管理器 (自动处理资源关闭)
async def main_with_context():
    async with ExhentaiAPI() as api:
        # 获取主页画廊列表
        galleries = await api.get_homepage()
        for gallery in galleries:
            print(f"Title: {gallery.title}")
            print(f"URL: {gallery.url}")

if __name__ == "__main__":
    asyncio.run(main_with_context())
```

### 2. 获取主页画廊列表 (get_homepage)
该方法将访问主页并将 HTML 转换成强类型的 `GalleryListItem` 对象列表。

```python
async with ExhentaiAPI() as api:
    items = await api.get_homepage()
    
    first_item = items[0]
    print(first_item.gid)         # 画廊 ID，例如 "1234567"
    print(first_item.token)       # 画廊 Token，例如 "abcdef1234"
    print(first_item.title)       # 标题
    print(first_item.category)    # 分类，例如 "Doujinshi"
    print(first_item.uploader)    # 上传者
    print(first_item.thumb_url)   # 封面图 URL
    print(first_item.posted)      # 上传时间
```

### 3. 底层机制与错误处理 (Sad Panda)
在 `ExhentaiClient` 的实现中，包含了两项关键的保护机制：
1. **重试逻辑**: 如果因网络波动或服务端短暂异常导致请求失败，系统会自动重试 (`get_html(..., retries=3, backoff_factor=1.0)`)。
2. **Sad Panda 检测**: 访问 ExHentai 需要正确的账号状态和 Cookies。如果没有正确配置或 Cookie 失效，网站可能返回一张哭泣的熊猫图。`client.get_html` 会检查 HTTP Headers 中的 `Content-Disposition`，一旦发现 `inline; filename="sadpanda.jpg"`，将抛出 `RuntimeError("Sad Panda: You do not have permission to view ExHentai.")`，并中断重试。

## 未来待开发项 (Todo)
依据整体重构规划，目前只完成了 `get_homepage`。接下来的开发应继续扩展：
1. **`api.py` 扩展**: 实现 `search()`, `get_gallery_details()`, `get_image_url()`, `get_favorites()`。
2. **`parsers/` 扩展**: 添加 `favorites.py`, `popular.py`, `user.py`, `image.py` 等解析器。
3. 将现有的 `tui.py` 与新的 `exhentai_api` 模块进行对接整合。