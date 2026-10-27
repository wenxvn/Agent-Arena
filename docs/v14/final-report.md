# V14 最终报告（Agent Arena Lab 1.2 · Stage II Final Evidence & Delivery）

- 执行日期：2026-10-27（本地）
- 起点 HEAD：`60c9ba2b64a3bd8d5cd549a7b76d0f3eb3ad092a`
- 终点 HEAD：见 `docs/v14/progress.md` 的最后一条 commit
- **V14 新增真实付费请求：0**（未获用户对模型 / 矩阵 / 总费用上限的批准）

## 0. 结论先行

| 判定 | 是否满足 | 说明 |
|---|---|---|
| `ENGINEERING_VERIFIED` | **满足** | 1790 项离线测试、mypy/ruff、冻结与复算、V11–V14 验收、浏览器 E2E、a11y 全部通过 |
| `LIVE_EVIDENCE_VERIFIED` | **不满足** | 没有新的真实模型样本；三个 v2 策略的真实收益仍是 `LIVE_PENDING` |
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

### 2.1 Memory（`memory.v2`）

- 机制（SIMULATED，零请求）：被拒/非法移动**不进路线**；回到起点后记忆块与
  `env_write` 载荷都包含 `north,east,south,west`；记忆块零隐藏真值。
- 代价：`env_write` 8 决策 / 6 请求（写一次占 1 决策、0 请求）；`context_only` 7/7。
- 单因子：E1-a 只改 `route_log`（钉 `context_only`）、E1-b 只改 `route_mode`。
- **真实收益：`LIVE_PENDING`**。

### 2.2 Planning（`planning.v2`）

- 触发链（SIMULATED）：`initial → repeated_rejection（被 TTL 延迟）→ no_progress → public_progress`。
- 成本：Planner 请求与动作请求同属 `requests`（adaptive 15 请求 / 3 次 Planner），
  `disabled` 12 请求 / 0 次 Planner；预算守卫与 `max_plans` 两条挡下路径都有证据。
- 单因子：E2-a `enabled`、E2-b `planning_mode`、E2-c 频率（4→12）。
- **真实收益：`LIVE_PENDING`**。

### 2.3 Reflection（`reflection.v2`）

- 六态：`eligible` / `triggered` / `blocked_cooldown` / `blocked_quota` /
  `false_triggers` / `recoveries`；`reflection_on` 12 决策里真触发 3 次、恢复 2 次。
- `trigger_only`：暴露 9 次但 0 请求（证明触发判定本身不注入提示）。
- 全程有进度的脚本 → `NO_TREATMENT_EXPOSURE`，**不写成"反思无效"**。
- **真实收益：`LIVE_PENDING`**。

## 3. 负面结果与保留项（不修饰）

1. **六图机制触发仍全部 UNKNOWN**：V12 CSV 没有该字段。这不是"0 次触发"，
   也不能用 V13 的 `map-validity.md` 原表（已修正并加注）。
2. **V12 三组消融都不能做效果结论**：6 对全部 `DESCRIPTIVE_ONLY`
   （缺 `contract_version` / `prompt_hash`），可比对 0，独立 seed 各 2 个。
3. **MAP-30 只有第一档能明确归因**：90 请求档 8/8 撞满请求上限；
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
- **3 项**（P0-4 / P0-5 / P0-6）工程完成、真实收益 `LIVE_PENDING`；
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
2. 若要补 LIVE：从方案 A（54 局 / ¥2.11 预估 / ¥5.00 上限）开始，先 Pilot 确认
   `reflection_triggered > 0`、`usage` 可结算、无异常拒绝。
3. 下一轮应当**先**给 trace 补上 `contract_version` 与 `prompt_hash`（DCR-V14-01），
   否则跨版本分析仍然只能靠文件名猜测。
4. MAP-30 若要继续，优先提高**请求上限**（第一档瓶颈是请求数），而不是继续抬 token。