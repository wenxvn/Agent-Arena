# 失败归因分层

- 局数：16；诊断条目：82
- 规则：主层按 PROVIDER > INTERFACE > MEASUREMENT > BUDGET > MECHANISM > POLICY 优先；接口与测量问题永远不算进能力分母。

## 主层分布

| 层 | 含义 | 局数 |
|---|---|---:|
| `INTERFACE_CONTRACT` | 接口/契约问题（不是能力） | 0 |
| `MEASUREMENT_COVERAGE` | 测量覆盖问题（不是能力） | 6 |
| `BUDGET_CENSORED` | 预算截尾（没测完） | 10 |
| `ENVIRONMENT_MECHANISM` | 环境机制真实触发但未达成 | 0 |
| `POLICY_BEHAVIOUR` | 策略可观察行为 | 0 |
| `PROVIDER` | Provider/基础设施 | 0 |
| `UNKNOWN` | 证据不足 | 0 |

## 逐局归因（带证据锚）

| run_id | 地图 | 实验臂 | 主层 | 证据步 | 摘要 |
|---|---|---|---|---|---|
| `web-20261026T144054Z-fb5d5229` | MAP-22 | `basic.v1` | `MEASUREMENT_COVERAGE` | 1, 2, 3, 4, 5, 6, 7, 8 | 主层 测量覆盖问题（不是能力）；共 4 条证据级诊断。 |
| `web-20261026T144054Z-25d1215c` | MAP-22 | `memory.v2` | `BUDGET_CENSORED` | 1, 2, 3, 4, 5, 6, 7, 8 | 主层 预算截尾（没测完）；共 2 条证据级诊断。 |
| `web-20261026T144054Z-451a2005` | MAP-22 | `planning.v2` | `MEASUREMENT_COVERAGE` | 1, 2, 3, 4, 5, 6, 7, 8 | 主层 测量覆盖问题（不是能力）；共 4 条证据级诊断。 |
| `web-20261026T144055Z-255381b5` | MAP-22 | `reflection.v2` | `MEASUREMENT_COVERAGE` | 1, 2, 3, 4, 5, 6, 7, 8 | 主层 测量覆盖问题（不是能力）；共 4 条证据级诊断。 |
| `web-20261026T144055Z-fd283beb` | MAP-22 | `basic.v1` | `MEASUREMENT_COVERAGE` | 1, 2, 3, 4, 5, 6, 7, 8 | 主层 测量覆盖问题（不是能力）；共 4 条证据级诊断。 |
| `web-20261026T144055Z-4d021b7b` | MAP-22 | `memory.v2` | `BUDGET_CENSORED` | 1, 2, 3, 4, 5, 6, 7, 8 | 主层 预算截尾（没测完）；共 2 条证据级诊断。 |
| `web-20261026T144055Z-dfea524c` | MAP-22 | `planning.v2` | `MEASUREMENT_COVERAGE` | 1, 2, 3, 4, 5, 6, 7, 8 | 主层 测量覆盖问题（不是能力）；共 4 条证据级诊断。 |
| `web-20261026T144056Z-f634b5e2` | MAP-22 | `reflection.v2` | `MEASUREMENT_COVERAGE` | 1, 2, 3, 4, 5, 6, 7, 8 | 主层 测量覆盖问题（不是能力）；共 4 条证据级诊断。 |
| `web-20261026T144056Z-e737b57b` | MAP-16 | `basic.v1` | `BUDGET_CENSORED` | 1, 2, 3, 4, 5, 6, 7, 8 | 主层 预算截尾（没测完）；共 7 条证据级诊断。 |
| `web-20261026T144056Z-9f6bd097` | MAP-16 | `memory.v2` | `BUDGET_CENSORED` | 1, 2, 3, 4, 5, 6, 7, 8 | 主层 预算截尾（没测完）；共 7 条证据级诊断。 |
| `web-20261026T144057Z-fc7ec835` | MAP-16 | `planning.v2` | `BUDGET_CENSORED` | 1, 2, 3, 4, 5, 6, 7, 8 | 主层 预算截尾（没测完）；共 8 条证据级诊断。 |
| `web-20261026T144057Z-28f84b93` | MAP-16 | `reflection.v2` | `BUDGET_CENSORED` | 1, 2, 3, 4, 5, 6, 7, 8 | 主层 预算截尾（没测完）；共 5 条证据级诊断。 |
| `web-20261026T144057Z-32cd5ef2` | MAP-16 | `basic.v1` | `BUDGET_CENSORED` | 1, 2, 3, 4, 5, 6, 7, 8 | 主层 预算截尾（没测完）；共 7 条证据级诊断。 |
| `web-20261026T144058Z-56506dc4` | MAP-16 | `memory.v2` | `BUDGET_CENSORED` | 1, 2, 3, 4, 5, 6, 7, 8 | 主层 预算截尾（没测完）；共 7 条证据级诊断。 |
| `web-20261026T144058Z-83a5ca73` | MAP-16 | `planning.v2` | `BUDGET_CENSORED` | 1, 2, 3, 4, 5, 6, 7, 8 | 主层 预算截尾（没测完）；共 8 条证据级诊断。 |
| `web-20261026T144059Z-4864ee44` | MAP-16 | `reflection.v2` | `BUDGET_CENSORED` | 1, 2, 3, 4, 5, 6, 7, 8 | 主层 预算截尾（没测完）；共 5 条证据级诊断。 |
