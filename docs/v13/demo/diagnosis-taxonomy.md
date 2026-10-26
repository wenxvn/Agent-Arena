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
| `web-20261026T123446Z-b2e7342b` | MAP-22 | `basic.v1` | `MEASUREMENT_COVERAGE` | 1, 2, 3, 4, 5, 6, 7, 8 | 主层 测量覆盖问题（不是能力）；共 4 条证据级诊断。 |
| `web-20261026T123446Z-e7978af1` | MAP-22 | `memory.v2` | `BUDGET_CENSORED` | 1, 2, 3, 4, 5, 6, 7, 8 | 主层 预算截尾（没测完）；共 2 条证据级诊断。 |
| `web-20261026T123446Z-5982b007` | MAP-22 | `planning.v2` | `MEASUREMENT_COVERAGE` | 1, 2, 3, 4, 5, 6, 7, 8 | 主层 测量覆盖问题（不是能力）；共 4 条证据级诊断。 |
| `web-20261026T123447Z-754d80ee` | MAP-22 | `reflection.v2` | `MEASUREMENT_COVERAGE` | 1, 2, 3, 4, 5, 6, 7, 8 | 主层 测量覆盖问题（不是能力）；共 4 条证据级诊断。 |
| `web-20261026T123447Z-f1c894b2` | MAP-22 | `basic.v1` | `MEASUREMENT_COVERAGE` | 1, 2, 3, 4, 5, 6, 7, 8 | 主层 测量覆盖问题（不是能力）；共 4 条证据级诊断。 |
| `web-20261026T123447Z-48306370` | MAP-22 | `memory.v2` | `BUDGET_CENSORED` | 1, 2, 3, 4, 5, 6, 7, 8 | 主层 预算截尾（没测完）；共 2 条证据级诊断。 |
| `web-20261026T123448Z-1a2c4524` | MAP-22 | `planning.v2` | `MEASUREMENT_COVERAGE` | 1, 2, 3, 4, 5, 6, 7, 8 | 主层 测量覆盖问题（不是能力）；共 4 条证据级诊断。 |
| `web-20261026T123448Z-07c6c351` | MAP-22 | `reflection.v2` | `MEASUREMENT_COVERAGE` | 1, 2, 3, 4, 5, 6, 7, 8 | 主层 测量覆盖问题（不是能力）；共 4 条证据级诊断。 |
| `web-20261026T123449Z-d1e9c71c` | MAP-16 | `basic.v1` | `BUDGET_CENSORED` | 1, 2, 3, 4, 5, 6, 7, 8 | 主层 预算截尾（没测完）；共 7 条证据级诊断。 |
| `web-20261026T123449Z-78c27153` | MAP-16 | `memory.v2` | `BUDGET_CENSORED` | 1, 2, 3, 4, 5, 6, 7, 8 | 主层 预算截尾（没测完）；共 7 条证据级诊断。 |
| `web-20261026T123450Z-49e5393e` | MAP-16 | `planning.v2` | `BUDGET_CENSORED` | 1, 2, 3, 4, 5, 6, 7, 8 | 主层 预算截尾（没测完）；共 8 条证据级诊断。 |
| `web-20261026T123450Z-83e0adf3` | MAP-16 | `reflection.v2` | `BUDGET_CENSORED` | 1, 2, 3, 4, 5, 6, 7, 8 | 主层 预算截尾（没测完）；共 5 条证据级诊断。 |
| `web-20261026T123451Z-897ff62d` | MAP-16 | `basic.v1` | `BUDGET_CENSORED` | 1, 2, 3, 4, 5, 6, 7, 8 | 主层 预算截尾（没测完）；共 7 条证据级诊断。 |
| `web-20261026T123451Z-c5b47c56` | MAP-16 | `memory.v2` | `BUDGET_CENSORED` | 1, 2, 3, 4, 5, 6, 7, 8 | 主层 预算截尾（没测完）；共 7 条证据级诊断。 |
| `web-20261026T123452Z-381f9838` | MAP-16 | `planning.v2` | `BUDGET_CENSORED` | 1, 2, 3, 4, 5, 6, 7, 8 | 主层 预算截尾（没测完）；共 8 条证据级诊断。 |
| `web-20261026T123452Z-4819e893` | MAP-16 | `reflection.v2` | `BUDGET_CENSORED` | 1, 2, 3, 4, 5, 6, 7, 8 | 主层 预算截尾（没测完）；共 5 条证据级诊断。 |
