# 2026-10-28 第二阶段交付后维护审计

## 范围与结论

第二阶段已收尾（`EXPLORATORY_COMPLETE`，tag `v14-stage2-exploratory-complete`）后，
对全仓做一次只读审计 + 文档一致性维护：代码、测试、冻结资产、账本与历史 trace **未改**。

- 起始基线：`544fb905564d`，工作区干净，与 `origin/main` 同步。
- 结论：工程仍然健康（1791 pytest、mypy 334 文件 0 issues、ruff clean、门禁全绿）；
  发现的问题**全部在文档层**，集中在三类：过期状态（V13/V14 的 `WAITING_USER_APPROVAL`）、
  事实数字漂移（1790/1791、14/15 项、CI 17/18/21/24 次）、README 落后一个版本。
- 逻辑代码、测试、世界规则、冻结清单、`results/` 历史聚合均无改动。

## 1. 已修的一致性问题

| # | 文件 | 问题 | 处理 |
|---|---|---|---|
| 1 | `README.md` | 主叙事停在 V13；「`results/` 不入库」与 V14 决策相反 | 新增 V14 现状段；数据位置改为 `results/` 入库并链接 `results/README.md` |
| 2 | `README.md` | 质量门禁缺 `verify_v13` / `verify_v14`，结论仍是 V12 的 1525 passed | 补齐并改为 1791 passed / 7-15-18-15 |
| 3 | `README.md` | V13 段写「真实模型验证 `WAITING_USER_APPROVAL`」 | 改为「已由 V14 承接」并保留 V13 的 0 局史实 |
| 4 | `docs/scope/scope.md` | At a glance 表缺 V14 行 | 新增 V14 行；V13 行注明 LIVE 由 V14 承接 |
| 5 | `docs/v14/agent-studies.md` | 整篇仍写「V14 新增付费请求 0 / 全部 `LIVE_PENDING` / 本计划不得执行」 | 顶部加「已执行」横幅；§4 汇总表改为 LIVE 真实结论；历史 probe 保留 |
| 6 | `docs/v14/live-plan.md` | 预注册文件读起来像「尚未执行」 | 顶部加已执行横幅（308 局 / ¥5.55809328）并声明不构成新授权 |
| 7 | `docs/v13/README.md`、`final-report.md`、`live-budget-proposal.md` | `WAITING_USER_APPROVAL` 会被误读为「至今未测」 | 各加「已由 V14 承接」指针，不改写 V13 自己的 0 局事实 |
| 8 | `docs/architecture.md` | 模块表缺 `src/agent_arena/lab/v14/` | 补模块行与闭环第 5 条 |
| 9 | `docs/v14/README.md`、`release-checklist.md`、`final-report.md`、`gap-audit.md` | `1790 passed`、`verify_v14` 14 项 | 统一为 1791 passed / 15 项 |
| 10 | `docs/v14/ci-evidence.md` | 连续成功计数停在 21 次 | 补 3 条真实 run（`40653998531` / `40660424924` / `40666398316`）→ 24 次 |
| 11 | `研究总纲.md`、`AGENTS.md`、`docs/scope/scope.md`、`stage2-closure.md` | CI 计数写成 22 / 18 / 17 / 17 | 统一为 24 次（截至 `40666398316`） |
| 12 | `docs/v14/validation-report.md` | 缺收尾后的统一复跑 | 追加第 16 节；历史批次的 14/14、1790 不回头改写 |
| 13 | `docs/engineering-log.md` | 文件前半倒序、后半正序，无说明 | 标题下加阅读顺序说明，不改排历史段落 |

## 2. 过期/冗余文件处理

| 对象 | 判定 | 处理 |
|---|---|---|
| `.v14tmp/`（59 个一次性 patch 脚本与日志） | 本地 scratch，已应用到代码并提交 | **删除**（未跟踪，不影响仓库与复现） |
| `examples/custom_agent/__pycache__/`、`scripts/__pycache__/` | 缓存 | 删除 |
| `docs/v14/*.json` 与同名 `.md` | 审计产物成对存在，脚本可复算 | 保留 |
| `docs/maintenance/2026-10-15-*.md`、`docs/reviews/2026-10-15-main.md` | 历史审计与审查记录 | 保留（历史证据，不追改） |
| `docs/v12/real-runs/`、`results/` 内重复 trace | 冻结证据 / 不同实验组各自完整副本 | 保留（删除会破坏可核对性） |
| `runs/`（487M）、`logs/`（3.8M） | 本机生成物，按 V14 决策不入库 | 保留，不清理 |
| `研究提纲/` 15 份 | 第二阶段提纲，用户要求入库 | 保留 |
| `test-preferences.json` | 有 Skill 消费者 | 保留 |
| 断链 16 处 | 全部是 `skills/` 里的模板占位符（`NNNN-title.md`、`<path>`） | 不修（模板语法，不是真链接） |

## 3. 未改动的部分（明确边界）

- 冻结资产：`worlds/scenario_v8/`、`src/agent_arena/v10/runtime/`、V8/V9/V10 账本与历史 trace。
- 代码与测试：本轮没有任何 `.py` 改动（ruff / mypy / pytest 结果与收尾时一致）。
- `results/` 入库内容：0 改动。
- 历史批次记录（`docs/v14/progress.md` 的 Batch 0–23、`validation-report.md` 的 1–15 节）：
  保留当时实测数字，只追加最终复跑。

## 4. 实际验证

| 命令 | 结果 |
|---|---|
| `uv lock --check` | 通过（65 packages） |
| `uv run ruff check .` | clean |
| `uv run mypy src` | 334 files，0 issues |
| `uv run pytest -q` | **1791 passed**，162.33s |
| `uv run python -m agent_arena.v10.freeze verify` | 9/9 unchanged |
| `uv run python -m agent_arena.v10.recompute --check` | 1093/1093，0 mismatch |
| `uv run python -m agent_arena.v10.independent_check --check` | 144 实例，0 违规；确定性 30/30；seed 互异 30/30 |
| `scripts/verify_v11.py` | 7/7 |
| `scripts/verify_v12.py` | 15/15 |
| `scripts/verify_v13.py` | 18/18 |
| `scripts/verify_v14.py` | 15/15（`external_requests: 0`） |
| 全仓 Markdown 相对链接扫描 | 628 份，0 处项目性断链（16 处为 Skill 模板占位符） |
| 远端 CI | `lab-e2e` 阻断门禁切换后连续 24 次 success |

## 5. 未验证 / 待办

- 浏览器 E2E 与可访问性审计本轮未复跑（Playwright CDN 下载受限），
  以本地最近一次通过 + 远端 CI 双 job success 为准。
- 外部 Provider 账单对账仍 `BLOCKED_EXTERNAL`（用户已接受）。
- 第三阶段候选（策略侧「按记录返程」、第二模型家族验 planning、补「规划有害」对照图、
  trace 落 `contract_version`/`prompt_hash`）**未启动**，见 `docs/v14/stage2-closure.md` §7。
