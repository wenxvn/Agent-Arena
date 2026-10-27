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
