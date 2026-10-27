# V14 最终报告（Agent Arena Lab 1.2 · Stage II Final Evidence & Delivery）

- 执行日期：2026-10-27（本地）
- 起点 HEAD：`60c9ba2b64a3bd8d5cd549a7b76d0f3eb3ad092a`
- 终点 HEAD：见 `docs/v14/progress.md` 的最后一条 commit
- **V14 真实付费执行：122 局 / 3 822 请求 / CNY 2.06710508**（方案 A + 三轮补充；2 局 unknown_spend 预留）

## 0. 结论先行

| 判定 | 是否满足 | 说明 |
|---|---|---|
| `ENGINEERING_VERIFIED` | **满足** | 1790 项离线测试、mypy/ruff、冻结与复算、V11–V14 验收、浏览器 E2E、a11y 全部通过 |
| `LIVE_EVIDENCE_VERIFIED` | **不满足（部分达成）** | 122 局真实样本：规划有强描述性收益（0/25 → 14/15）、记忆仅在 seed 2+150 请求有效（2/9 → 8/8）、反思暴露达成但效果不可测 |
| `STAGE_II_FINAL_READY` | **不满足** | 缺少 LEGIT 的 LIVE 证据分母；按提纲不得宣称收官 |

V14 的真实增量不是"再写一套工程"，而是**修掉了会误导结论的测量缺陷**，并把
"不许夸大的边界"变成可执行检查（`scripts/verify_v14.py` 14 项）。

## 1. 修掉的五个实质问题

| 编号 | 问题 | 影响 | 修正 |
|---|---|---|---|
| P0-2-a | `validity_markdown` 把缺失的 `mechanism_triggered` 渲染成 `0/N` | 六图的"机制从未触发"是**伪造的否定证据** | 三档计数 + `UNKNOWN (0 observed)` |
| P0-2-b | `live-budget-proposal.md` 逐行 221 写成 229；方案 B 写 150 局 | 预算申请不可信，可能批错额度 | 逐行复算 → 221 局 / ¥10.97；方案 B 186 局 / ¥5.60 |
| DCR-V14-01 | 历史 CSV 缺 `contract_version` / `prompt_hash` | MAP-22 的 contract-1/2 无法在数据层区分 | 按实验登记文件分组 + `POOLED_ACROSS_PROTOCOLS` 禁止合并 |
| DCR-V14-03 | `memory.v2.bottleneck()` 在 `env_write` 下用写入次数比路线长度 | 完整写入被判成"记录过短" | 分析层投影按"已写入方位数"判定（源码未改） |
| P0-3 | 配对只用 `(map, seed, agent)` | on/off 臂可能因 config hash 丢配对 | 8 元组条件身份 + 三档判定 + seed 白名单 |

## 2. 三个 v2 策略：机制证据与真实收益

> 真实执行与账本见 `docs/v14/live-report.md`；数据明细见 `docs/v14/live-results.md`。
> 一句话：**机制成立，效果未定**。
>
> | 组 | 真实结果（MiMo） | 可下的结论 |
> |---|---|---|
> | E1-a `route_log` on/off（MAP-22，20 局） | `route_recall` 0.045 → 0.557；成功 0/10 vs 0/10；费用 +25% | 机制 `SUPPORTED`；**效果无差异** |
> | E2-a `planning` on/off（MAP-16，17 局） | off 0/10；on **3/7**；3.43 次计划/局 | **描述性**，臂不完整（停批），不作结论 |
> | E3 `reflection`（MAP-22，2 局） | `triggered = 0` | `NO_TREATMENT_EXPOSURE`，不评价效果 |

### 2.1 Memory（`memory.v2`）

- 机制（SIMULATED，零请求）：被拒/非法移动**不进路线**；回到起点后记忆块与
  `env_write` 载荷都包含 `north,east,south,west`；记忆块零隐藏真值。
- 代价：`env_write` 8 决策 / 6 请求（写一次占 1 决策、0 请求）；`context_only` 7/7。
- 单因子：E1-a 只改 `route_log`（钉 `context_only`）、E1-b 只改 `route_mode`。
- **真实收益**：机制成立（`route_recall` 0.045 → 0.557）；90 请求下 **0/10 vs 0/10**，
  150 请求下 **seed 2 `2/9 → 8/8`**、seed 0/1 两臂全败；每成功局 ¥0.207 → ¥0.033。
  → **机制 `SUPPORTED`，效果是"实例 × 预算"条件性的**（DCR-V14-06/07）。

### 2.2 Planning（`planning.v2`）

- 触发链（SIMULATED）：`initial → repeated_rejection（被 TTL 延迟）→ no_progress → public_progress`。
- 成本：Planner 请求与动作请求同属 `requests`（adaptive 15 请求 / 3 次 Planner），
  `disabled` 12 请求 / 0 次 Planner；预算守卫与 `max_plans` 两条挡下路径都有证据。
