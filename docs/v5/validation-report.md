# V5 离线验收报告

状态：39 局矩阵和 MAP-30 完整历史条件已实现并通过本机离线验证；扩展矩阵第二模型复核为 Approve，无未解决发现。还须在提交后的 HEAD 上执行完整冻结门禁，随后才可发起真实 API smoke。当前没有真实 API pilot 请求。最终冻结 hash 以 ignored `runs/v5/frozen_offline_gate.json` 为准。本文仅记录本机实际验证；Oracle 与求解结果都属于离线环境证据。

## 门禁范围

冻结 offline gate 将运行代码、provider adapter、Action/Observation schema、提示词、V4 六图源材料、条件/前缀、测试、用户提供的 V5 提纲、规格和 map source hash 绑定到当前 Git HEAD。以下任一项变化都要重新运行 gate：代码或测试、依赖 lock、设计输入、提示词、矩阵/前缀、provider 协议。

Gate 命令：

```powershell
.\.venv\Scripts\python.exe scripts\freeze_v5_offline_gate.py
```

## 实际离线结果（2026-10-16，提交前）

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
- V5 唯一 paid pilot registry 的定向只读查询当前为 `None`，尚未登记真实 run。一次离线输入测量另留下 ignored `runs/temporary-review-only.jsonl`；它仅含一条 `pilot_created`（model=`offline-fake-v5`），没有请求预留/结算或 episode，位于正式 `runs/v5/` registry 之外，不可作为真实 pilot ledger 恢复或复用。
- 全仓 Ruff 仍有已知 baseline 问题：`ruff check . --statistics` 报 653 项（601 项 E501 等），集中于原有手写 MAP planning 参考材料；本任务不改写这些设计材料。冻结门禁只对 `src scripts tests` 运行 scoped Ruff，并运行完整 pytest。

上述 511 项和其余检查在修复提交前执行；冻结脚本将在新 HEAD 上原样重跑全部门禁并保存准确输出/hash。离线冻结门禁通过前不会执行 Stage B 付费 smoke。真实 pilot 结果、usage、费用和最终 episode 数只从唯一 V5 ledger 与生成报告读取。
