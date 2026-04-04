# Exhentai API 使用说明

## 概述

`exhentai_api` 是一个 Python 异步库，提供对 Exhentai/E-Hentai 的完整数据访问能力。底层依赖 `httpx` (异步 HTTP) 和 `BeautifulSoup4` (HTML 解析)。

## 包结构

```
exhentai_api/
├── __init__.py          # 导出: ExhentaiAPI, ExhentaiClient, 17 个模型类
├── api.py               # ExhentaiAPI: 22 个异步方法
├── client.py            # ExhentaiClient: cookies, headers, Sad Panda 检测, 重试
├── constants.py         # BASE_URL, 分类常量
├── utils.py             # extract_gallery_token
├── models/
│   ├── gallery.py       # GalleryListItem, GalleryDetail
│   ├── image.py         # ImageDetail
│   ├── search.py        # SearchParams
│   ├── favorites.py     # FavoriteCategory, FavoritesResponse
│   ├── toplist.py       # TopListItem
│   ├── comment.py       # GalleryComment
│   ├── torrent.py       # TorrentItem
│   ├── archive.py       # ArchiveOption, ArchiverData
│   ├── home.py          # HomeDetail
│   ├── profile.py       # ProfileResult
│   ├── vote.py          # RateResult, VoteCommentResult
│   └── tags.py          # Tag, WatchedTag
└── parsers/
    ├── gallery.py       # 画廊列表解析 (含评分/页数/缩略图尺寸)
    ├── gallery_detail.py # 画廊详情解析 (完整元数据+评论)
    ├── image.py         # 图片查看器 + API 响应解析
    ├── favorites.py     # 收藏列表解析
    ├── toplist.py       # TopList 解析
    ├── comments.py      # 评论解析
    ├── torrent.py       # 种子列表解析
    ├── archive.py       # 归档选项解析
    ├── home.py          # 用户主页解析
    ├── profile.py       # 用户资料解析
    └── mytags.py        # 标签管理解析
```

## 使用示例

### 初始化

```python
import asyncio
from exhentai_api import ExhentaiAPI, ExhentaiClient

async def main():
    # 带凭证初始化 (访问 ExHentai 必须)
    client = ExhentaiClient(
        igneous="your_igneous_cookie",
        ipb_member_id="your_member_id"
    )
    async with ExhentaiAPI(client=client) as api:
        galleries = await api.get_homepage()
        for g in galleries:
            print(f"{g.title} - {g.rating}* - {g.pages}p")

asyncio.run(main())
```

### 搜索

```python
from exhentai_api.models.search import SearchParams

params = SearchParams(keyword="fate", min_rating=4, show_expunged=False)
results = await api.search(params, page=0)
```

### 画廊详情与图片下载

```python
detail = await api.get_gallery_details("12345", "abcdef1234")
print(detail.title, detail.tags, detail.pages)

# 获取第 1 页图片 URL
image = await api.get_image_url("12345", "imgkey", 1)
print(image.image_url)

# 使用 nl token 重载图片
image2 = await api.get_image_url("12345", "imgkey", 1, nl=image.nl)
```

### 收藏管理

```python
# 获取收藏 (支持关键字搜索)
favs = await api.get_favorites(favcat=0, keyword="artist:name", sn=True)
for cat in favs.categories:
    print(f"[{cat.slot}] {cat.name}: {cat.count}")

# 添加收藏
await api.add_favorite("12345", "abcdef", favcat=2, favnote="good")

# 批量操作
await api.modify_favorites(["12345", "67890"], ddact="fav3")
```

### 评论与评分

```python
# 发表评论
comments = await api.comment_gallery("12345", "abcdef", "Great gallery!")

# 评论投票 (api_uid/api_key 来自 GalleryDetail)
result = await api.vote_comment(detail.api_uid, detail.api_key, 12345, "abcdef", 100, vote=1)

# 评分 (2-10 对应 1.0-5.0 星)
rate = await api.rate_gallery(detail.api_uid, detail.api_key, 12345, "abcdef", rating=8)
```

### 种子与归档

```python
torrents = await api.get_torrent_list("12345", "abcdef")
archives = await api.get_archive_list("12345", "abcdef")
download_url = await api.download_archive(archives.original.url, resolution="org")
```

### 用户信息

```python
home = await api.get_home_detail()
print(f"图片配额: {home.image_used}/{home.image_total}")

profile = await api.get_profile()
print(profile.display_name)
```

## 错误处理

### Sad Panda 检测

`ExhentaiClient.get_html` 会检测 HTTP 响应头中的 `Content-Disposition: inline; filename="sadpanda.jpg"`。一旦检测到，立即抛出 `RuntimeError("Sad Panda: You do not have permission to view ExHentai.")`，不再重试。

### 自动重试

所有 HTTP 请求默认重试 3 次，指数退避 (`backoff_factor=0.1`)。适用于 `get_html`、`post_json`、`post_form`。

## 详细 API 文档

完整方法签名和模型字段参见 `docs/api_reference.md`。
