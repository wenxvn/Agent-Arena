# V2-01 CI 与基线

## 2026-10-13 CI 状态

- 最新重验：恢复登记提交 `1499888952ca79cd42dbd1c545d4e261b21cf558` 的 [run #65](https://github.com/wenxvn/Agent-Arena/actions/runs/38375201784) 与日志登记提交 `d55ce2e5da3cbd3f32c3fbc622191ef1f0c22a38` 的 [run #66](https://github.com/wenxvn/Agent-Arena/actions/runs/38375824041) 均在 `mypy src` 失败；Ruff 通过，pytest 被跳过。公开 annotations 仅报告步骤 exit 1，job log 当前要求登录/更高权限，无法读取 mypy 原始 stderr。
- 以锁定依赖创建干净临时环境后，默认 Windows 平台 `mypy --no-incremental src` 通过；`mypy --no-incremental --platform linux src` 复现 5 个错误，均为 `budget.py` 的 Linux 类型检查器无法识别 Windows-only `msvcrt` 属性。已在 Windows API 边界增加 `cast(Any, msvcrt)`，不改变运行行为；修复后 Windows 与 Linux-targeted mypy 均通过，Ruff、pytest（348 passed）、`uv lock --check` 和 `git diff --check` 均通过。实现提交 `4ec5bb1442037543f2f01656bc956f78df546e85` 对应 [run #67](https://github.com/wenxvn/Agent-Arena/actions/runs/38376965970) 的 sync、Ruff、mypy、pytest 全部通过，S0 远端 Gate 恢复为绿。
- 维护前 HEAD 为 587dccd43e1a3c39bb78c75e199bfc66ab1331e2；Actions run #54（38353317972）在 Ruff 阶段失败，共报告 25 项，mypy 与 pytest 被跳过。
- 修复提交 d9d13e4 更新 Ruff 与 mypy 暴露的问题。对应 run #55（38358108378）通过 Ruff、mypy；pytest 在 GitHub clean checkout 中有 9 项失败，根因是测试依赖本机忽略的 runs/ 与 results/ 数据。
- 补齐独立合成 fixture 后，提交 d40f3e6 对应 run #56（[GitHub Actions](https://github.com/wenxvn/Agent-Arena/actions/runs/38358490666)）的 quality job 全部通过。S0 远端 Gate 完成。
- V2 Trace 审计工具提交 a372dce 后，run #57（[GitHub Actions](https://github.com/wenxvn/Agent-Arena/actions/runs/38360270607)）的 quality job 也全部通过。该提交未改依赖锁文件。

## S0 本地质量检查

S0 修复在隔离的 Python 3.13.16 / uv 0.13.0 临时环境验证，未重建项目 .venv，也未改写 uv.lock。

| 检查 | S0 结果 |
|---|---|
| uv sync --frozen --all-groups | 通过 |
| ruff check . | 通过 |
| mypy src | 通过，48 个源文件 |
| pytest -q | 通过，303 passed |
| uv lock --check | 通过，36 个 packages 已解析 |
| git diff --check | 通过 |

S1 审计脚本增加两项离线单元测试后，当前本地质量检查复跑为 Ruff 通过、mypy 48 个源文件通过、pytest 305 passed；GitHub Actions #57 全绿。依赖未变化，uv.lock 无需更新。

2026-10-13 S2 Memory v3 离线实现增加后，Ruff 与 mypy 仍通过，pytest 为 316 passed。审计产物已重生成，仍为 518 个文件、474 个唯一 episode；当时没有真实模型调用。

2026-10-13 首次加入 S2 provider budget guard 后为 329 passed；复审修复 expected provider、活跃请求 lease、超时后记账、账本状态一致性、invocation 串行化、benchmark 非零退出及后续 cell 身份不匹配时保留已完成汇总后，Python 3.13 临时隔离环境最终验证为 Ruff 通过、mypy 49 个源文件通过、pytest 338 passed、`uv lock --check` 与 `git diff --check` 通过。实现提交 SHA `0a09a4f479cd8b6ba49dd0eeefed80a47d623c06` 已冻结登记；真实 provider 调用尚未开始。

2026-10-13 pilot 前置运行又发现 seeded flex world identity 受 `frozenset` 输出顺序影响。新增跨进程 `PYTHONHASHSEED` 稳定性修复与回归；最终 Ruff、mypy 49 个源文件、pytest 339 passed、`uv lock --check`、`git diff --check` 通过。seed 1、2 在 hash seed 1/2/3 下均为 `bd1f77eabdcd032e80dbbaaad29163e85cbea34caf7486c22babcb3b85cb8373`。两次 CLI preflight 都在 API 调用前拒绝，真实请求数为 0。修复代码提交 `0d3bb0ba0b81ca682ea714941de7b5bd17fd03f9`，已在运行登记表冻结。

## S0 修复范围

- 清理 scripts/audit_maps.py 的未使用绑定与死代码；将 scripts/build_run_register.py 的 lambda 改成局部函数。
- 修复 UI 异常链和超长行；补全 zip 长度契约，整理测试格式。
- 将世界工厂公开返回类型统一为 Environment 基类，以 WorldDefinitionLike 表达确定性环境读取的共享定义字段。
- UI 汇总只把数值型步数/token 纳入聚合，并跳过缺失或非整数的成功 seed。
- 校正研究文档中的 E1-ON 条件、首次尝试与重跑口径，并修正火山均值的难度说明；历史实测数值不变。
- 将依赖 runs/ 与 results/ 的 UI 测试改成临时目录及合成 trace/CSV，保证干净 GitHub checkout 能复现测试。

## 研究口径校正

- 9 配置的 45/45 指每个配置至少有一条成功 trace；原始记录有 46 次成功、5 次 provider_error。按全部唯一 episode_id 计为 46/51，但重跑使它不等于首次尝试稳定率。E1-ON 的 prompt hash 为 44229085。
- 新 10×3 的 150/150 指每个配置最终有成功 trace；部分有网关失败后的补跑，不表示首次尝试 150/150。
- 七个新世界中，火山困难图均值 31.4 步，低于中等图的 35.4 步；其余六图均值随难度递增。
- 本轮 S1 的 episode_id 去重和 earliest-recorded proxy 规则及删失口径见 [V2-02 既有 Trace 离线瓶颈审计](02-bottleneck-audit.md)。该审计不重算上述历史矩阵的首跑结果。

## 当前状态

截至 2026-10-13，S0 本地与远端质量门禁通过。早期基线提交 `4ec5bb1442037543f2f01656bc956f78df546e85` / Actions #67 为 348 项 pytest；当前验收夹具提交 `29d6917c8f2825b175735f92443d1692b14e843d` 本机 pytest 357 passed、Ruff 全仓和 mypy 49 个源文件通过，Actions #81 成功；文档同步提交 `a441e4c74f893425c5792524a0dbfa1e66fb55f6` 的 Actions #82 成功。S1 离线 Trace 审计为 518 个文件、474 个唯一 episode、44 个副本、0 个 ID 冲突或非法 Trace，Top 5 假设及 CSV/JSON 见 V2-02。S2 spec 0014 离线验收条件 1–6 均通过；但三次隔离在线尝试均在首个 v2 episode 失败，合计 19/500 requests、100,137/4,000,000 locally charged tokens（其中失败 reservation 不代表 provider 确认 usage），v2 0/2、v3 未启动。BUDGET-01/02/03 均关闭，当前登记矩阵停止 API 尝试；S2 matched-pilot Gate 未通过，按阶段依赖不推进 S3。细节见 [V2-03](03-memory-v3.md) 与 [在线运行登记表](00-run-registry.md)。
