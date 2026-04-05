# P1 缓存淘汰调度 — 设计文档

**日期:** 2026-04-05
**状态:** 已批准
**范围:** pandora-daemon 缓存定时淘汰

## 背景

`CacheManager` 已实现 `evict_images()`（LRU 磁盘淘汰）和 `prune_expired_galleries()`（TTL 内存清理），但从未被调用。缓存无限增长直到进程重启。

## 方案选择

| 方案 | 描述 | 结论 |
|------|------|------|
| A 仅定时淘汰 | 后台循环定期调用已有方法 | ✅ 采用 |
| B 定时+写入触发 | 额外维护 `_current_size`，写入超限时立即淘汰 | ❌ 过度设计，引入并发竞态 |
| C 仅写入触发 | 无定时任务，写入时检查 | ❌ gallery TTL 清理无触发点 |

选择 A 的理由：`evict_images()` 本身就做全目录扫描，不需要增量追踪；图片缓存短暂超限完全可接受；实现最简单。

## 设计

### 1. config.py — 新增字段

`CacheConfig` 新增：

```python
eviction_interval_seconds: int = 600
```

`load_config` 的 `[cache]` 段通用解析已覆盖，无需额外代码。

### 2. app.py — 淘汰循环

新增模块级协程：

```python
async def _cache_eviction_loop(cache: CacheManager, interval: int) -> None:
    while True:
        await asyncio.sleep(interval)
        try:
            cache.prune_expired_galleries()
            await cache.evict_images()
        except Exception:
            logger.exception("Cache eviction error")
```

执行顺序：先 `prune_expired_galleries()`（纯内存，快），再 `await evict_images()`（磁盘 I/O）。

异常处理：try/except 吞掉异常并 log，防止单次失败杀死循环。

### 3. app.py — lifespan 集成

`lifespan` 函数中：

```python
# yield 前
eviction_task = asyncio.create_task(
    _cache_eviction_loop(cache, config.cache.eviction_interval_seconds)
)

# yield 后
eviction_task.cancel()
with contextlib.suppress(asyncio.CancelledError):
    await eviction_task
```

### 4. cache.py — 不改

`evict_images()` 和 `prune_expired_galleries()` 已完整实现，无需修改。

## 改动文件清单

| 文件 | 改动 |
|------|------|
| `pandora_daemon/config.py` | `CacheConfig` 加 `eviction_interval_seconds: int = 600` |
| `pandora_daemon/app.py` | 加 `_cache_eviction_loop`，lifespan 中启动/关闭 |

## 测试计划

| 测试 | 验证点 |
|------|--------|
| `test_config_eviction_interval_default` | 默认值 600 |
| `test_config_eviction_interval_custom` | TOML 自定义值生效 |
| `test_cache_eviction_loop_calls` | 循环调用 prune + evict，顺序正确 |
| `test_cache_eviction_loop_exception_resilience` | evict 抛异常，循环继续运行 |
| `test_cache_eviction_loop_cancel` | cancel 后干净退出，无异常 |
| `test_lifespan_starts_eviction_task` | lifespan 启动了 eviction task |