- 单因子：E2-a `enabled`、E2-b `planning_mode`、E2-c 频率（4→12）。
- **真实收益**：两个独立父实验合并，off **0/25**（全部 `NODE_CAPACITY_CONFLICT`，多在 3–13 决策内）、
  on **14/15 有效局**（7 局截尾为请求上限）；每成功局 ¥0.0498。
  → **强描述性收益**；仍需跨图、跨模型复现，且采样未登记 → 不作因果断言。

### 2.3 Reflection（`reflection.v2`）

- 六态：`eligible` / `triggered` / `blocked_cooldown` / `blocked_quota` /
  `false_triggers` / `recoveries`；`reflection_on` 12 决策里真触发 3 次、恢复 2 次。
- `trigger_only`：暴露 9 次但 0 请求（证明触发判定本身不注入提示）。
- 全程有进度的脚本 → `NO_TREATMENT_EXPOSURE`，**不写成"反思无效"**。
- **真实收益**：MAP-22 两局 `triggered = 0` → `NO_TREATMENT_EXPOSURE`（DCR-V14-04）；
  离线诊断 MAP-19/20/29 后换 MAP-19 → **on 臂 3/9 局真触发**（暴露达成），
  但两臂 0/9 成功（全部 `THERMAL_RUNAWAY`）→ **效果 `NOT_MEASURABLE`**。

## 3. 负面结果与保留项（不修饰）

1. **真实效果证据仍不完整**：规划只有单模型单图（需泛化）；记忆只有 seed 2 生效；
   反思虽已能触发，但选中的图对 MiMo 是地板 → 三条都不能写成"策略普遍有效"。
2. **六图机制触发仍全部 UNKNOWN**：V12 CSV 没有该字段。这不是"0 次触发"，
   也不能用 V13 的 `map-validity.md` 原表（已修正并加注）。
3. **V12 三组消融都不能做效果结论**：6 对全部 `DESCRIPTIVE_ONLY`
   （缺 `contract_version` / `prompt_hash`），可比对 0，独立 seed 各 2 个。
4. **MAP-30 只有第一档能明确归因**：90 请求档 8/8 撞满请求上限；
   180 请求与 600k token 两档的 5 局/7 局截尾**公开终态码没有暴露撞哪一维**，
   标 `UNSPECIFIED`，不强行归因。
4. **`failure_recovery` 维度 `UNAVAILABLE`**：V12 没有 MAP-05/19/20 的逐局数据，
   不填 0 分。
5. **候选图 MAP-19/20/29 不能断言更好**：V12 无该三图数据 → `NEEDS_MORE_EVIDENCE`。
6. **CI 门禁切换后出现过一次真实红灯**（`40477841302`）：根因是本轮新加的 E2E
   断言用固定 sleep 判断渲染时序。失败 run 保留在 `ci-evidence.md`，修复后连续成功。
7. **外部账单未对**：`NO_EXTERNAL_BILL_PROVIDED`，不冒充已对账。
8. **本机 Playwright 自带 chromium 未装成**（CDN 受限）：`AGENT_ARENA_E2E_BROWSER=chromium`
   的本地复现路径标 `NOT_VERIFIED`。

## 4. 19 项状态

见 `docs/v14/gap-audit.md`。汇总：

- **15 项 `DONE`**；
- **P0-4 / P0-5** 机制与真实运行均完成，但效果证据不足（零差异 / 臂不完整）；
- **P0-6** `NO_TREATMENT_EXPOSURE`（零干预）；
- **1 项**（P2-6）本地 `DONE`、外部账单 `BLOCKED_EXTERNAL`。

## 5. 复现方式

```bash
uv sync --extra web
uv run agent-arena web                  # 单机 Lab（无 Key，SIMULATED 全流程）
uv run python scripts/verify_v14.py     # 14 项 V14 事实边界
uv run python scripts/audit_v14_data.py --write
uv run python scripts/audit_v14_agents.py --write
uv run python scripts/audit_v14_maps.py --write
uv run python scripts/audit_v14_failures.py --write
uv run python scripts/audit_v14_engineering.py --write
uv run python scripts/plan_v14_live.py --check
uv run python scripts/e2e_lab.py --start --port 8512
```

## 6. 建议

1. **不要**在未批准的情况下进入第三阶段结论；当前只能交付"工程可信 + 真实效果待测"。
2. LIVE 已执行 122 局 / ¥2.0671（各阶段上限内）：
   - 最值得做的是**验证 `planning.v2` 的泛化**（MAP-18/17 + 第二个模型）；
   - `route_log` 需补 seed 3 与更多重复，确认"实例依赖"是否稳定；
   - `reflection` 应换到"能成功但会卡"的图（如 MAP-16）做 trigger_only→on 单因子。
3. 下一轮应当**先**给 trace 补上 `contract_version` 与 `prompt_hash`（DCR-V14-01），
   否则跨版本分析仍然只能靠文件名猜测。
4. MAP-30 若要继续，优先提高**请求上限**（第一档瓶颈是请求数），而不是继续抬 token。