# V2-03 Memory v3：Spatial/Event M1

## 状态

Memory v3 离线实现与 fail-closed provider budget guard 已完成本地实现和验证；seeded world identity 的跨进程不稳定问题已修复。三份隔离 ledger 的 v2 recovery 均在首个 episode 中因 provider error fail closed：BUDGET-01 2 次请求后 unknown spend，BUDGET-02 10 次后分类为 timeout，BUDGET-03 7 次后为通用 provider_error。没有完整 episode，v3 未启动，S2 Gate 尚未完成；三份 ledger 和部分输出均保留。当前登记矩阵已停止在线尝试。本次没有 GPU 运行。预算门禁、hash 差异和执行记录见 [V2 在线运行登记表](00-run-registry.md)。

针对这次无法从旧 ledger 追溯 provider error 原因的问题，已增加仅记录固定错误类别和可选 4xx/5xx 状态码的安全诊断字段；类别是基于异常链的 best-effort 分类，schema-1 ledger 可迁移至 schema 2，不记录 exception message 或 response。最新离线验证为 348 passed、Ruff/mypy/`uv lock --check` 通过。旧 pilot 的实际根因仍未知，不能把新诊断字段倒推为旧请求原因。

## 实现范围

- 新增 `memory_version=v3_spatial_event`，仅用于 `agent=memory`；默认仍为 v2。v2 的 reducer、renderer 与既有 trace provenance 保持兼容。
- v3 状态仅由公开 Observation、已校验 Action 和 ToolResult 更新：记录当前房间、episode 内全部已观察到的访问房间、有向可见出口、成功移动边和成功公开因果事件。Frontier 排除已访问目标和已走通的同向边；反向边独立保留。
- v2 的 12 项访问地点列表是有损短列表；v3 另保留上限 64 的 episode 访问房间集合，避免已进入房间因短列表容量而被误判成 frontier。
- 记忆渲染上限为 12,000 字符。超限按固定顺序省略旧普通事实、失败摘要和 v2 短访问列表，并记录 omission counts；影响导航语义的 v3 房间/出口/边/事件超过数量或字符预算时，在下一次 provider 请求前失败，不静默淘汰。
- Trace 可选地记录累计 insertions、updates、invalidations、compactions、rendered_chars 和字符估算 token 数。初始背包项、事实、失败动作、问题、revealed items、访问房间、出口、成功边和事件纳入 insertions；背包/current room/里程碑状态、问题解决或变化、重复事件纳入 updates；显式事实失效单独计入 invalidations，M1 为 0。兼容用的 v2 `visited_locations` 不重复计数。`rendered_chars` 和估算 tokens 记录最近一次渲染值，历史 trace 缺少统计字段时仍可读取。

## 离线验证

2026-10-13，在隔离的 Python 3.13 临时环境执行：

| 检查 | 结果 |
|---|---|
| `ruff check .` | 通过 |
| `mypy src` | 通过，48 个源文件 |
| `pytest -q` | 316 passed |
| Trace audit | 518 个文件，474 个唯一 episode，44 个重复副本；派生 CSV/JSON 已加入内存统计列，历史 trace 中携带该字段的 episode 为 0 |

2026-10-13 随后加入跨 invocation 的 fail-closed provider budget guard，首次检查为 329 passed。独立复审后增加 expected provider、OS request/invocation leases、跨进程锁测试、截止时间后记账、terminal ledger status 一致性、CLI 中断状态修复，以及后续 cell 身份不匹配时保留已完成汇总；Python 3.13 临时隔离环境最终检查为 Ruff 通过、mypy 通过（49 个源文件）、全量 pytest 338 passed、`uv lock --check` 与 `git diff --check` 通过。依赖文件未改动，实现提交 SHA `0a09a4f479cd8b6ba49dd0eeefed80a47d623c06` 已冻结登记；真实模型调用尚未开始。完整设计见 [spec 0015](../../specs/0015-v2-provider-budget-guard/index.md)。

2026-10-13 为复盘实际 pilot 的错误路径，将 provider budget ledger 扩为 schema 2，加入固定类别与可选 HTTP 状态码，并保留 schema-1 读取/迁移。全量 pytest 348 passed、Ruff 全仓通过、mypy 49 个源文件通过、`uv lock --check` 通过。修改后的代码用于 BUDGET-02/BUDGET-03；原始 BUDGET-01 运行仍以 SHA `0d3bb0ba0b81ca682ea714941de7b5bd17fd03f9` 为准。

2026-10-13 BUDGET-02 recovery 在 v2 seed 1 的第 10 次请求遇到 `timeout`，安全 ledger 记账 10 次 / 40,852 tokens（9 次成功 usage 合计 15,374；失败请求 reservation 25,478），v2 汇总 0/2，v3 未启动。与 BUDGET-01 合计 12 次 / 64,938 本地记账 tokens；不确定的 provider spend 不等同于实际 usage。只读配置检查得到 per-request timeout 30 秒；因此独立预登记 BUDGET-03，将此 operational timeout 调至 120 秒，其余研究条件一致，使用剩余总 cap 和原 deadline。超时发生后 S2 仍未完成，禁止推进 S3。

