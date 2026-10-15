# V5 离线验收报告

状态：39 局矩阵和 MAP-30 完整历史条件已实现并通过本机离线验证；扩展矩阵第二模型复核为 Approve，无未解决发现。冻结门禁在运行 commit `e440cc1b599a5de4a57650f418d78b03c4746399` 通过，之后启动 MiMo 真实 smoke；首局出现 70 次 `INVALID_ACTION_SCHEMA`，第 71 个请求被中断且 usage 未知，唯一 ledger 已关闭。Stage C 未启动。停止后修改了 prompt 约束和 runner fail-fast；513 项 pytest、Ruff 和 mypy 离线验证通过，但没有再次运行 MiMo。冻结 hash 只对应真实运行时的旧 commit；本报告也保留离线加固状态，Oracle 与求解结果都属于离线环境证据。

## 门禁范围

冻结 offline gate 将运行代码、provider adapter、Action/Observation schema、提示词、V4 六图源材料、条件/前缀、测试、用户提供的 V5 提纲、规格和 map source hash 绑定到当前 Git HEAD。以下任一项变化都要重新运行 gate：代码或测试、依赖 lock、设计输入、提示词、矩阵/前缀、provider 协议。

Gate 命令：

```powershell
.\.venv\Scripts\python.exe scripts\freeze_v5_offline_gate.py
```

## 实际离线与门禁结果（2026-10-16）

- `python -m pytest -q`：511 passed。
- 相关控制与运行时用例：`python -m pytest tests/test_v5_pilot_controls.py tests/test_scenario_v4_runtime.py -q`，45 passed。
- `python -m mypy src`：79 source files, success。
- `python -m ruff check src scripts tests`：通过。
- `python scripts/validate_v4_runtime.py`：Oracle/参考回放计数 MAP-08 4、MAP-16 2、MAP-18 3、MAP-22 1、MAP-26 2、MAP-30 3。MAP-22 使用 DCR 记录的合法观测路径，没有把原 Oracle 未来地图记忆交给 Agent。
- `python scripts/validate_v5_solvers.py`：MAP-08 signature/entropy、MAP-16 BFS 最短 6 tick、MAP-18 timetable 与延误差、MAP-22 图距离、MAP-26 备件恢复、MAP-30 证据依赖独立检查均通过。
- 39 局矩阵 Fake dry-run：6 个预登记 smoke episode、6 个 Fake 决定；无付费请求、无持久实验目录。预算计算为 CNY ¥37.49888 / ¥37.50，或 USD $5.2498432 / $5.25；全局上限 3,662 次请求和 33,748,992 token reservation。
- MAP-30 A/B/C 对照输入：合法问询解锁身份后，A/C 均可读取 `MARA_VENN` 和同一证据事实；固定前缀的解锁前视图及 gap 后 B 不含该标识。完整历史请求界为 7,880 bytes，追加一个决策记录后为 7,985 bytes，均低于 8,192。
- MiMo adapter Fake SDK 输入检查：两个 MAP-18 条件在 tick 0–4 捕获 10 个真实 adapter 请求，不含未来闭塞区段/时间；V5 Responses kwargs 不含未文档化 `store`。这不是网络或计费测试。
- 第二模型只读代码复审：此前 36 局版本及本次 39 局扩展版均为 Approve。扩展版复核发现并促成修复 Stage B 剩余局数、MAP-30 合法问询的结构化 evidence、及 episode manifest 的条件策略字段；终审无待处理项，记录见 [`docs/reviews/2026-10-15-main.md`](../reviews/2026-10-15-main.md)。
- `git diff --check`：提交前已通过。`pyproject.toml` 与 `uv.lock` 相对 HEAD 无改动；当前宿主未安装 `uv`，故 `uv lock --check` 未运行，不表述为通过。
- Pilot 停止后的离线加固验证：`pytest -q` 为 513 passed；`tests/test_v5_pilot_controls.py` 为 26 passed；`ruff check src scripts tests` 通过；`mypy src` 对 79 个源文件无问题。新增测试覆盖完整顶层 JSON 字段约束和三次连续 schema 拒绝时 fail-closed；未通过这些 Fake/离线结果宣称 MiMo 修复成功。
- 冻结 offline gate 在 commit `e440cc1b599a5de4a57650f418d78b03c4746399` 通过，hash 为 `664e2d1210f77c30a5fe486ac8d80808f4c0f71a10a2b35311b7f866dabe6813`。当时 HEAD 与门禁 commit 一致；其后加入真实运行记录及离线 prompt/fail-fast 加固，当前源码不等于本次 MiMo 运行源码，任何未来 paid run 都必须先重新冻结并重新登记。
- 唯一正式 V5 pilot `d3f3d7be-c928-4433-b6aa-9a269d97f593` 使用 `mimo-v2.6-flash`、CNY 预算。70 个 settled response 全部在运行时产出 `INVALID_ACTION_SCHEMA`；第 71 个 reservation 在进程中断时未结算，ledger 写入 `UNKNOWN_SPEND_AFTER_INTERRUPTED_REQUEST` 并关闭。0/39 episode 完成、六局 smoke gate 未通过、Stage C 未启动。真实请求与费用见 [`pilot-report.md`](pilot-report.md) 和 ignored run artifacts；不可恢复或创建 successor ledger。
- Trace 仅保存安全 Action 与校验结果，不保存原始模型文本；因此实际 schema 失败的精确原因仍未知。MiMo Structured Output 文档要求完整定义字段层级和类型，并建议提供示例；运行时使用的旧 V5 system prompt 顶层对象示意使用省略号，已在运行后修正为明确字段约束，但尚未确认该处是根因（[官方文档](https://mimo.mi.com/docs/en-US/quick-start/usage-guide/text-generation/structured-output)）。
- 一次离线输入测量另留下 ignored `runs/temporary-review-only.jsonl`；它仅含一条 `pilot_created`（model=`offline-fake-v5`），没有请求预留/结算或 episode，位于正式 `runs/v5/` registry 之外，不可作为真实 pilot ledger 恢复或复用。
- 全仓 Ruff 仍有已知 baseline 问题：`ruff check . --statistics` 报 653 项（601 项 E501 等），集中于原有手写 MAP planning 参考材料；本任务不改写这些设计材料。冻结门禁只对 `src scripts tests` 运行 scoped Ruff，并运行完整 pytest。

511 项和其余冻结门禁检查在模型运行前对 commit `e440cc1` 执行并通过；513 项和其余离线加固检查在 pilot 关闭后执行。真实 pilot 的请求、usage 和费用只按唯一 V5 ledger 记录；1 个未结算 reservation 的实际扣费未知。文档区分两个源码状态，不把此次停止或离线修复表述为模型能力结论。
