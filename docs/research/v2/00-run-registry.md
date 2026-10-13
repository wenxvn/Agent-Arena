# V2 在线运行登记表

本登记表先记录计划与门禁状态；每次真实 provider API 尝试（包括失败、重试和格式修正请求）都必须新增一行。不得把单次 benchmark episode 误当成一次 API 请求。

## S2 M1 pilot 预登记

| experiment_id | 条件 | 地图 / seed | budget | 计划 provider / model | API 尝试 | 状态 |
|---|---|---|---:|---|---:|---|
| EXP-V2-S2-M1-V2-S1 | Memory v2 baseline；E1 ON / H5 / R1 / P2(world-declared) 固定 | `lunar_escape_v2_seeded` / 1 | 100 decisions | 按 V2 提纲 Muse；本机配置尚未核验 | 0 | blocked：预算硬门禁未实现 |
| EXP-V2-S2-M1-V2-S2 | Memory v2 baseline；E1 ON / H5 / R1 / P2(world-declared) 固定 | `lunar_escape_v2_seeded` / 2 | 100 decisions | 按 V2 提纲 Muse；本机配置尚未核验 | 0 | blocked：预算硬门禁未实现 |
| EXP-V2-S2-M1-V3-S1 | Memory v3 spatial/event；其他条件与 v2 配对 | `lunar_escape_v2_seeded` / 1 | 100 decisions | 按 V2 提纲 Muse；本机配置尚未核验 | 0 | blocked：预算硬门禁未实现 |
| EXP-V2-S2-M1-V3-S2 | Memory v3 spatial/event；其他条件与 v2 配对 | `lunar_escape_v2_seeded` / 2 | 100 decisions | 按 V2 提纲 Muse；本机配置尚未核验 | 0 | blocked：预算硬门禁未实现 |

## 门禁与解除条件

- 截至 2026-10-13，新增真实模型调用为 0；本机 `.env` 未读取，provider、model、凭据与远端限额均未核验。
- 当前 Agent Loop 有 episode 决策步数上限；Ollama provider 有单请求 `num_predict` 上限。但 OpenAI-compatible 与 Bailian 决策请求没有统一的单请求输出上限，所有 provider 也没有共享的跨 episode API 请求数/token 预留器。usage 字段可能缺失，故仅在 response 后累计 usage 不能构成硬预算。
- 因此不启动以上四个 planned cell。解除条件：实现 fail-closed 的全局 request/token 预算器；对选定 provider 的每次请求设置输出上限；在发请求前预留输入上界和输出上限；对 missing usage、重试及 correction request 采用可审计计数；并通过非计费 fake-provider 测试与一次明确登记的受限网关探针验证所选 gateway 确实接受限制。
- Gate 打开后，先冻结 git SHA、模型/配置、prompt hash、地图定义 hash、seed 语义、并发 1、单局 100 decisions、全局超时和总 request/token caps；执行过程中触顶即停止，不扩样本。

| experiment_id | request cap | token cap | global timeout | concurrency | 实际 API 尝试 |
|---|---:|---:|---:|---:|---:|
| EXP-V2-S2-M1 pilot | 未设置（阻塞） | 未设置（阻塞） | 未设置（阻塞） | 1（计划值） | 0 |

本表是预登记，不代表实验已运行或模型条件已核验。
