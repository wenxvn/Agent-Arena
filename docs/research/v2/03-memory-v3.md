# V2-03 Memory v3：Spatial/Event M1

## 状态

Memory v3 离线实现与 fail-closed provider budget guard 已完成本地实现和验证；真实模型 pilot 尚未运行，S2 Gate 尚未完成。当前新增 provider API 调用为 0，也没有 GPU 运行。预算门禁、hash 差异说明和 4 个配对计划 cell 见 [V2 在线运行登记表](00-run-registry.md)。

## 实现范围

- 新增 `memory_version=v3_spatial_event`，仅用于 `agent=memory`；默认仍为 v2。v2 的 reducer、renderer 与既有 trace provenance 保持兼容。
- v3 状态仅由公开 Observation、已校验 Action 和 ToolResult 更新：记录当前房间、episode 内全部已观察到的访问房间、有向可见出口、成功移动边和成功公开因果事件。Frontier 排除已访问目标和已走通的同向边；反向边独立保留。
- v2 的 12 项访问地点列表是有损短列表；v3 另保留上限 64 的 episode 访问房间集合，避免已进入房间因短列表容量而被误判成 frontier。
- 记忆渲染上限为 12,000 字符。超限按固定顺序省略旧普通事实、失败摘要和 v2 短访问列表，并记录 omission counts；影响导航语义的 v3 房间/出口/边/事件超过数量或字符预算时，在下一次 provider 请求前失败，不静默淘汰。
- Trace 可选地记录累计 insertions、updates、invalidations、compactions、rendered_chars 和字符估算 token 数。历史 trace 缺少该字段时仍可读取。

## 离线验证

2026-10-13，在隔离的 Python 3.13 临时环境执行：

| 检查 | 结果 |
|---|---|
| `ruff check .` | 通过 |
| `mypy src` | 通过，48 个源文件 |
| `pytest -q` | 316 passed |
| Trace audit | 518 个文件，474 个唯一 episode，44 个重复副本；派生 CSV/JSON 已加入内存统计列，历史 trace 中携带该字段的 episode 为 0 |

2026-10-13 随后加入跨 invocation 的 fail-closed provider budget guard，首次检查为 329 passed。独立复审后增加 expected provider、OS request/invocation leases、跨进程锁测试、截止时间后记账、terminal ledger status 一致性、CLI 中断状态修复，以及后续 cell 身份不匹配时保留已完成汇总；Python 3.13 临时隔离环境最终检查为 Ruff 通过、mypy 通过（49 个源文件）、全量 pytest 338 passed、`uv lock --check` 与 `git diff --check` 通过。依赖文件未改动，实现提交 SHA `0a09a4f479cd8b6ba49dd0eeefed80a47d623c06` 已冻结登记；真实模型调用尚未开始。完整设计见 [spec 0015](../../specs/0015-v2-provider-budget-guard/index.md)。

定向 fixture 覆盖公开 frontier 与成功边、v3 访问集合在 v2 12 项短列表达到容量后的正确性、必需房间/出口/边/事件容量边界、事件顺序不预设、episode reset、公开前置条件修复、超限压缩与显式失败、v3 provenance/step statistics、config 兼容及旧 trace 审计读取。测试和静态检查不证明模型收益。

## Pilot 决策

候选比较预登记为 `lunar_escape_v2_seeded` 的 seed 1、2，Memory v2 与 v3 配对，每局 100 decisions，E1 ON / H5 / R1 / P2(world-declared) 条件固定，串行运行。共享上限、输出 cap、全局超时、ledger 和两条执行命令已写入 run registry；每次决策调用都在发出前预留并落盘，请求/重试/usage 不确定时 fail closed。计划报告 first-recorded attempt、Success@60/100、动作数、重复边/动作、输入/输出 Token、token/success、provider_error 和延迟。实现 SHA `0a09a4f479cd8b6ba49dd0eeefed80a47d623c06` 已冻结；首次 hash 前置检查拒绝后，seed 1/2 的真实运行时 hash 已核对并修正登记，API 尝试仍为 0。S2 仍未完成。

离线指标、源 Trace 与既有 232-action 月球长尾事实仍只支持“值得检验”的 M1 假设；没有同条件 v2/v3 结果，不能声称成功率、步数、重复边或 token-efficiency 改善。当前运行时生成的 world definition hash 与旧长尾 trace 记录不同，原因未确认；因此旧 trace 只作假设来源，不作本轮 hash-matched 对照。下一步先提交并记录代码 SHA，再按冻结的预算执行 pilot；完成前不推进 S3。
