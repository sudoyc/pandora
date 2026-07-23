# EhViewer Android 项目架构详解

> 已归档：本文是参考项目研究报告，不是 Pandora 当前架构。当前文档见
> [`../../architecture/README.md`](../../architecture/README.md)。

> 本文档基于 EhViewer_CN_SXJ 分支，对项目的整体架构、接口设计、数据库设计、前端 UI、下载系统、网络层等进行全面分析。

> 本文保留历史分析原貌；其中代码规模、目录和实现细节不代表当前仓库状态。

---

## 目录

1. [项目概览与代码统计](#1-项目概览与代码统计)
2. [整体架构设计](#2-整体架构设计)
3. [API 客户端层 (client/)](#3-api-客户端层)
4. [数据库与持久化层](#4-数据库与持久化层)
5. [UI 与前端架构](#5-ui-与前端架构)
6. [下载系统与 Spider 管线](#6-下载系统与-spider-管线)
7. [网络层与基础设施](#7-网络层与基础设施)

---

## 1. 项目概览与代码统计

### 1.1 项目简介

EhViewer 是一个功能完整的 E-Hentai / ExHentai 画廊浏览器 Android 客户端，支持画廊搜索、浏览、下载、收藏、评论、评分等全部功能。项目采用 Java/Kotlin 混合开发，并包含大量 C/C++ 原生代码用于图片解码。

### 1.2 代码量统计

| 语言 | 文件数 | 代码行数 | 占比 |
|------|--------|----------|------|
| Java / Kotlin | ~555 | ~120,000 | 27% |
| C / C++ (原生代码) | ~568 | ~295,000 | 66% |
| XML (布局/资源) | - | ~30,000 | 7% |
| **总计** | - | **~445,000** | 100% |

### 1.3 Java/Kotlin 代码分布

| 模块 | 行数 | 说明 |
|------|------|------|
| `ehviewer/` | ~61,000 | 核心业务逻辑 (API、UI、下载、数据库) |
| `lib/` | ~24,000 | 自研框架 (OpenGL 画廊渲染、工具集 yorozuya) |
| `widget/` | ~9,000 | 自定义 Android 控件 |
| 其他工具包 | ~18,000 | 缓存、网络、IO、数据库等基础设施 |
| 测试 + 生成器 | ~8,000 | 单元测试和 DAO 代码生成器 |

### 1.4 原生代码分布

| 库 | 行数 (约) | 来源 | 用途 |
|----|----------|------|------|
| libwebp | ~130,000 | Google (第三方) | WebP 图片编解码 |
| libjpeg-turbo | ~90,000 | libjpeg-turbo (第三方) | JPEG 高性能编解码 |
| libpng | ~50,000 | libpng (第三方) | PNG 解码 |
| giflib | ~16,000 | giflib (第三方) | GIF 解码 |
| 自定义 JNI 桥接 | ~4,400 | 项目自研 | 连接 Java 层与原生库 |

> **关键结论**：项目看似 44.5 万行，但 290K 行是打包的第三方 C 图片库源码。真正的核心业务代码约 **6.1 万行** (Java/Kotlin `ehviewer/` 包)。

### 1.5 顶层目录结构

```
reference_project/
├── app/                        # Android 应用主模块
│   └── src/main/
│       ├── java/com/hippo/     # Java/Kotlin 源码
│       │   ├── ehviewer/       # ★ 核心业务代码 (~61K 行)
│       │   ├── lib/            # 自研框架库 (~24K 行)
│       │   ├── widget/         # 自定义控件 (~9K 行)
│       │   └── (其他工具包)     # 基础设施 (~18K 行)
│       ├── cpp/                # C/C++ 原生代码 (~295K 行)
│       │   ├── jni/            # 第三方图片库 (~290K 行)
│       │   ├── gif/            # GIF JNI 桥接
│       │   └── image/          # 图片处理 JNI 桥接
│       └── res/                # Android 资源文件
├── daogenerator/               # GreenDAO 代码生成器
├── art/                        # 应用图标等美术资源
├── fastlane/                   # 发布自动化
└── build.gradle                # Gradle 构建配置
```

---

## 2. 整体架构设计

### 2.1 分层架构总览

EhViewer 采用经典的 Android 分层架构，自上而下分为 **UI 层**、**业务逻辑层**、**数据层** 和 **基础设施层**：

```
┌─────────────────────────────────────────────────────────────────┐
│                        UI 层 (展示)                              │
│  ┌───────────────┐  ┌──────────────┐  ┌───────────────────────┐ │
│  │  Scene/Fragment│  │ GalleryView  │  │   自定义 Widget       │ │
│  │  (场景导航)    │  │ (OpenGL渲染) │  │   (widget/ 包)        │ │
│  └───────┬───────┘  └──────┬───────┘  └───────────┬───────────┘ │
├──────────┼─────────────────┼──────────────────────┼─────────────┤
│          ▼                 ▼                      ▼              │
│                      业务逻辑层 (核心)                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ EhClient     │  │DownloadMgr  │  │ GalleryProvider      │   │
│  │ EhEngine     │  │SpiderQueen  │  │ (Eh/Archive/Dir)     │   │
│  │ (API 调用)   │  │(下载管线)    │  │ (画廊数据源)          │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘   │
├─────────┼─────────────────┼──────────────────────┼──────────────┤
│         ▼                 ▼                      ▼               │
│                        数据层 (持久化)                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ EhDB         │  │ Settings     │  │ SpiderDen            │   │
│  │ GreenDAO     │  │ SharedPrefs  │  │ (文件存储)            │   │
│  │ (SQLite)     │  │ (配置)       │  │                      │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘   │
├─────────┼─────────────────┼──────────────────────┼──────────────┤
│         ▼                 ▼                      ▼               │
│                      基础设施层 (通用)                            │
│  ┌──────────┐ ┌──────────┐ ┌─────────┐ ┌──────────┐ ┌────────┐ │
│  │ OkHttp   │ │BeerBelly │ │ Conaco  │ │ UniFile  │ │ Native │ │
│  │ Network  │ │(磁盘缓存) │ │(图片加载)│ │(文件抽象) │ │(C图片库)│ │
│  └──────────┘ └──────────┘ └─────────┘ └──────────┘ └────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 核心包结构 (`com.hippo.ehviewer`)

```
ehviewer/
├── client/                 # E-Hentai API 客户端 (★ 网络接口层)
│   ├── data/               #   数据模型 (GalleryInfo, GalleryDetail 等)
│   ├── parser/             #   HTML/JSON 解析器 (22 个)
│   └── exception/          #   自定义异常 (9 种)
├── ui/                     # UI 界面 (★ 展示层)
│   ├── scene/              #   各功能场景 (15+ 个 Scene)
│   ├── dialog/             #   对话框
│   ├── fragment/           #   Fragment
│   └── annotation/         #   UI 注解
├── dao/                    # 数据访问对象 (★ 数据库层)
│   ├── DaoMaster.java      #   GreenDAO 主控
│   ├── DaoSession.java     #   会话管理
│   └── (各表 DAO)          #   10 张表的 DAO 类
├── download/               # 下载管理 (★ 下载系统)
│   ├── DownloadManager.java
│   └── DownloadService.kt
├── spider/                 # 图片抓取管线 (★ 核心下载引擎)
│   ├── SpiderQueen.java    #   多线程图片抓取
│   ├── SpiderInfo.java     #   元数据持久化
│   └── SpiderDen.java      #   磁盘存储管理
├── gallery/                # 画廊数据提供者
│   ├── EhGalleryProvider.java     # 在线画廊
│   ├── ArchiveGalleryProvider.java # 压缩包画廊
│   └── DirGalleryProvider.java    # 本地文件夹画廊
├── preference/             # 设置界面
├── widget/                 # 应用专用控件
├── sync/                   # 数据同步
├── event/                  # EventBus 事件
├── EhApplication.java      # Application 入口
├── EhDB.java               # 数据库门面类
└── Settings.java           # 全局配置管理
```

### 2.3 基础设施包结构 (`com.hippo.*`)

| 包名 | 文件数 | 职责 |
|------|--------|------|
| `lib/glview/` | ~65 | 自研 OpenGL 渲染框架 (GLView, GLCanvas, GLTexture 等) |
| `lib/glgallery/` | 9 | 基于 GLView 的画廊浏览组件 |
| `lib/yorozuya/` | ~50 | 通用工具集 (集合、动画、数学、线程、资源) |
| `lib/image/` | 5 | JNI 图片解码封装 |
| `widget/` | 38 | 通用自定义 Android 控件 |
| `network/` | 11 | 网络工具 (Cookie、SSL/TLS、DNS) |
| `beerbelly/` | 5 | 两级缓存框架 (内存 LRU + 磁盘 LRU) |
| `conaco/` | 8 | 异步资源加载与缓存 |
| `unifile/` | 16 | 统一文件抽象层 (兼容 SAF/MediaStore) |
| `util/` | 28 | 通用工具 (权限、模糊、排序等) |
| `scene/` | 6 | Scene/Fragment 导航框架 |
| `database/` | 2 | SQLite 辅助工具 |
| `drawable/` | 10 | 自定义 Drawable |
| `io/` | 4 | 流管道工具 |
| `preference/` | 7 | 自定义 Preference 控件 |
| `reveal/` | 4 | 揭示动画库 |
| `text/` | 3 | 文本处理 (HTML、链接) |
| `content/` | 3 | ContentProvider 封装 |
| `app/` | 4 | Dialog 辅助类 |

### 2.4 核心依赖关系

```
EhApplication (入口)
  ├── EhClient / EhEngine         ← OkHttp, EhCookieStore, EhHosts
  │     └── Parser (22个)         ← Jsoup, org.json
  │           └── Data Models     ← GalleryInfo, GalleryDetail, ...
  │
  ├── DownloadManager             ← SpiderQueen, EhDB, EventBus
  │     └── SpiderQueen           ← EhEngine, SpiderDen, SpiderInfo
  │           └── SpiderDen       ← UniFile, SimpleDiskCache
  │
  ├── EhDB                        ← GreenDAO (DaoMaster/DaoSession)
  │     └── 10 个 DAO 类
  │
  ├── GalleryProvider             ← SpiderQueen / Archive / Directory
  │     └── GalleryView           ← GLView (OpenGL 渲染)
  │
  └── Settings                    ← SharedPreferences
```

### 2.5 第三方依赖 (Gradle)

| 依赖 | 版本 | 用途 |
|------|------|------|
| OkHttp | 3.14.7 | HTTP 客户端 |
| GreenDAO | 3.0.0 | ORM 数据库框架 |
| Jsoup | 1.18.1 | HTML 解析 |
| TagSoup | 1.2.1 | 容错 HTML 解析 |
| Conscrypt | 2.5.3 | 现代 SSL/TLS 提供者 |
| EventBus | 3.3.1 | 事件总线 |
| AndroidX AppCompat | - | 兼容库 |
| Material Design | - | 界面组件 |

---

## 3. API 客户端层

API 客户端是应用与 E-Hentai 服务器交互的核心层，位于 `com.hippo.ehviewer.client/`，共约 69 个 Java 文件。

### 3.1 核心类职责

| 类 | 文件 | 行数 | 职责 |
|----|------|------|------|
| `EhEngine` | `EhEngine.java` | ~1,418 | API 调度中心，包含所有 30+ 个公开静态方法 |
| `EhClient` | `EhClient.java` | ~251 | AsyncTask 异步请求分发器，封装线程池 |
| `EhRequest` | `EhRequest.java` | ~82 | 流式请求构建器 |
| `EhRequestBuilder` | `EhRequestBuilder.java` | ~54 | OkHttp Request 构建，自动加 Chrome UA |
| `EhUrl` | `EhUrl.java` | ~321 | URL 常量与端点定义 |
| `EhCookieStore` | `EhCookieStore.java` | ~114 | Cookie 持久化与认证管理 |
| `EhHosts` | `EhHosts.java` | ~173 | DNS 硬编码 IP (绕过 DNS 污染) |
| `EhConfig` | `EhConfig.java` | ~800+ | 用户偏好设置 (存储在 Cookie 中) |
| `EhCacheKeyFactory` | `EhCacheKeyFactory.java` | ~41 | 缓存键生成工具 |

### 3.2 请求调用链

```
用户操作 (UI 层)
  → EhClient.execute(EhRequest)
    → EhClient.Task.executeOnExecutor(线程池, 参数)
      → Task.doInBackground()
        → switch(METHOD 常量)
          → EhEngine.静态方法(Task, OkHttpClient, 参数)
            → 构建 HTTP 请求 (EhRequestBuilder)
            → OkHttp 发送请求
            → Parser 解析响应 (HTML/JSON)
            → 返回数据模型
      → Task.onPostExecute()
        → Callback.onSuccess(结果) 或 Callback.onFailure(异常)
```

### 3.3 URL 端点定义

**主域名**：

| 域名 | 用途 |
|------|------|
| `e-hentai.org` | 公开站 |
| `exhentai.org` | 会员站 (需 igneous Cookie) |
| `forums.e-hentai.org` | 论坛 (登录、个人资料) |
| `upld.e-hentai.org` | 图片反向搜索上传 |

**核心端点**：

| 端点 | URL 模式 | 方法 | 用途 |
|------|----------|------|------|
| 登录 | `forums.e-hentai.org/index.php?act=Login&CODE=01` | POST | 用户认证 |
| JSON API | `{domain}/api.php` | POST | 画廊元数据、评分、Token |
| 画廊列表 | `{domain}/` | GET | 搜索结果页 (HTML) |
| 画廊详情 | `{domain}/g/{gid}/{token}/` | GET | 画廊详情页 (HTML) |
| 图片页 | `{domain}/s/{pToken}/{gid}-{index}` | GET | 单张图片页 (HTML) |
| 收藏夹 | `{domain}/favorites.php` | GET/POST | 收藏管理 |
| 用户主页 | `{domain}/home.php` | GET | 配额信息 |
| 个人资料 | `forums.e-hentai.org/index.php?showuser={uid}` | GET | 用户信息 |
| 用户标签 | `{domain}/mytags` | GET | 关注/屏蔽标签 |
| 排行榜 | `e-hentai.org/toplist.php` | GET | 画廊排名 |
| 图片搜索 | `upld.e-hentai.org/image_lookup.php` | POST | 以图搜图 |

### 3.4 EhEngine 公开接口一览

#### 3.4.1 认证与会话

```java
// 登录
static String signIn(Task, OkHttpClient, String username, String password)
// 返回：用户名
// 表单：UserName, PassWord, submit, CookieDate, temporary_https
```

#### 3.4.2 画廊搜索与列表

```java
// 获取画廊列表 (搜索/首页/标签/上传者)
static GalleryListParser.Result getGalleryList(Task, OkHttpClient, String url, int mode)
// 返回：pages, nextPage, galleryInfoList, 分页链接 (first/prev/next/last)

// 用 JSON API 补充画廊列表信息 (标签、页数、评分)
static List<GalleryInfo> fillGalleryListByApi(Task, OkHttpClient, List<GalleryInfo>, String url)
// 端点：POST api.php  载荷：{"method":"gmetadata","gidlist":[[gid,token],...]}
```

#### 3.4.3 画廊详情

```java
// 获取画廊完整详情
static GalleryDetail getGalleryDetail(Task, OkHttpClient, String url)
// 返回：标签、评论、预览、归档信息、评分等

// 获取预览缩略图集
static Pair<PreviewSet, Integer> getPreviewSet(Task, OkHttpClient, String url)
// 返回：PreviewSet (NORMAL 或 LARGE) 和预览页数
```

#### 3.4.4 图片访问

```java
// 解析 HTML 图片页，获取图片 URL
static GalleryPageParser.Result getGalleryPage(Task, OkHttpClient, String url)
// 返回：imageUrl, skipHathKey, originImageUrl, showKey

// 通过 JSON API 获取图片 URL
static GalleryPageApiParser.Result getGalleryPageApi(Task, OkHttpClient, String url)
// 端点：POST api.php
// 返回：imageUrl, skipHathKey, otherImageUrl, originImageUrl

// 获取画廊 Token
static String getGalleryToken(Task, OkHttpClient, long gid, String pageToken, int pageNumber)
// 端点：POST api.php  载荷：{"method":"gtoken","pagelist":[[gid,pagetoken],...]}
```

#### 3.4.5 评分与评论

```java
// 评分 (2-10)
static RateGalleryParser.Result rateGallery(Task, OkHttpClient, long gid, String token,
    long apiuid, String apikey, float rating)

// 发表/编辑评论
static GalleryCommentList commentGallery(Task, OkHttpClient, String url,
    String comment, String commentVote)

// 评论投票
static VoteCommentParser.Result voteComment(Task, OkHttpClient, long gid, String token,
    long commentId, int commentVote, long apiuid, String apikey)
```

#### 3.4.6 收藏管理

```java
// 获取收藏列表 (10 个分类)
static FavoritesParser.Result getFavorites(Task, OkHttpClient, String url, boolean filter)
// 返回：catArray(10个分类名), countArray(各分类数量), galleryInfoList, 分页

// 添加到收藏
static void addFavorites(Task, OkHttpClient, long gid, String token,
    int slot, String favoriteName)

// 批量添加到收藏
static void addFavoritesRange(Task, OkHttpClient, long[] gids, String[] tokens, int slot)

// 移动/删除收藏
static FavoritesParser.Result modifyFavorites(Task, OkHttpClient, String url,
    long[] gids, int slot, boolean delete)
```

#### 3.4.7 种子与归档

```java
// 获取种子列表
static Pair<String, String>[] getTorrentList(Task, OkHttpClient, String url,
    long gid, String token)
// 返回：[url, name] 数组

// 获取归档下载选项
static Pair<String, Pair<String, String>[]> getArchiveList(Task, OkHttpClient, String url,
    long gid, String token)
// 返回：paramOr + [resolution, name] 数组

// 获取 H@H 归档价格信息
static ArchiverData getArchiver(Task, OkHttpClient, String url, long gid, String token)

// 触发归档下载
static void downloadArchive(Task, OkHttpClient, long gid, String token,
    String or, String archiveType)
```

#### 3.4.8 用户资料与标签

```java
// 用户资料
static ProfileParser.Result getProfile(Task, OkHttpClient)

// 用户主页 (配额)
static HomeDetail getHomeDetail(Task, OkHttpClient)
// 返回：imageLimit(已用/总量), GP 收益, 审核能力

// 重置图片查看限额 (消耗 GP)
static HomeDetail resetLimit(Task, OkHttpClient)

// 获取用户关注标签
static UserTagList getWatchedList(Task, OkHttpClient, String url)

// 添加/删除/编辑关注标签
static UserTagList addTag(Task, OkHttpClient, String url, TagPushParam)
static UserTagList deleteWatchedTag(Task, OkHttpClient, String url, UserTag)
static Response editWatchedTag(...)
```

#### 3.4.9 搜索与排行榜

```java
// 反向图片搜索
static GalleryListParser.Result imageSearch(Task, OkHttpClient, File imageFile,
    boolean similarityScan, boolean coverOnly, boolean expunged)
// 端点：POST multipart 到 upld.e-hentai.org/image_lookup.php

// 排行榜
static EhTopListDetail getTopList(Task, OkHttpClient, String url)
// 返回：Gallery/Uploader/Tagging/HentaiHome/EHTracker/Cleanup/Rating 各榜

// 新闻
static EhNewsDetail getEhNews(Task, OkHttpClient)
```

### 3.5 解析器 (Parser) 详细列表

共 22 个解析器，位于 `client/parser/`：

| 解析器 | 输入 | 输出 | 解析方式 |
|--------|------|------|----------|
| `GalleryListParser` | 搜索结果 HTML | `Result{pages, galleryInfoList, 分页链接}` | Jsoup + Regex |
| `GalleryDetailParser` | 画廊详情 HTML | `GalleryDetail` | Jsoup + Regex + JS变量提取 |
| `GalleryApiParser` | JSON API 响应 | `List<GalleryApiInfo>` | org.json |
| `GalleryPageParser` | 图片页 HTML | `Result{imageUrl, skipHathKey, showKey}` | Regex |
| `GalleryPageApiParser` | JSON API 响应 | `Result{imageUrl, skipHathKey}` | org.json |
| `GalleryTokenApiParser` | JSON API 响应 | `String token` | org.json |
| `SignInParser` | 登录响应 HTML | `String username` | Jsoup |
| `FavoritesParser` | 收藏页 HTML | `Result{catArray, countArray, galleryInfoList}` | Jsoup |
| `TorrentParser` | 种子弹窗 HTML | `Pair<String,String>[]` | Regex |
| `ArchiveParser` | 归档弹窗 HTML | 归档选项列表 | Regex |
| `RateGalleryParser` | 评分 JSON | `Result{rating, ratingCount}` | org.json |
| `VoteCommentParser` | 投票 JSON | `Result{score, expectVote}` | org.json |
| `TopListParser` | 排行榜 HTML | `EhTopListDetail` | Jsoup |
| `ProfileParser` | 个人资料 HTML | `Result{displayName, avatar}` | Jsoup |
| `EhHomeParser` | 主页 HTML | `HomeDetail` | Regex |
| `EhEventParse` | 事件 HTML | 事件数据 | Jsoup |
| `MyTagLitParser` | 标签页 HTML | `UserTagList` | Jsoup |
| `ForumsParser` | 论坛 HTML | 论坛数据 | Jsoup |
| `GalleryListUrlParser` | URL 字符串 | 搜索参数 | URL 解析 |
| `GalleryDetailUrlParser` | URL 字符串 | `{gid, token}` | Regex |
| `GalleryPageUrlParser` | URL 字符串 | `{gid, pToken, page}` | Regex |
| `ParserUtils` | - | - | 共享工具方法 |

### 3.6 数据模型 (Data)

位于 `client/data/`，共约 20 个模型类：

| 模型类 | 用途 | 关键字段 |
|--------|------|----------|
| `GalleryInfo` | 画廊基础信息 (列表项) | gid, token, title, titleJpn, thumb, category, posted, uploader, rating, simpleLanguage, pages, thumbWidth, thumbHeight, favoriteSlot, favoriteName |
| `GalleryDetail` | 画廊完整详情 (extends GalleryInfo) | apiUid, apiKey, torrentCount, torrentUrl, archiveUrl, parent, visible, language, size, favoriteCount, ratingCount, tags(TagGroup[]), comments, previewPages, previewSet |
| `GalleryApiInfo` | JSON API 补充信息 | 同 GalleryInfo 但来自 JSON |
| `GalleryTagGroup` | 标签分组 | groupName (namespace), tagList |
| `GalleryComment` | 评论 | id, score, editable, voteUpAble, voteDownAble, uploader, comment, time, lastEdited |
| `GalleryCommentList` | 评论列表 | comments[], hasMore |
| `PreviewSet` | 预览集 (抽象基类) | 各预览图 URL + 位置信息 |
| `NormalPreviewSet` | 标准预览集 | 雪碧图裁切参数 (offsetX, offsetY, clipWidth, clipHeight) |
| `LargePreviewSet` | 大图预览集 | 独立图片 URL |
| `ListUrlBuilder` | 搜索 URL 构建器 | mode, category, keyword, advanceSearch, minRating, pageFrom, pageTo |
| `FavListUrlBuilder` | 收藏 URL 构建器 | favCat, keyword |
| `ArchiverData` | 归档信息 | funds, originalCost, resampleCost, originalSize, resampleSize |
| `HomeDetail` | 用户主页信息 | currentLimit, maximumLimit, resetCost |
| `EhTopListDetail` | 排行榜 | 7 个子榜单列表 |
| `Tag` / `UserTag` | 标签 | tagId, title, state, color |
| `NewVersion` | 画廊版本 | gid, token |

### 3.7 搜索模式 (ListUrlBuilder)

`ListUrlBuilder` 支持 8 种搜索模式：

| 模式 | 常量 | URL 特征 | 用途 |
|------|------|----------|------|
| `MODE_NORMAL` | 0 | `/` + 参数 | 普通关键词搜索 |
| `MODE_UPLOADER` | 1 | `uploader:xxx` | 按上传者搜索 |
| `MODE_TAG` | 2 | `tag:xxx` | 按标签搜索 |
| `MODE_WHATS_HOT` | 3 | `/popular` | 热门画廊 |
| `MODE_IMAGE_SEARCH` | 4 | multipart POST | 以图搜图 |
| `MODE_SUBSCRIPTION` | 5 | `/watched` | 关注订阅 |
| `MODE_FILTER` | 6 | 过滤器 | 本地过滤 |
| `MODE_TOPLIST` | 7 | `/toplist.php` | 排行榜 |

### 3.8 认证机制

**Cookie 认证**：

| Cookie | 用途 | 必须 |
|--------|------|------|
| `ipb_member_id` | 用户 ID | 登录后获得 |
| `ipb_pass_hash` | 密码哈希 | 登录后获得 |
| `igneous` | ExHentai 访问凭证 | 访问 exhentai.org 必须 |
| `nw=1` | 隐藏内容警告横幅 | 自动注入 |

**认证流程**：

```
1. POST 用户名/密码 → forums.e-hentai.org 登录接口
2. 服务器返回 Set-Cookie: ipb_member_id, ipb_pass_hash
3. Cookie 自动持久化到 SQLite (okhttp3-cookie.db)
4. 后续请求由 OkHttp CookieJar 自动附带 Cookie
5. ExHentai 需要额外的 igneous Cookie (需论坛会员资格)
```

**验证方法**：

```java
EhCookieStore.hasSignedIn()
// → true 当 ipb_member_id AND ipb_pass_hash 均存在
```

### 3.9 异常体系

9 种自定义异常，位于 `client/exception/`：

| 异常类 | 含义 | 触发条件 |
|--------|------|----------|
| `EhException` | 基础异常 | 各种错误 |
| `ParseException` | 解析失败 | HTML 结构变化 / 空响应 |
| `CancelledException` | 请求取消 | 用户取消或 Task.stop() |
| `GalleryUnavailableException` | 画廊不可用 | 画廊被删除 |
| `OffensiveException` | 攻击性内容 | 内容需确认 |
| `PiningException` | 画廊已消亡 | "pining for the fjords" |
| `NoHAtHClientException` | 缺少 H@H | 需要 Hentai@Home 客户端 |
| `Image509Exception` | 图片暂不可用 | 流量限制 (HTTP 509) |
| `EmptyGalleryException` | 空画廊 | 画廊无图片 |

**特殊检测**：

```
Sad Panda 检测：响应 Content-Disposition 包含 "sadpanda.jpg"
  → 表示认证失败或内容不可访问

Kokomade 检测：响应体包含 "kokomade.jpg"
  → 表示画廊已永久删除
```

### 3.10 EhClient 方法常量

`EhClient` 使用整数常量映射到 `EhEngine` 的各个方法：

```java
METHOD_SIGN_IN                = 0
METHOD_GET_GALLERY_LIST       = 1
METHOD_GET_GALLERY_DETAIL     = 3
METHOD_GET_PREVIEW_SET        = 4
METHOD_GET_RATE_GALLERY       = 5
METHOD_GET_COMMENT_GALLERY    = 6
METHOD_GET_GALLERY_TOKEN      = 7
METHOD_GET_FAVORITES          = 8
METHOD_ADD_FAVORITES          = 9
METHOD_MODIFY_FAVORITES       = 11
METHOD_GET_TORRENT_LIST       = 12
METHOD_GET_TOP_LIST           = 13
METHOD_GET_PROFILE            = 14
METHOD_VOTE_COMMENT           = 15
METHOD_IMAGE_SEARCH           = 16
METHOD_ARCHIVE_LIST           = 17
METHOD_DOWNLOAD_ARCHIVE       = 18
METHOD_ADD_TAG                = 20
METHOD_EDIT_WATCHED           = 21
METHOD_DELETE_WATCHED         = 22
METHOD_GET_WATCHED            = 23
METHOD_GET_NEWS               = 24
METHOD_GET_HOME               = 25
METHOD_RESET_LIMIT            = 26
```

### 3.11 缓存键设计

`EhCacheKeyFactory` 生成的缓存键格式：

| 方法 | 键格式 | 用途 |
|------|--------|------|
| `getThumbKey(gid)` | `preview:large:{gid}:0` | 封面缩略图 |
| `getNormalPreviewKey(gid, index)` | `preview:normal:{gid}:{index}` | 标准预览图 |
| `getLargePreviewKey(gid, index)` | `preview:large:{gid}:{index}` | 大预览图 |
| `getLargePreviewSetKey(gid, index)` | `large_preview_set:{gid}:{index}` | 大预览集合 |
| `getImageKey(gid, index)` | `image:{gid}:{index}` | 完整图片 |

---

## 4. 数据库与持久化层

### 4.1 ORM 框架

项目使用 **GreenDAO 3.x** 作为 ORM 框架，通过 `daogenerator/` 下的代码生成器生成 DAO 类。

- 数据库文件：`eh.db`
- Schema 版本：7 (经历 6 次迁移)
- 核心类：`EhDB.java` (数据库门面)、`DaoMaster.java`、`DaoSession.java`
- 所有公开方法均使用 `synchronized` 保证线程安全

### 4.2 表结构设计 (10 张表)

#### 4.2.1 DOWNLOADS (下载记录表)

**主键**：`gid` (long, NOT NULL)

| 列名 | 类型 | 可空 | 说明 |
|------|------|------|------|
| GID | INTEGER | NO | 画廊 ID (主键) |
| TOKEN | TEXT | YES | 画廊 Token |
| TITLE | TEXT | YES | 英文标题 |
| TITLE_JPN | TEXT | YES | 日文标题 |
| THUMB | TEXT | YES | 缩略图 URL |
| CATEGORY | INTEGER | NO | 分类 |
| POSTED | TEXT | YES | 发布时间 |
| UPLOADER | TEXT | YES | 上传者 |
| RATING | REAL | NO | 评分 |
| SIMPLE_LANGUAGE | TEXT | YES | 语言 |
| STATE | INTEGER | NO | 下载状态 |
| LEGACY | INTEGER | NO | 遗留标记 |
| TIME | INTEGER | NO | 下载时间 |
| LABEL | TEXT | YES | 下载标签分组 |
| ARCHIVE_URI | TEXT | YES | 导入归档的 URI (v7 新增) |

**下载状态枚举**：

```java
STATE_INVALID  = -1   // 无效
STATE_NONE     = 0    // 初始
STATE_WAIT     = 1    // 等待中
STATE_DOWNLOAD = 2    // 下载中
STATE_FINISH   = 3    // 已完成
STATE_FAILED   = 4    // 失败
STATE_UPDATE   = 5    // 更新中
GOTO_NEW       = 6    // 跳转新版
```

**运行时附加字段** (不持久化)：

```java
speed: long         // 下载速度
remaining: long     // 剩余字节
finished: int       // 已完成页数
downloaded: int     // 已下载字节
total: int          // 总页数
fileSize: long      // 文件夹总大小
```

#### 4.2.2 HISTORY (浏览历史表)

**主键**：`gid` (long, NOT NULL) | **最大记录数**：100 条 (可配置)

| 列名 | 类型 | 可空 | 说明 |
|------|------|------|------|
| GID | INTEGER | NO | 画廊 ID (主键) |
| TOKEN | TEXT | YES | 画廊 Token |
| TITLE | TEXT | YES | 英文标题 |
| TITLE_JPN | TEXT | YES | 日文标题 |
| THUMB | TEXT | YES | 缩略图 URL |
| CATEGORY | INTEGER | NO | 分类 |
| POSTED | TEXT | YES | 发布时间 |
| UPLOADER | TEXT | YES | 上传者 |
| RATING | REAL | NO | 评分 |
| SIMPLE_LANGUAGE | TEXT | YES | 语言 |
| MODE | INTEGER | NO | 浏览模式 |
| TIME | INTEGER | NO | 浏览时间 |

#### 4.2.3 LOCAL_FAVORITES (本地收藏表)

**主键**：`gid` (long, NOT NULL)

与 HISTORY 结构相似，存储本地收藏的画廊信息，字段包括 GID、TOKEN、TITLE、TITLE_JPN、THUMB、CATEGORY、POSTED、UPLOADER、RATING、SIMPLE_LANGUAGE、TIME。

#### 4.2.4 BOOKMARKS (书签表)

**主键**：`gid` (long, NOT NULL)

在 LOCAL_FAVORITES 基础上增加：

| 列名 | 类型 | 说明 |
|------|------|------|
| PAGE | INTEGER | 书签标记页码 |
| TIME | INTEGER | 书签时间 |

#### 4.2.5 QUICK_SEARCH (快速搜索表)

**主键**：`_id` (Long, 自增)

| 列名 | 类型 | 说明 |
|------|------|------|
| _id | INTEGER | 自增主键 |
| NAME | TEXT | 搜索名称 |
| MODE | INTEGER | 搜索模式 |
| CATEGORY | INTEGER | 分类过滤 |
| KEYWORD | TEXT | 关键词 |
| ADVANCE_SEARCH | INTEGER | 高级搜索标记 |
| MIN_RATING | INTEGER | 最低评分 |
| PAGE_FROM | INTEGER | 起始页 (v4 新增) |
| PAGE_TO | INTEGER | 结束页 (v4 新增) |
| TIME | INTEGER | 创建时间 |

#### 4.2.6 DOWNLOAD_LABELS (下载标签表)

**主键**：`_id` (Long, 自增)

| 列名 | 类型 | 说明 |
|------|------|------|
| _id | INTEGER | 自增主键 |
| LABEL | TEXT | 标签名称 |
| TIME | INTEGER | 创建时间 |

#### 4.2.7 DOWNLOAD_DIRNAME (下载目录名映射表)

**主键**：`gid` (long, NOT NULL)

| 列名 | 类型 | 说明 |
|------|------|------|
| GID | INTEGER | 画廊 ID (主键) |
| DIRNAME | TEXT | 目录名 |

#### 4.2.8 FILTER (过滤规则表)

**主键**：`_id` (Long)

| 列名 | 类型 | 说明 |
|------|------|------|
| _id | INTEGER | 主键 |
| MODE | INTEGER | 过滤模式 (标题/上传者/标签/标签命名空间) |
| TEXT | TEXT | 过滤文本 |
| ENABLE | INTEGER | 是否启用 (v3 新增) |

#### 4.2.9 Black_List (黑名单表)

**主键**：`_id` (Long, 自增) | **索引**：`BADGAYNAME`

| 列名 | 类型 | 可空 | 说明 |
|------|------|------|------|
| _id | INTEGER | NO | 自增主键 |
| BADGAYNAME | TEXT | NO | 被拉黑用户名 (有索引) |
| REASON | TEXT | YES | 原因 |
| ANGRYWITH | TEXT | YES | 关联画廊 |
| ADD_TIME | TEXT | YES | 添加时间 |
| MODE | INTEGER | YES | 模式 |

#### 4.2.10 Gallery_Tags (画廊标签缓存表)

**主键**：`gid` (long, NOT NULL)

| 列名 | 类型 | 说明 |
|------|------|------|
| GID | INTEGER | 画廊 ID (主键) |
| ROWS | TEXT | 行标签 |
| ARTIST | TEXT | 艺术家 |
| COSPLAYER | TEXT | Cosplayer |
| CHARACTER | TEXT | 角色 |
| FEMALE | TEXT | 女性标签 |
| GROUP | TEXT | 社团 |
| LANGUAGE | TEXT | 语言 |
| MALE | TEXT | 男性标签 |
| MISC | TEXT | 杂项 |
| MIXED | TEXT | 混合 |
| OTHER | TEXT | 其他 |
| PARODY | TEXT | 原作 |
| RECLASS | TEXT | 重分类 |
| CREATE_TIME | INTEGER | 创建时间 |
| UPDATE_TIME | INTEGER | 更新时间 |

### 4.3 数据库迁移历史

| 版本 | 变更 |
|------|------|
| v2 → v3 | FILTER 表新增 `ENABLE` 列 |
| v3 → v4 | QUICK_SEARCH 表新增 `PAGE_FROM`、`PAGE_TO` 列 |
| v4 → v5 | 重建 Black_List 表 |
| v5 → v6 | 重建 Gallery_Tags 表 |
| v6 → v7 | DOWNLOADS 表新增 `ARCHIVE_URI` 列 |

### 4.4 EhDB 公开接口

`EhDB.java` 作为数据库的门面类 (Facade)，封装所有 DAO 操作。所有方法均为 `public static synchronized`。

#### 下载管理

```java
List<DownloadInfo> getAllDownloadInfo()              // 获取全部下载 (按时间降序)
void putDownloadInfo(DownloadInfo)                   // 插入或更新下载记录
void removeDownloadInfo(long gid)                    // 删除下载记录
void moveDownloadInfo(List, int from, int to)        // 移动排序位置
```

#### 下载目录映射

```java
String getDownloadDirname(long gid)                  // 获取下载目录名
void putDownloadDirname(long gid, String dirname)    // 设置目录名
void removeDownloadDirname(long gid)                 // 删除映射
void updateDownloadDirname(long removeGid, long newGid, String dirname) // 更新映射
void clearDownloadDirname()                          // 清空全部
```

#### 下载标签

```java
List<DownloadLabel> getAllDownloadLabelList()         // 获取全部标签
DownloadLabel addDownloadLabel(String label)          // 添加标签
void updateDownloadLabel(DownloadLabel)               // 更新标签
void moveDownloadLabel(int from, int to)              // 移动排序
void removeDownloadLabel(DownloadLabel)               // 删除标签
```

#### 本地收藏

```java
List<GalleryInfo> getAllLocalFavorites()              // 获取全部本地收藏
List<GalleryInfo> searchLocalFavorites(String query)  // 按标题搜索
GalleryInfo searchLocalFavorites(long gid)            // 按 GID 搜索
boolean containLocalFavorites(long gid)               // 检查是否已收藏
void putLocalFavorite(GalleryInfo)                    // 添加收藏
void putLocalFavorites(List<GalleryInfo>)             // 批量添加
void removeLocalFavorites(long gid)                   // 删除收藏
void removeLocalFavorites(long[] gidArray)            // 批量删除
```

#### 浏览历史

```java
LazyList<HistoryInfo> getHistoryLazyList()           // 懒加载历史列表
void putHistoryInfo(GalleryInfo)                     // 添加历史记录
void putHistoryInfo(List<HistoryInfo>)               // 批量添加
void deleteHistoryInfo(HistoryInfo)                  // 删除记录
void clearHistoryInfo()                              // 清空历史
```

#### 快速搜索

```java
List<QuickSearch> getAllQuickSearch()                 // 获取全部快速搜索
void insertQuickSearch(QuickSearch)                   // 插入
void updateQuickSearch(QuickSearch)                   // 更新
void deleteQuickSearch(QuickSearch)                   // 删除
void moveQuickSearch(int from, int to)                // 移动排序
```

#### 黑名单

```java
List<BlackList> getAllBlackList()                     // 获取全部黑名单
boolean inBlackList(String name)                      // 检查是否在黑名单
void insertBlackList(BlackList)                       // 添加
void updateBlackList(BlackList)                       // 更新
void deleteBlackList(BlackList)                       // 删除
```

#### 画廊标签缓存

```java
List<GalleryTags> getAllGalleryTags()                 // 获取全部
boolean inGalleryTags(long gid)                       // 检查是否已缓存
GalleryTags queryGalleryTags(long gid)                // 按 GID 查询
void insertGalleryTags(GalleryTags)                   // 插入
void updateGalleryTags(GalleryTags)                   // 更新
void deleteGalleryTags(GalleryTags)                   // 删除
```

#### 过滤规则

```java
List<Filter> getAllFilter()                           // 获取全部过滤规则
void addFilter(Filter)                                // 添加规则
void deleteFilter(Filter)                             // 删除规则
void triggerFilter(Filter)                            // 切换启用/禁用
```

#### 数据导入导出

```java
boolean exportDB(Context, File)                       // 导出数据库到文件
String importDB(Context, File, Handler)               // 从文件导入数据库
```

### 4.5 SharedPreferences 配置

`Settings.java` 管理两个 SharedPreferences 实例：

#### 默认 SharedPreferences

存储全局应用设置，包括：

| 分类 | 典型键 | 说明 |
|------|--------|------|
| 显示 | 主题、语言、画廊列表样式 | 界面偏好 |
| 网络 | 代理设置、DNS-over-HTTPS | 网络配置 |
| 下载 | 下载路径、并发数 | 下载偏好 |
| 安全 | 应用锁、指纹 | 安全设置 |
| 高级 | 历史数量上限 (默认 100) | 高级配置 |

#### Archiver Cache SharedPreferences

键名：`archiver_cache`，用于归档下载追踪：

```java
GalleryInfo getArchiverDownload(long downloadId)     // 获取归档下载信息
void putArchiverDownload(long downloadId, GalleryInfo) // 保存归档下载
boolean deleteArchiverDownload(long downloadId)       // 删除归档记录
long getArchiverDownloadId(long gid)                  // 按 GID 获取下载 ID
void putArchiverDownloadId(long gid, long downloadId) // 保存 GID→下载ID 映射
```

### 4.6 缓存层

#### BeerBelly 两级缓存 (`com.hippo.beerbelly`)

提供 **内存 LRU 缓存 + 磁盘 LRU 缓存** 的两级缓存框架：

```
请求 → 查内存 LRU → 命中? → 返回
                    ↓ 未命中
              查磁盘 LRU → 命中? → 写入内存 → 返回
                           ↓ 未命中
                     网络请求 → 写入磁盘 → 写入内存 → 返回
```

**配置参数**：

| 参数 | 说明 |
|------|------|
| `hasMemoryCache` | 是否启用内存缓存 |
| `memoryCacheMaxSize` | 内存缓存上限 |
| `hasDiskCache` | 是否启用磁盘缓存 |
| `diskCacheDir` | 磁盘缓存目录 |
| `diskCacheMaxSize` | 磁盘缓存上限 |

**磁盘缓存实现** (DiskLruCache)：
- Journal 文件记录事务日志
- LinkedHashMap 维护 LRU 访问顺序
- 后台线程执行淘汰清理
- 原子提交保证一致性

#### Conaco 异步资源加载 (`com.hippo.conaco`)

在 BeerBelly 基础上封装异步加载逻辑：

```
Conaco.load(key, url, unikery)
  → 检查内存 (SOURCE_MEMORY=0) → 命中 → unikery.onGetValue()
  → 检查磁盘 (SOURCE_DISK=1)   → 命中 → unikery.onGetValue()
  → 网络请求 (SOURCE_NETWORK=2) → 成功 → 写缓存 → unikery.onGetValue()
                                 → 失败 → unikery.onMiss()
```

**线程池配置**：
- 磁盘线程池：串行执行，3 秒超时
- 网络线程池：3 个工作线程，5 秒超时

### 4.7 ER 关系图

```
DOWNLOADS ─── 1:1 ─── DOWNLOAD_DIRNAME   (通过 GID 关联)
    │
    └── N:1 ── DOWNLOAD_LABELS            (通过 LABEL 字段关联)

HISTORY, LOCAL_FAVORITES, BOOKMARKS       (独立表，共享 GalleryInfo 字段结构)

Gallery_Tags ─── 1:1 ─── (对应网络画廊)   (通过 GID 关联)

FILTER, QUICK_SEARCH, Black_List          (配置类独立表)
```

> **设计特点**：所有包含画廊信息的表 (DOWNLOADS, HISTORY, LOCAL_FAVORITES, BOOKMARKS) 都内联了 GalleryInfo 的核心字段 (title, thumb, category 等)，采用**反范式设计**避免 JOIN 查询，以提升 Android 端查询性能。

---

## 5. UI 与前端架构

### 5.1 Scene/Fragment 导航框架

EhViewer 使用自研的 **Scene 导航框架**，而非 Android Navigation Component。核心思想是在单个 Activity 中管理多个 Scene (基于 Fragment)。

**核心类**：

| 类 | 位置 | 职责 |
|----|------|------|
| `StageActivity` | `com.hippo.scene` | Activity 容器，管理 Scene 栈 |
| `SceneFragment` | `com.hippo.scene` | Fragment 基类，支持 Launch Mode |
| `StageLayout` | `com.hippo.scene` | 自定义 FrameLayout，管理 Scene 视图绘制顺序 |
| `BaseScene` | `com.hippo.ehviewer.ui.scene` | 业务场景基类，集成 Drawer |
| `ToolbarScene` | `com.hippo.ehviewer.ui.scene` | 带 Toolbar 的场景基类 |

**Launch Mode**：

| 模式 | 行为 | 类似 Android |
|------|------|-------------|
| `LAUNCH_MODE_STANDARD` | 每次都创建新实例入栈 | Activity standard |
| `LAUNCH_MODE_SINGLE_TOP` | 栈顶相同则复用 | Activity singleTop |
| `LAUNCH_MODE_SINGLE_TASK` | 清除其上所有场景后复用 | Activity singleTask |

**场景导航流程**：

```
StageActivity.startScene(Announcer)
  → 查找已有实例 (根据 Launch Mode)
    → STANDARD: 直接创建新 Fragment 入栈
    → SINGLE_TOP: 栈顶匹配则调用 onNewArguments()
    → SINGLE_TASK: pop 到已有实例，调用 onNewArguments()
  → FragmentTransaction.add/replace
  → 更新 mSceneTagList (场景标签栈)
```

### 5.2 MainActivity

`MainActivity` 继承 `StageActivity`，是唯一的 Activity：

**主要职责**：
- 管理侧边导航抽屉 (EhDrawerLayout)，左抽屉 = 导航菜单，右抽屉 = 场景自定义内容
- 初始化用户头像/资料到 Header
- 注册全部 Scene 及其 Launch Mode (静态初始化块)
- 检测剪贴板中的 E-Hentai URL 并提示打开
- 处理 Intent 跳转 (Deep Link)

**导航菜单项**：

| 菜单项 | 目标 Scene | Launch Mode |
|--------|-----------|-------------|
| 主页 | GalleryListScene | SINGLE_TOP |
| 订阅 | SubscriptionsScene | SINGLE_TASK |
| 热门 | GalleryListScene (WhatsHot) | SINGLE_TOP |
| 排行 | EhTopListScene | SINGLE_TOP |
| 收藏 | FavoritesScene | SINGLE_TASK |
| 历史 | HistoryScene | SINGLE_TOP |
| 下载 | DownloadsScene | SINGLE_TASK |
| 设置 | SettingsActivity | - |

### 5.3 全部 Scene 列表

#### 画廊浏览类

| Scene | Launch Mode | 功能 |
|-------|-------------|------|
| `GalleryListScene` | SINGLE_TOP | 画廊列表 (首页/搜索/标签/上传者) |
| `GalleryDetailScene` | STANDARD | 画廊详情 (元数据、标签、评论、预览) |
| `GalleryPreviewsScene` | STANDARD | 预览缩略图浏览 |
| `GalleryInfoScene` | STANDARD | 画廊基本信息展示 |
| `GalleryCommentsScene` | STANDARD | 评论列表与发表 |

#### 收藏与历史

| Scene | Launch Mode | 功能 |
|-------|-------------|------|
| `FavoritesScene` | SINGLE_TASK | 收藏管理 (10 个分类) |
| `HistoryScene` | SINGLE_TOP | 浏览历史 |
| `SubscriptionsScene` | SINGLE_TASK | 关注订阅 |
| `EhTopListScene` | SINGLE_TOP | 排行榜 |

#### 下载管理

| Scene | Launch Mode | 功能 |
|-------|-------------|------|
| `DownloadsScene` | SINGLE_TASK | 下载列表 (进度、状态) |
| `DownloadLabelsScene` | SINGLE_TASK | 下载标签管理 |

#### 认证

| Scene | Launch Mode | 功能 |
|-------|-------------|------|
| `SignInScene` | SINGLE_TASK | 账号密码登录 |
| `WebViewSignInScene` | SINGLE_TASK | WebView 登录 |
| `CookieSignInScene` | SINGLE_TASK | 手动输入 Cookie 登录 |

#### 系统

| Scene | Launch Mode | 功能 |
|-------|-------------|------|
| `SecurityScene` | SINGLE_TASK | 应用锁验证 |
| `WarningScene` | SINGLE_TASK | 首次启动警告 |
| `AnalyticsScene` | SINGLE_TASK | 分析统计提示 |

### 5.4 OpenGL 画廊渲染器

图片浏览使用自研的 OpenGL ES 渲染引擎，位于 `com.hippo.lib.glview/` 和 `com.hippo.lib.glgallery/`。

#### 渲染架构

```
Android TextureView (GLRootView)
  └── GLRoot (渲染线程管理)
        └── GLCanvas (绘图表面)
              └── GLView 树 (组件层级)
                    ├── GalleryView (画廊容器)
                    │     ├── PagerLayoutManager (翻页模式)
                    │     └── ScrollLayoutManager (滚动模式)
                    └── GalleryPageView (单页)
                          ├── ImageView (图片 + 缩放/平移)
                          ├── GLProgressView (加载进度)
                          ├── GLTextView (页码)
                          └── GLTextureView (错误信息)
```

#### GalleryView 配置

| 属性 | 说明 |
|------|------|
| 布局模式 | LEFT_TO_RIGHT, RIGHT_TO_LEFT, TOP_TO_BOTTOM |
| 缩放模式 | ORIGIN, FIT_WIDTH, FIT_HEIGHT, FIT, FIXED |
| 页间距 | `mPagerInterval` (翻页模式) / `mScrollInterval` (滚动模式) |
| 最小高度 | `mPageMinHeight` |
| 进度指示器 | 颜色和大小可配置 |
| 页码显示 | 颜色、大小、字体可配置 |

#### GLView 系统

自研的 OpenGL UI 框架，类似于 Android View 系统：

| 组件 | 对应 Android | 功能 |
|------|-------------|------|
| `GLView` | `View` | 基础组件，支持树形层级 |
| `GLFrameLayout` | `FrameLayout` | 帧布局 |
| `GLLinearLayout` | `LinearLayout` | 线性布局 |
| `GLRoot` | `ViewRootImpl` | 渲染线程 + 事件分发 |
| `GLCanvas` | `Canvas` | 绘图操作 |
| `GLTexture` | - | 纹理资源管理 |
| `GLPaint` | `Paint` | 样式 (颜色、大小、字体) |
| `CanvasAnimation` | `Animation` | 动画 (Alpha、Float 等) |

**设计特点**：
- 完全绕过 Android View 系统，直接在 GL 线程上渲染
- 内存池复用 GalleryPageView 减少 GC
- 支持手势 (缩放、平移、fling)
- 图片加载时显示进度动画
- 共享元素过渡动画

### 5.5 自定义 Widget

`com.hippo.widget/` 包含 38 个通用自定义控件，`com.hippo.ehviewer.widget/` 包含应用专属控件：

**通用控件** (部分列举)：

| 控件 | 用途 |
|------|------|
| `DrawerLayout` | 自定义抽屉布局 (修改版) |
| `EasyRecyclerView` | 增强型 RecyclerView |
| `SearchBar` / `SearchBarMover` | 搜索栏动画 |
| `FabLayout` | 浮动按钮组布局 |
| `LoadImageView` | 带缓存加载的 ImageView |
| `ProgressView` | 自定义进度条 |
| `Slider` | 自定义滑块 |
| `LockPatternView` | 图案锁 |
| `FixedAspectImageView` | 固定比例 ImageView |
| `GalleryHeader` | 画廊详情头部 |

---

## 6. 下载系统与 Spider 管线

### 6.1 系统总览

下载系统由三层组成：**DownloadManager** (任务调度) → **SpiderQueen** (图片抓取) → **SpiderDen** (磁盘存储)。

```
用户点击下载
  → DownloadManager.addDownload(GalleryInfo, label)
    → 加入 mWaitList (等待队列)
    → 出队 → 创建 SpiderQueen (MODE_DOWNLOAD)
      → SpiderQueen 启动工作线程池
        → 获取 SpiderInfo (页面 Token 列表)
        → 并行下载各页图片
          → SpiderDen 写入磁盘
        → 回调 OnSpiderListener 通知进度
      → DownloadManager 更新状态 → EhDB 持久化 → EventBus 通知 UI
```

### 6.2 DownloadManager (任务调度)

**位置**：`com.hippo.ehviewer.download.DownloadManager`

#### 核心数据结构

```java
mAllInfoList: LinkedList<DownloadInfo>              // 全部下载记录
mAllInfoMap: SparseJLArray<DownloadInfo>             // GID → DownloadInfo 快速查找
mMap: Map<String, LinkedList<DownloadInfo>>          // Label → 下载列表 (按标签分组)
mWaitList: LinkedList<DownloadInfo>                  // 等待下载队列
mCurrentTask: DownloadInfo                           // 当前下载任务
mCurrentSpider: SpiderQueen                          // 当前 Spider 实例
```

#### 下载状态机

```
                      addDownload()
 [初始] ──────────────→ [等待中]
   ↑                      │
   │                      ↓ 出队
   │                   [下载中] ──→ [已完成]
   │                      │
   │                      ↓ 失败
   │                   [失败] ──→ (重试) → [等待中]
   │                      │
   └── stopDownload() ←──┘
```

#### 公开 API

```java
// 添加下载任务
void addDownload(GalleryInfo galleryInfo, String label, int state)

// 控制下载
void stopDownload(long gid)                // 停止单个
void stopAllDownload()                     // 停止全部
void deleteDownload(long gid)              // 删除 (含文件)
void deleteRangeDownload(LongList gidList) // 批量删除

// 查询
DownloadInfo getDownloadInfo(long gid)     // 获取下载信息
int getDownloadState(long gid)             // 获取状态

// 标签管理
List<DownloadLabel> getLabelList()
LinkedList<DownloadInfo> getLabelDownloadInfoList(String label)
void changeLabel(List<DownloadInfo>, String newLabel)
void addLabel(String)
void deleteLabel(String)
```

#### 监听器

```java
// 全局下载事件
interface DownloadListener {
    void onStart(DownloadInfo info)
    void onDownload(DownloadInfo info)
    void onGetPage(DownloadInfo info)
    void onFinish(DownloadInfo info)
    void onCancel(DownloadInfo info)
}

// 单项信息更新
interface DownloadInfoListener {
    void onAdd(DownloadInfo info, List<DownloadInfo> list, int position)
    void onUpdate(DownloadInfo info, List<DownloadInfo> list)
    void onUpdateAll()
    void onReload()
}
```

### 6.3 DownloadService (后台服务)

**位置**：`com.hippo.ehviewer.download.DownloadService.kt`

Android 后台 Service，维持下载进程存活并管理通知栏：

**通知类型**：
- `mDownloadingBuilder` — 下载中通知 (显示进度)
- `mDownloadedBuilder` — 下载完成通知
- `m509dBuilder` — HTTP 509 (流量限制) 错误通知

**Intent Action**：

| Action | 功能 |
|--------|------|
| `ACTION_CLEAR` | 清除通知 |
| `ACTION_DELETE` | 删除单个下载 |
| `ACTION_DELETE_RANGE` | 批量删除 |
| `ACTION_STOP_ALL` | 停止全部下载 |
| `ACTION_STOP_RANGE` | 停止范围下载 |
| `ACTION_STOP_CURRENT` | 停止当前下载 |

**生命周期**：
- `onCreate()` → 初始化 DownloadManager 和通知
- `onStartCommand()` → 返回 `START_STICKY` (系统杀死后自动重启)
- `onDestroy()` → 释放监听器和资源

### 6.4 SpiderQueen (图片抓取管线)

**位置**：`com.hippo.ehviewer.spider.SpiderQueen`

这是下载系统的**核心引擎**，负责从 E-Hentai 服务器并行抓取画廊所有页面图片。

#### 单例管理

```java
// 每个画廊一个 SpiderQueen 实例，缓存在 sQueenMap 中
static SpiderQueen obtainSpiderQueen(Context, GalleryInfo, int mode)
static void releaseSpiderQueen(SpiderQueen, int mode)
```

**运行模式**：

| 模式 | 用途 | 行为差异 |
|------|------|----------|
| `MODE_READ` | 在线浏览 | 按需加载，优先当前页 |
| `MODE_DOWNLOAD` | 后台下载 | 顺序下载全部页面 |

#### 内部架构

```
SpiderQueen
  ├── mWorkerPoolExecutor (线程池, 可配置线程数)
  │     └── Worker (下载单页图片)
  │           ├── 获取 Page Token (mPTokenMap)
  │           ├── 请求图片页 HTML (EhEngine.getGalleryPage)
  │           ├── 解析图片 URL
  │           └── 下载图片 → SpiderDen 写入磁盘
  │
  ├── mDecodeThread[2] (解码线程, 2 个)
  │     └── 解码已下载的图片数据
  │
  ├── mRequestPageQueue     (普通请求队列)
  ├── mRequestPageQueue2    (预加载请求队列)
  ├── mForceRequestPageQueue (优先请求队列)
  └── mRequestPTokenQueue   (Token 请求队列)
```

#### 页面状态管理

每页图片有独立的下载状态：

```java
mPageStateArray: volatile int[]  // 所有页面状态
// 状态值：
STATE_NONE       = 0  // 未开始
STATE_DOWNLOADING = 1  // 下载中
STATE_FINISHED    = 2  // 已完成
STATE_FAILED      = 3  // 失败
```

#### Page Token 机制

E-Hentai 的安全机制要求每页图片都需要一个 Token 才能获取 URL：

```
1. 首次访问画廊 → 获取 SpiderInfo (含部分 pToken)
2. 从预览页批量获取 pToken → 存入 mPTokenMap
3. 如果缺少某页 Token → mRequestPTokenQueue 排队
4. 专用线程调用 EhEngine.getGalleryToken() 获取
5. Token 缓存到 SpiderInfo 持久化到磁盘
```

#### 监听器接口

```java
interface OnSpiderListener {
    void onGetPages(int pages)                                    // 获取到总页数
    void onGet509(int index)                                      // 遇到 509 限制
    void onPageDownload(int index, long contentLength,            // 页面下载进度
                        long receivedSize, int bytesRead)
    void onPageSuccess(int index, int finished,                   // 页面下载成功
                       int downloaded, int total)
    void onPageFailure(int index, String error,                   // 页面下载失败
                       int finished, int downloaded, int total)
    void onFinish(int finished, int downloaded, int total)        // 全部完成
}
```

### 6.5 SpiderInfo (元数据持久化)

**位置**：`com.hippo.ehviewer.spider.SpiderInfo`

存储画廊的下载元数据，支持序列化到磁盘以实现**断点续传**。

**持久化字段**：

| 字段 | 类型 | 用途 |
|------|------|------|
| `startPage` | int | 断点续传位置 |
| `gid` | long | 画廊 ID |
| `token` | String | 画廊 Token |
| `pages` | int | 总页数 |
| `previewPages` | int | 预览页数 |
| `previewPerPage` | int | 每预览页包含的图片数 |
| `pTokenMap` | SparseArray\<String\> | 页码 → Page Token 映射 |

**序列化格式** (v2)：
- 写入到画廊下载目录的 `.ehviewer` 文件
- 自定义二进制格式 (版本号 + 各字段)

### 6.6 SpiderDen (磁盘存储管理)

**位置**：`com.hippo.ehviewer.spider.SpiderDen`

管理画廊图片在磁盘上的存储位置和读写。

**目录查找逻辑**：

```
1. 从数据库查找已知目录名 (EhDB.getDownloadDirname)
2. 搜索下载根目录下匹配 GID 前缀的文件夹
3. 如果不存在 → 按 "{gid}-{sanitized_title}" 格式创建新目录
```

**图片缓存**：
- 位置：`context.cacheDir/image/`
- 大小：40-640 MB (可配置)
- 实现：`SimpleDiskCache` (BeerBelly 磁盘缓存)

**下载模式切换**：
- `setMode(MODE_READ)` → 只使用缓存，不创建持久目录
- `setMode(MODE_DOWNLOAD)` → 创建持久目录，写入完整图片文件

### 6.7 GalleryProvider (画廊数据源)

抽象基类 `GalleryProvider2` 为 OpenGL 渲染器提供图片数据，有三种实现：

#### EhGalleryProvider (在线画廊)

```
GalleryView ←── EhGalleryProvider ←── SpiderQueen (MODE_READ)
                    │
                    ├── onRequest(index)      → 发起下载请求
                    ├── onForceRequest(index)  → 优先下载请求
                    ├── onCancelRequest(index) → 取消请求
                    └── save(index, file)      → 保存图片到指定位置
```

- 图片文件名格式：`{gid}-{token}-{index+1}`
- 内部委托 SpiderQueen 完成所有图片获取
- release 时延迟 3 秒释放 SpiderQueen (避免快速切换画廊时重复创建)

#### ArchiveGalleryProvider (压缩包画廊)

支持 ZIP / 7Z / RAR 格式的本地压缩包：

```
GalleryView ←── ArchiveGalleryProvider
                    ├── archiveThread (解压线程)
                    └── decodeThread  (解码线程)
```

- 维护 `LinkedHashMap<Integer, InputStream>` 管理解压流
- 最大支持 100,000 页 (防止 OOM)

#### DirGalleryProvider (本地文件夹画廊)

浏览已下载到本地的画廊：

```
GalleryView ←── DirGalleryProvider
                    └── mBgThread (后台加载线程)
```

- 扫描目录内的图片文件 (.jpg, .jpeg, .png, .gif, .webp)
- 使用 NaturalComparator 自然排序
- 支持 `getStartPage()` 恢复上次阅读位置

---

## 7. 网络层与基础设施

### 7.1 OkHttp 客户端配置

应用维护两个 OkHttp 客户端实例 (在 `EhApplication` 中初始化)：

| 客户端 | 用途 | 特点 |
|--------|------|------|
| `mOkHttpClient` | 通用 HTTP 请求 (API、HTML 页面) | 标准超时 |
| `mImageOkHttpClient` | 图片下载 | 更长超时、独立连接池 |

**公共配置**：
- Cookie 管理：`EhCookieStore` (自动持久化到 SQLite)
- DNS 解析：`EhHosts` (硬编码 IP + DoH 备选)
- SSL/TLS：`EhSSLSocketFactory` (TLS 1.2 强制 + 域前置)
- 连接池：OkHttp 默认连接池

### 7.2 DNS 解析策略 (EhHosts)

**位置**：`com.hippo.ehviewer.client.EhHosts`

为绕过 DNS 污染/封锁，内置硬编码 IP 地址：

| 域名 | 硬编码 IP (部分) | 用途 |
|------|-----------------|------|
| `e-hentai.org` | 104.20.18.168, 104.20.19.168, 172.67.2.238 | 主站 |
| `exhentai.org` | 178.175.128.251-254, 178.175.129.251-254 | ExHentai |
| `forums.e-hentai.org` | 172.66.132.196, 172.66.140.62 | 论坛 |
| `ehgt.org` | 109.236.85.28, 62.112.8.21 | 图片服务器 |
| `s.exhentai.org` | 178.175.128.253-254, 178.175.129.253-254 | ExH 图片 |

**解析顺序**：

```
1. 用户自定义 Hosts (Settings)
2. 内置硬编码 IP (如果在 Settings 中启用)
3. DNS-over-HTTPS (Yandex: https://77.88.8.1/dns-query)
4. 系统 DNS (兜底)
```

**负载均衡**：
- 多个 IP 通过 `Collections.shuffle()` 随机排序
- 种子为当前时间，每次请求分散到不同 IP

### 7.3 Cookie 管理

#### CookieRepository (`com.hippo.network`)

实现 OkHttp `CookieJar` 接口，提供 Cookie 持久化：

```
OkHttp 请求
  → CookieRepository.loadForRequest(url)
    → 内存缓存 (Map<String, CookieSet>)
      → 匹配域名、路径、过期时间
      → 返回有效 Cookie 列表

OkHttp 响应
  → CookieRepository.saveFromResponse(url, cookies)
    → 更新内存缓存
    → 持久化到 SQLite (CookieDatabase)
```

**存储**：
- 内存：`Map<String, CookieSet>` (域名 → Cookie 集合)
- 持久化：SQLite 数据库 `okhttp3-cookie.db`
- 区分持久 Cookie 和会话 Cookie

#### EhCookieStore (`com.hippo.ehviewer.client`)

在 CookieRepository 基础上封装 E-Hentai 特定逻辑：

```java
// 关键 Cookie
KEY_IPD_MEMBER_ID = "ipb_member_id"    // 用户 ID
KEY_IPD_PASS_HASH = "ipb_pass_hash"    // 密码哈希
KEY_IGNEOUS       = "igneous"          // ExHentai 凭证

// 自动注入 Cookie (隐藏内容警告)
sTipsCookie: name="nw", value="1", domain="e-hentai.org"

// 认证检查
boolean hasSignedIn()  // ipb_member_id AND ipb_pass_hash 均存在
```

### 7.4 SSL/TLS 配置

**EhSSLSocketFactory** (`com.hippo.network`)：

| 特性 | 说明 |
|------|------|
| TLS 1.2 强制 | 通过 `Tls12SocketFactory` 确保 |
| SSLv3 禁用 | `NoSSLv3SSLSocket` 移除 SSLv3 |
| 域前置 | `Settings.getDF()` 启用时修改 SNI |
| 证书验证 | `EhX509TrustManager` 自定义验证 |
| Conscrypt | 使用 Conscrypt 作为 SSL 提供者 |
| 低版本兼容 | `EhSSLSocketFactoryLowSDK` 适配旧设备 |

### 7.5 请求构建

`EhRequestBuilder` 继承 `ChromeRequestBuilder`：

```java
// 自动添加的 Header
User-Agent: Chrome 浏览器签名
Accept-Language: 标准浏览器值

// E-Hentai 特定 Header
Referer: https://[e-hentai|exhentai].org
Origin: https://[e-hentai|exhentai].org

// 请求体类型
FormBody     → 表单 POST (登录、收藏、评论)
JSON String  → API POST (api.php)
MultipartBody → 图片搜索上传
```

### 7.6 UniFile 文件抽象层

**位置**：`com.hippo.unifile/` (16 个文件)

统一文件访问接口，兼容三种 Android 文件访问方式：

| 实现类 | 对应 API | 适用场景 |
|--------|----------|----------|
| `RawFile` | `java.io.File` | 内部存储、旧版外部存储 |
| `TreeDocumentFile` | DocumentsContract (SAF) | Android 5.0+ 外部存储 |
| `MediaFile` | MediaStore | Android 10+ 分区存储 |

**统一接口**：

```java
interface UniFile {
    UniFile createFile(String displayName)
    UniFile createDirectory(String displayName)
    Uri getUri()
    String getName()
    String getType()
    boolean isFile()
    boolean isDirectory()
    long length()
    boolean delete()
    boolean exists()
    UniFile[] listFiles()
    OutputStream openOutputStream()
    InputStream openInputStream()
    UniFile findFile(String displayName)
    boolean renameTo(String displayName)
}
```

### 7.7 自研基础库总结

| 库 | 包名 | 核心功能 | 对标 |
|----|------|----------|------|
| **BeerBelly** | `com.hippo.beerbelly` | 内存 + 磁盘两级 LRU 缓存 | DiskLruCache + LruCache |
| **Conaco** | `com.hippo.conaco` | 异步资源加载 + 三级缓存 | Glide/Picasso (简化版) |
| **UniFile** | `com.hippo.unifile` | 统一文件访问抽象 | AndroidX DocumentFile |
| **GLView** | `com.hippo.lib.glview` | OpenGL ES UI 框架 | Android View (GL 实现) |
| **GLGallery** | `com.hippo.lib.glgallery` | 画廊浏览渲染器 | PhotoView (GL 实现) |
| **Yorozuya** | `com.hippo.lib.yorozuya` | 通用工具集 | Apache Commons / Guava |
| **Scene** | `com.hippo.scene` | Fragment 场景导航 | Android Navigation |

### 7.8 事件总线

使用 **EventBus 3.3.1** 进行跨组件通信：

**主要事件** (位于 `ehviewer/event/`)：

| 事件 | 触发场景 | 消费者 |
|------|----------|--------|
| 收藏变更 | 添加/移除收藏 | 画廊列表刷新 |
| 下载状态变更 | 下载开始/完成/失败 | 下载列表 UI 更新 |

### 7.9 原生 JNI 桥接

**位置**：`app/src/main/cpp/`

自定义 JNI 代码 (~4,400 行) 连接 Java 和 C 图片库：

```
Java 层
  ├── com.hippo.lib.image.Image      ← JNI 入口
  └── com.hippo.Native               ← Kotlin native 声明
        │
        ▼ (JNI 调用)
C 层
  ├── image.c                        ← 主 JNI 桥接
  ├── fdutils.c                      ← 文件描述符工具
  ├── gifutils.c                     ← GIF 工具
  ├── gif/native-lib.cpp             ← GIF 动画支持
  └── 第三方库
        ├── libjpeg-turbo/           ← JPEG 编解码
        ├── libpng/                  ← PNG 解码
        ├── libwebp/                 ← WebP 编解码
        └── giflib/                  ← GIF 解码
```

**支持的图片格式**：
- JPEG (libjpeg-turbo, SIMD 优化)
- PNG (libpng)
- WebP (libwebp, 含动画 WebP)
- GIF (giflib, 含动画 GIF)

---

## 附录 A：关键文件索引

| 文件 | 路径 (相对于 `app/src/main/java/com/hippo/`) | 行数 |
|------|----------------------------------------------|------|
| EhEngine | `ehviewer/client/EhEngine.java` | ~1,418 |
| EhClient | `ehviewer/client/EhClient.java` | ~251 |
| EhUrl | `ehviewer/client/EhUrl.java` | ~321 |
| EhConfig | `ehviewer/client/EhConfig.java` | ~800+ |
| EhDB | `ehviewer/EhDB.java` | ~600+ |
| Settings | `ehviewer/Settings.java` | ~800+ |
| DownloadManager | `ehviewer/download/DownloadManager.java` | ~1,100+ |
| SpiderQueen | `ehviewer/spider/SpiderQueen.java` | ~800+ |
| SpiderDen | `ehviewer/spider/SpiderDen.java` | ~300+ |
| SpiderInfo | `ehviewer/spider/SpiderInfo.java` | ~100+ |
| MainActivity | `ehviewer/ui/MainActivity.java` | ~700+ |
| GalleryListScene | `ehviewer/ui/scene/GalleryListScene.java` | ~1,500+ |
| GalleryDetailScene | `ehviewer/ui/scene/GalleryDetailScene.java` | ~1,200+ |
| GalleryView | `lib/glgallery/GalleryView.java` | ~800+ |
| GLView | `lib/glview/view/GLView.java` | ~500+ |
| BeerBelly | `beerbelly/BeerBelly.java` | ~300+ |
| CookieRepository | `network/CookieRepository.java` | ~150+ |
| EhHosts | `ehviewer/client/EhHosts.java` | ~173 |

---

## 附录 B：设计模式总结

| 模式 | 应用场景 |
|------|----------|
| **Facade (门面)** | EhDB 封装全部 DAO 操作；EhEngine 封装全部 API 调用 |
| **Singleton (单例)** | SpiderQueen 按画廊 GID 缓存；EhApplication 全局实例 |
| **Observer (观察者)** | EventBus 跨组件事件；SpiderQueen.OnSpiderListener |
| **Strategy (策略)** | GalleryProvider 三种实现 (Eh/Archive/Dir) |
| **Builder (构建器)** | ListUrlBuilder, EhRequestBuilder, FormBody.Builder |
| **Template Method (模板方法)** | BaseScene/ToolbarScene 提供生命周期钩子 |
| **Async Callback** | EhClient.Callback\<E\> 异步回调 |
| **LRU Cache** | BeerBelly 内存+磁盘两级缓存 |
| **反范式数据库** | 画廊信息内联到各表，避免 JOIN |
