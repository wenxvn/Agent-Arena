# V14 验证记录

> 只记录**实际运行**的命令与输出摘要。失败保留原样，不事后修饰。
> 平台：Windows 11 + Git Bash（MSYS2）；本地启动器 `python 3.11.9`，项目解释器由 `uv` 固定为 3.13。

## 0. 基线（Batch 0，2026-10-27，HEAD `60c9ba2`）

| 命令 | 结果 |
|---|---|
| `uv lock --check` | 通过 |
| `uv run ruff check .` | 通过 |
| `uv run mypy src` | 323 files，0 issues |
| `uv run pytest -q` | **1639 passed**，122.25s |
| `uv run python -m agent_arena.v10.freeze verify` | 全部 `unchanged` |
| `uv run python -m agent_arena.v10.recompute --check` | 1093/1093 match，30 maps |
| `uv run python -m agent_arena.v10.independent_check --check` | 0 violations，144 seed instances |
| `uv run python scripts/verify_v11.py` | 7/7 |
| `uv run python scripts/verify_v12.py` | 15/15 |
| `uv run python scripts/verify_v13.py` | 18/18 |

远端：`lab-e2e` 连续 7 次 `success`（见 `ci-evidence.md`）。

## 1. Batch 1（P0-2，2026-10-27）

| 命令 | 结果 |
|---|---|
| `uv run python scripts/audit_v14_data.py --write` | 生成 4 份文档；221 局 / ¥10.97 |
| `uv run pytest -q tests/test_v14_data_validity.py` | **14 passed** |
| `uv run pytest -q tests/test_v13_*.py` | **114 passed** |
| `uv run python scripts/verify_v13.py` | 18/18 |
| `uv run ruff check <改动文件>` | 通过 |
| `uv run mypy src/agent_arena/lab/v13/validity.py src/agent_arena/lab/v14/` | 0 issues |

关键输出：

```text
records: 138
pooled_maps: [MAP-16, MAP-18, MAP-22, MAP-30]
trigger_unknown_maps: [MAP-08, MAP-16, MAP-18, MAP-22, MAP-26, MAP-30]
budget totals: runs=221 upper=103.75 estimate=9.08 recomputed=10.97
declared_total_runs: 229 -> 221（修正后一致）
plans: A 54 / B 186 / C 221
```

## 9. Batch 9–12

> 后续批次在此追加。

## 2. Batch 2（P0-3，2026-10-27）

| 命令 | 结果 |
|---|---|
| `uv run pytest -q tests/test_v14_conditions.py` | **23 passed** |
| `uv run pytest -q`（批次边界全量） | **1676 passed**，134.89s |
| `uv run ruff check .` | 通过 |
| `uv run mypy src` | 326 files，0 issues |
| `uv run python scripts/audit_v14_data.py --write` | 生成 `pairing-audit.md`，illegal_seeds = [] |

配对复核实测（只读历史）：

```text
memory.v1 消融      pairs=2 comparable=0 descriptive=2 incomparable=0 single_switch=true
planning.v1 消融    pairs=2 comparable=0 descriptive=2 incomparable=0 single_switch=true
reflection.v1 消融  pairs=2 comparable=0 descriptive=2 incomparable=0 single_switch=true
```

## 3. Batch 3（P0-4，2026-10-27）

| 命令 | 结果 |
|---|---|
| `uv run pytest -q tests/test_v14_agent_studies.py` | **17 passed** |
| `uv run python scripts/audit_v14_agents.py --write` | 生成 `agent-studies.md` / `.json` |
| `uv run ruff check src/agent_arena/lab/v14/` | 通过 |
| `uv run mypy src/agent_arena/lab/v14/` | 0 issues |

SIMULATED 机制结果（零请求）：

```text
context_only_on   decisions=7 requests=7 route=north,east,south,west rejected=1 invalid=1 render=7
context_only_off  decisions=7 requests=7 route=(empty)  bottleneck=NO_RECORD
env_write_on      decisions=8 requests=6 route=north,east,south,west write_accepted=2 route_recall=1.0
disabled          decisions=7 requests=7 render=0 bottleneck=DISABLED
memory_block_leaks = []（全部臂）
all_single_factor = true
plan: 36 局 / PLANNED_ONLY / 实验费用上限 ¥5.00
```

## 4. Batch 4（P0-5，2026-10-27）

| 命令 | 结果 |
|---|---|
| `uv run pytest -q tests/test_v14_planning_study.py` | **14 passed** |
| `uv run python scripts/audit_v14_agents.py --write` | 生成 Planning 段 |
| `uv run ruff check .` | 通过 |
| `uv run mypy src` | 328 files，0 issues |
| `uv run pytest -q`（批次边界全量） | **1707 passed**，178.23s |