2026-10-13 BUDGET-03 将 per-request timeout 提至 120 秒后，第 7 次请求仍以通用 `provider_error` fail closed；前 6 次 usage 合计 10,043 tokens、失败 reservation 25,156 tokens，账本累计 7 次 / 35,199 tokens，v2 0/2、v3 未启动。三账本累计 19 次 / 100,137 本地记账 tokens，三次失败 reservation 的 provider 实际 usage 均未知。通用类别无 HTTP status，无法确定 provider 端根因。按最终预登记停止后续 provider 调用；S2 未过 Gate，不推进 S3。

定向 fixture 覆盖公开 frontier 与成功边、v3 访问集合在 v2 12 项短列表达到容量后的正确性、必需房间/出口/边/事件容量边界、事件顺序不预设、episode reset、公开前置条件修复、超限压缩与显式失败、v3 provenance/step statistics、config 兼容及旧 trace 审计读取。测试和静态检查不证明模型收益。

2026-10-13 离线验收补充：发现并补齐“完整公开 Trace 重放得到稳定 v3 memory digest”的实现缺口。`MemoryV3State.memory_digest` 对逻辑状态做排序键、紧凑 JSON 的 SHA-256，不含派生运行计数器；新增测试将 10 步公开 Trace 写入并重新读取，再独立重放两次，断言 digest、frontier、事件顺序一致。全量本地检查为 pytest 349 passed、Ruff 全仓通过、mypy 49 个源文件通过；提交 `e907237ca4c1dd4f06a48690a44a59c8568865c2` 的 [GitHub Actions run #70](https://github.com/wenxvn/Agent-Arena/actions/runs/38378309801) 通过。当前 shell 没有 `uv` 命令，未执行 `uv lock --check`；依赖文件未改动。此项只补齐离线确定性验收，不改变模型结果：三份 pilot ledger 无完整 episode，S2 Gate 仍未通过，不推进 S3。

2026-10-13 随后对 trace statistics 做容量边界复核，发现 v2 访问短列表达到 12 项后，新增的 v3 `visited_rooms` 没有计入 `insertions`。统计改为按 v3 episode 房间集合的新增项计数，并在原 frontier 容量 fixture 增加第 13 个房间的 insertion 精确断言。本地全量 pytest 349 passed、Ruff 和 mypy 49 个源文件通过；提交 `8e4217241f848887bb7040e40865db6b0a075070` 的 [GitHub Actions run #72](https://github.com/wenxvn/Agent-Arena/actions/runs/38379141983) 成功。未发起 provider 请求，S2 在线 Gate 仍未通过。

2026-10-13 继续按全部持久记忆字段审计计数口径，发现初始化未计 `revealed_items`，后续也漏计新增 open question 与题目解决、里程碑状态/current room 变化。计数口径已在 spec 0014 明确；新增回归 fixture 覆盖初始化、背包/已揭示物品、失败动作/问题创建、修复后问题解决与重复事件更新。修正后本地全量 pytest 350 passed、Ruff 全仓和 mypy 49 个源文件通过；当前提交的远端 Actions 待验证。无 provider 请求。

## Pilot 决策

候选比较为 `lunar_escape_v2_seeded` 的 seed 1、2，Memory v2 与 v3 配对，每局 100 decisions，E1 ON / H5 / R1 / P2(world-declared) 条件固定，串行运行。共享预算、输出 cap、deadline、ledger 和执行命令见 registry；每次请求发出前均预留，本地预算超限或 provider error 时 fail closed。计划指标为 first-recorded attempt、Success@60/100、动作数、重复边/动作、输入/输出 Token、token/success、provider_error 和延迟。world identity hash 为 `bd1f77eabdcd032e80dbbaaad29163e85cbea34caf7486c22babcb3b85cb8373`；原 pilot 源代码 SHA 为 `0d3bb0ba0b81ca682ea714941de7b5bd17fd03f9`。BUDGET-01 在第 2 次请求后 unknown spend（2/500、24,086 tokens），BUDGET-02 在第 10 次请求 timeout（10/498、40,852 tokens），BUDGET-03 在第 7 次请求通用 provider_error（7/488、35,199 tokens）；三次都没有完整 episode，seed 2 和 v3 未启动。失败账本和 partial 输出不得重置、复用或覆盖。当前登记矩阵在线尝试停止，S2 仍未完成。

离线指标、源 Trace 与既有 232-action 月球长尾事实仍只支持“值得检验”的 M1 假设；没有同条件 v2/v3 完整结果，不能声称成功率、步数、重复边或 token-efficiency 改善。当前稳定 world definition hash 与旧长尾 trace 记录不同，原因仍未确认；因此旧 trace 只作假设来源，不作本轮 hash-matched 对照。BUDGET-01 根因未知；BUDGET-02 虽分类为 timeout、BUDGET-03 分类为 provider_error，provider 端实际处理/计费均未知。当前研究矩阵不再发送 provider 请求；完成 S2 Gate 前不推进 S3。
