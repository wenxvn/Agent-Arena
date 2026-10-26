# 性能压力测试（合成历史）

- 数据：[1000, 5000] 条合成 run（`STRESS_DATA`，临时目录）
- 事件文件：每局 20 条
- 说明：压力数据是合成的，放在临时目录，永不进入真实账本；所有耗时为本机实测，不代表 CI 或用户机器。

## 关键数字（横向对比）

| 操作 | 1000 条 | 5000 条 |
|---|---|---|
| `index_cold_build` | 499.31 ms | 3317.93 ms |
| `index_rebuild_incremental` | 203.19 ms | 1173.35 ms |
| `page_first_50_lazy_new_index` | 18.45 ms | 30.71 ms |
| `page_first_50` | 0.1 ms | 0.41 ms |
| `aggregate` | 0.77 ms | 3.87 ms |
| 峰值内存 | 1443.26 KiB | 7277.86 KiB |

## 1000 条历史

- 环境：Windows-11-10.0.26200-SP0 / Python 3.13.3
- 峰值内存：1443.26 KiB
- 索引内存估算：320000 B
- 导出字节数：559780 B

| 操作 | 耗时 ms | 说明 |
|---|---:|---|
| `index_cold_build` | 499.31 | 首次构建（文件已在页缓存；含 JSON 解析） |
| `index_rebuild_incremental` | 203.19 | 强制重建：只重读 mtime 变化的文件 |
| `page_first_50` | 0.1 | — |
| `page_first_50_lazy_new_index` | 18.45 | 全新索引的第一页（只读当前页 manifest） |
| `page_offset_1000` | 0.13 | — |
| `filter_map_state` | 0.11 | — |
| `aggregate` | 0.77 | — |
| `export_json_bytes` | 8.11 | — |

## 5000 条历史

- 环境：Windows-11-10.0.26200-SP0 / Python 3.13.3
- 峰值内存：7277.86 KiB
- 索引内存估算：1600000 B
- 导出字节数：2798907 B

| 操作 | 耗时 ms | 说明 |
|---|---:|---|
| `index_cold_build` | 3317.93 | 首次构建（文件已在页缓存；含 JSON 解析） |
| `index_rebuild_incremental` | 1173.35 | 强制重建：只重读 mtime 变化的文件 |
| `page_first_50` | 0.41 | — |
| `page_first_50_lazy_new_index` | 30.71 | 全新索引的第一页（只读当前页 manifest） |
| `page_offset_1000` | 0.85 | — |
| `filter_map_state` | 0.55 | — |
| `aggregate` | 3.87 | — |
| `export_json_bytes` | 53.29 | — |

## 结论口径

- 分页只返回请求页，内存不随历史总量线性增长（索引只存列表字段）；
- 冷启动需要解析全部 manifest，这是 O(n) 的一次性成本；热查询命中索引；
- 事件文件不进入索引，回放时才按 run 读取，避免页面一次加载全部轨迹。

### 测量方法（先读这一节）

- 测量前先把全部 manifest 读一遍**预热**（不计时）：压力数据是刚写入的临时
  文件，首次读取会触发杀毒/索引扫描，单文件代价可达常态的 10–80 倍；
  不预热会把「安全软件扫描」误读成「我们的代码慢」。
- 因此 `index_cold_build` 读作「文件已在页缓存时的解析成本」，
  而不是「首次安装后第一次打开页面的耗时」。
- `page_first_50_lazy_new_index` 是「全新索引 + 只读当前页」的路径：
  目录只 stat、只解析 50 个 manifest，条目数与历史总量无关。
- `page_offset_1000` / `filter_map_state` / `aggregate` 在同一个已建索引上，
  读作「日常翻页/筛选/汇总」成本。
- 目录签名有 30 秒 TTL：TTL 内不重新 stat 全部目录；写入新 run 时
  `RunService.invalidate_index()` 会立刻失效缓存。