SIMULATED 触发链（12 决策脚本，零请求）：

```text
adaptive     requests=15 planner=3 plans=3 ttl_skip=1 triggers=[initial, no_progress, public_progress]
initial_only requests=13 planner=1 plans=1
periodic_4   requests=15 planner=3
periodic_12  requests=13 planner=1
disabled     requests=12 planner=0
budget_guard ttl_skip=4 budget_skip=2 planner=3
max_plans    plans=2（封顶）
plan: 72 局（MAP-16 主测 54 + MAP-18 对照 18）/ PLANNED_ONLY
```

## 5. Batch 5（P0-6，2026-10-27）

| 命令 | 结果 |
|---|---|
| `uv run pytest -q tests/test_v14_reflection_study.py` | **15 passed** |
| `uv run ruff check .` | 通过 |
| `uv run mypy src` | 329 files，0 issues |
| `uv run pytest -q`（批次边界全量） | **1722 passed**，189.79s |

SIMULATED 六态（12 决策，零请求）：

```text
disabled        requests=12 triggered=0 exposure=DISABLED
trigger_only    requests=12 triggered=9 reflection_requests=0 exposure=TREATMENT_TRIGGERED
reflection_on   requests=15 triggered=3 cooldown_blocked=6 recoveries=2
long_failure_on requests=15 triggered=3 quota_blocked=1 recoveries=3
no_trigger_on   triggered=0 exposure=NO_TREATMENT_EXPOSURE
plan: 27 局（两臂子集 18）/ PLANNED_ONLY
```

## 6. Batch 6（LIVE 方案 A 预注册，2026-10-27）

| 命令 | 结果 |
|---|---|
| `uv run python scripts/plan_v14_live.py --check` | `PLANNED_ONLY`，54 局，¥2.11，上界 ¥27.00，6 规格 |
| `uv run python scripts/plan_v14_live.py --write` | 生成 `live-plan.md` / `.json` |
| `uv run pytest -q tests/test_v14_live_plan.py` | **10 passed** |
| `uv run ruff check .` / `uv run mypy src` | 通过 / 330 files 0 issues |
| `uv run pytest -q`（批次边界全量） | **1732 passed**，139.72s |

```text
groups: E1-a(MAP-22, route_log) / E2-a(MAP-16, enabled) / E3(MAP-22, 组合对照)
runs: 54  estimate: 2.11  upper: 27.00  recommended_cap: 5.00
all_single_factor: true   all_seeds_valid: true   external_requests: 0
```

## 7. Batch 7（P1-1 + P1-2，2026-10-27）

| 命令 | 结果 |
|---|---|
| `uv run python scripts/audit_v14_maps.py --write` | 生成 `map-audit.md` / `.json` |
| `uv run pytest -q tests/test_v14_map_audit.py` | **12 passed** |
| `uv run ruff check .` / `uv run mypy src` | 通过 / 331 files 0 issues |
| `uv run pytest -q`（批次边界全量） | **1744 passed**，226.10s |

```text
six_map_labels: 08 CEILING / 16,18,22 SUITABLE / 26 CEILING / 30 CENSORED（全部 DESCRIPTIVE_ONLY）
map30_axes: req=90 REQUESTS(8/8) / req=180 UNSPECIFIED / req=180+600k UNSPECIFIED
map30_intervals: [113,155] / [111,155] / [334,460]
candidates: MAP-19/20/29 → NEEDS_MORE_EVIDENCE（V12 无该三图数据）
```

## 8. Batch 8（P1-3 + P1-4 + P1-6，2026-10-27）

| 命令 | 结果 |
|---|---|
| `uv run pytest -q tests/test_v14_failure_capability.py` | **16 passed** |
| `uv run python scripts/audit_v14_failures.py --write` | 生成 `failure-and-capability.md` / `.json` |
| `uv run ruff check .` / `uv run mypy src` | 通过 / 332 files 0 issues |
| `uv run pytest -q`（批次边界全量） | **1760 passed**，185.15s |

```text
fixtures: REJECTED_NO_PROGRESS(POLICY, 可进) / PROGRESS_THEN_BUDGET_CENSORED(不可进) / INTERFACE_ARTEFACT(不可进)
capability: information_gathering/memory_tracking/planning_replanning/resource_constraints/evidence_reasoning AVAILABLE
            failure_recovery UNAVAILABLE（V12 无 MAP-05/19/20 数据）
conclusion: INSUFFICIENT / NO_TREATMENT_EXPOSURE / NOT_MEASURABLE
```

## 9. Batch 9（P1-5 + P2-3，2026-10-27）

