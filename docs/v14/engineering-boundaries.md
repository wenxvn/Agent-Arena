# V14 工程边界（P2-2 / P2-4 / P2-5 / P2-6）

> 全部在临时目录用合成数据（`STRESS_DATA`）实测；零外部请求。

## 1. 冷启动与预热（P2-2）

| 项 | 毫秒 | 说明 |
|---|---:|---|
| `cold_first_open` | 951.41 | 全新进程/全新索引，未做任何预热（含文件系统首次读取） |
| `warm_page_first_50` | 0.06 | 已预热：索引已构建，读读页缓存 |
| `warm_index_rebuild` | 211.17 | 已预热后的全量索引重建（只 stat + 解析 manifest） |

> ``cold_first_open`` 是**未预热**的首次打开；``warm_*`` 是预热后的解析成本。两者不可互相替代，也不代表 CI 或用户机器的性能。

## 2. 异常负载（P2-2）

| 场景 | 结果 | 关键数字 |
|---|---|---|
| 损坏 manifest | 通过（不崩、不混入统计） | 索引 5 局、页面 5 条 |
| 并发读写 | 通过（0 异常） | 40 轮、异常 0、最终索引 60 局 |
| TTL 刷新 | 通过 | 3 → 4 → 4（TTL 30.0s） |

## 3. 长历史导出（P2-2 / P2-4）

- 导出 1000 / 1000 行，耗时 9.84 ms，索引估算 320000 字节；
- 导出只读 manifest 索引；不加载 events.jsonl，因此行数不受事件长度影响。

## 4. SDK 加固（P2-5）

| 检查 | 结果 | 说明 |
|---|---|---|
| `contract_version` | 通过 | agent_contract_version=agent_policy_v1（旧插件无需改动） |
| `public_observation_only` | 通过 | 插件可见字段 12 个；隐藏键 无 |
| `lifecycle_hooks` | 通过 | 缺失钩子：无 |
| `version_identity` | 通过 | agent_version=0.2.0 |
| `invalid_action_isolated` | 通过 | state=BUDGET_REACHED, invalid_actions=6 |
| `budget_and_simulated` | 通过 | cost=0, requests=0 |
| `exception_isolated` | 通过 | state=FAILED, outcome=policy_error, leaked=False |
| `legacy_act_signature` | 通过 | act(observation, history) 旧签名仍被适配 |
| `legacy_signature_compatible`（V14） | 通过 | agent_contract_version=agent_policy_v1 |
| `policy_exception_isolated`（V14） | 通过 | 非法动作/异常被计为局级失败，而不是让服务崩溃 |
| `budget_gateway_not_bypassable`（V14） | 通过 | 插件只看到公开观察；费用只由 gateway 结算 |

> 只验证本机可信插件；不声称可以安全运行任意第三方代码。

## 5. 账本复算（P2-6）

| 指标 | 复算值 | V13 记录 |
|---|---:|---:|
| 局数（settled） | 159 | 159 |
| started / settled | 159 / 159 | 159 / 159 |
| 请求数 | 5641 | 5641 |
| 结算费用 CNY | 5.43680012 | 5.43680012 |
| 重复结算 | 0 | 0 |
| 孤儿结算 | 0 | 0 |
| 费用未知局 | 0 | — |

- 与 V13 记录一致：是
- 外部账单：`NO_EXTERNAL_BILL_PROVIDED` — 用户未提供脱敏后台账单 CSV；外部对账保持 `BLOCKED_EXTERNAL`，不能假装已经对上外部账。

> 只读复算：不写账本、不重算费用、不重试任何局。`csv_subset` 只覆盖 138 局，不能代替全账本口径。

## 6. 导出一致性（P2-4）

| 文件 | 行数 |
|---|---:|
| `runs.csv` | 4 |
| `metrics.csv` | 22 |
| `paired_comparison.csv` | 2 |
| `findings.csv` | 15 |

- 模式：['simulated']（期望 `simulated`）
- 按类别统计的有效分母：4
- 空单元格：无
- 问题：无
- 结论：通过

> 导出口径必须一致：行数、分母、模式、空值处理，任一不一致即失败。
