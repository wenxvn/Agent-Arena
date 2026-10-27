# V14 进度日志（Batch 0–12）

> 每完成一个 Batch 追加一条，记录：做了什么、跑了什么命令、结果、commit、遗留。
> 不允许把未运行的检查写成已通过。

## Batch 0 · 仓库与收口审计（P0-1）

- 基线 HEAD：`60c9ba2b64a3bd8d5cd549a7b76d0f3eb3ad092a`（与提纲建议一致）
- 工作区：仅 3 个未跟踪的用户本地提纲文件
- 门禁复跑：`uv lock --check` ✅、`ruff` ✅、`mypy src` ✅ 323 文件、`pytest -q` **1639 passed**、
  `v10.freeze verify` ✅、`v10.recompute --check` 1093/1093、`v10.independent_check` 0 违规、
  `verify_v11` 7/7、`verify_v12` 15/15、`verify_v13` 18/18
- 远端 CI 取证：REST API 取得 10 次运行，`lab-e2e` **连续 7 次 success**（详见 `ci-evidence.md`）
- 交付：`baseline-audit.md`、`ci-evidence.md`、`progress.md`、`decisions.md`、`gap-audit.md`、`validation-report.md`
- 发现的文档缺陷（转 Batch 1）：`map-validity.md` 机制触发列 `0/N`、`live-budget-proposal.md` 合计 229≠221
- commit：`docs(v14): batch 0 baseline audit and CI evidence`

## Batch 1 · P0-2 历史口径与数据契约

- 代码：`lab/v13/validity.py` 新增 `mechanism_triggered_summary()` / `format_trigger_ratio()`，
  `map_validity()` 增加 `observed_true/observed_false/unknown/observed/status/display`，
  `validity_markdown()` 全未知输出 `UNKNOWN (0 observed / N runs)`；`SUITABLE` 理由改为
  “只说明现有样本里出现成功率梯度，不证明构念效度或因果”。
- 新模块：`lab/v14/data_audit.py`（协议隔离、六图标签差异复算、预算表算术复核、单价统计）。
- 脚本：`scripts/audit_v14_data.py --write`。
- 文档：新增 `docs/v14/data-validity.md`、`data-validity.json`、`validity-diff.md`、`budget-audit.md`；
  修正 `docs/v13/map-validity.md`（加 V14 修正说明）与 `docs/v13/live-budget-proposal.md` 算术。
- 实测：`pytest tests/test_v14_data_validity.py` **14 passed**；`pytest tests/test_v13_*.py` **114 passed**；
  `verify_v13.py` 18/18；ruff/mypy 通过。
- 关键数字：逐行子局 **221**（原写 229）、方案 A **54 局 / ¥2.11**、B **186 局 / ¥5.60**、C **221 局 / ¥10.97**。
- 新 DCR：`DCR-V14-01`（历史 CSV 缺 `contract_version`/`prompt_hash`，跨契约只能按登记文件隔离）。
- commit：`fix(v14): separate UNKNOWN from zero and recheck V13 arithmetic`