| 命令 | 结果 |
|---|---|
| `uv run pytest -q tests/test_v14_ui_views.py` | **12 passed** |
| `uv run --with playwright python scripts/e2e_lab.py --start --port 8514` | `{"ok": true, v14_map22_view: true, v14_first_divergence: true, v13_stability_page: true, v13_audit_page: true, v13_sdk_selfcheck: true}` |
| `uv run --with playwright python scripts/a11y_v12.py --browser --start` | 浅色/深色 critical=0 serious=0 moderate=0；theme_ok=true |
| `uv run --with playwright --with streamlit python scripts/capture_v14_screenshots.py` | 7 张截图写入 `docs/v14/screenshots/` |
| `uv run ruff check .` / `uv run mypy src` | 通过 / 333 files 0 issues |
| `uv run pytest -q`（批次边界全量） | **1772 passed**，160.43s |

截图清单（全部 SIMULATED、脱敏、临时目录数据）：

```text
01-lab-result-gate.png          可比性门禁 + 实验臂汇总
02-lab-map22-exploration.png    MAP-22 探索：被拒移动不画成路径
03-lab-first-divergence.png     双轨迹首次分歧高亮
04-lab-seed-groups.png          按 seed 分组的重复结果 + 六图效度
05-lab-stability-mobile.png     430px 窄屏
06-lab-result-dark.png          深色模式
07-lab-audit.png                报告与审计
```

## 10. Batch 10（P2-1，2026-10-27）

| 项 | 结果 |
|---|---|
| 切换前远端证据 | `lab-e2e` 连续 7 次 success |
| 切换后第一次运行 `40477841302` | `quality` success / `lab-e2e` **failure**（新断言时序问题，保留） |
| 修复后运行 `40482235016` | `quality` success / **`lab-e2e` success**（门禁阻断生效） |
| 本地 `e2e_lab.py --start --port 8516 --report runs/v14/e2e-report.json` | `{"ok": true, ...}` |
| 本地 `a11y_v12.py --browser --start` | critical/serious/moderate 全 0 |
| 本地 chromium 复现（`AGENT_ARENA_E2E_BROWSER=chromium`） | `NOT_VERIFIED`（CDN 下载受限） |

## 11. Batch 11（P2-2 / P2-4 / P2-5 / P2-6，2026-10-27）

| 命令 | 结果 |
|---|---|
| `uv run python scripts/audit_v14_engineering.py --write` | 生成 `engineering-boundaries.md` / `.json` |
| `uv run pytest -q tests/test_v14_engineering.py` | **18 passed** |
| `uv run ruff check .` / `uv run mypy src` | 通过 / 334 files 0 issues |
| `uv run pytest -q`（批次边界全量） | **1790 passed**，207.14s |

```text
cold_first_open 277.19 ms / warm_page_first_50 0.03 ms / warm_index_rebuild 40.91 ms
损坏 manifest：通过（索引 5 局，坏 manifest 不入统计）
并发读写：40 轮 0 异常
TTL：3 → 4 → 4
长历史导出：1000/1000 行
导出一致性：runs 4 / metrics 22 / paired 2 / findings 15，问题 0
SDK：8 项 V13 + 3 项 V14 全部通过
账本：159/159、5641 请求、¥5.43680012、0 重复、0 孤儿（与 V13 记录一致）
外部账单：NO_EXTERNAL_BILL_PROVIDED
```

## 12. Batch 12（P2-7，2026-10-27）

| 命令 | 结果 |
|---|---|
| `uv run python scripts/verify_v14.py --report runs/v14/selfcheck.json` | **14/14 通过**（`ok: true`，`failed: []`） |
| `uv run ruff check .` | 通过 |
| `uv run mypy src` | 334 files，0 issues |
| `uv run pytest -q` | **1790 passed** |

CI 变更：`quality` job 新增 `V14 Lab 1.2 离线验收` 步骤（`scripts/verify_v14.py`）。

## 13. Batch 13（LIVE 执行，2026-10-27）

| 命令 | 结果 |
|---|---|
| `bash scripts/verify_model.sh` | 模型 `mimo-v2.6-flash` 验证成功（1 次极小请求） |
| `uv run python scripts/run_v14_live.py --pilot ... --submit` | 6 局完成，¥0.1441，0 unknown |
| `uv run python scripts/run_v14_live.py --groups E1-a E2-a ... --submit` | 33 局后因 `unknown_spend` 停批 |
| `uv run python scripts/summarize_v14_live.py --write` | `live-results.md/.json` |
| 账本 | 39/39 started=settled、1 313 请求、¥0.72437412、0 重复、0 孤儿 |
| `uv run pytest -q tests/test_v14_conditions.py` | **24 passed**（含 2 条新增干预口径测试） |
| `uv run python scripts/verify_v14.py` | 14/14 |
