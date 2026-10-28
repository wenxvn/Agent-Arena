# V14 第二阶段探索收尾声明

- 收尾日期：2026-10-28
- 收尾 HEAD：`d11bd9773931`（V14 全部工作已推送）
- Tag：`v14-stage2-exploratory-complete`
- 执行者：Pi Agent（DeepSeek V4.1 Flash 通道）
- 用户决定：明确要求收尾；并由用户接受下文 §4 列出的 3 项非阻断例外

## 1. 收尾结论（一句话）

**第二阶段的“阶段性探索”到此收尾：工程可信、研究问题被回答、结论边界写清。
但“最终实证”（`STAGE_II_FINAL_READY`）不成立，且本文件不宣称它成立。**

| 判定 | 状态 | 说明 |
|---|---|---|
| `ENGINEERING_VERIFIED` | ✅ **满足** | 19/19 项有可核查证据；10 项门禁全绿；CI 连续 24 次阻断门禁成功 |
| **阶段性探索完成**（`EXPLORATORY_COMPLETE`） | ✅ **满足** | 3 个 v2 策略均有真实数据 + 机制证据 + 负向结果 + DCR，且无一条是“看起来成功”的假结论 |
| `LIVE_EVIDENCE_VERIFIED` | ⚠️ **部分**（用户已接受例外） | 308 局真实数据；但配对全为 `DESCRIPTIVE_ONLY`、外部账单未对 |
| `STAGE_II_FINAL_READY` | ❌ **不满足** | 缺“显著性/因果级”证据与外部账单核对；不因收尾而改写 |

## 2. 收尾时的事实基线（可复算）

| 项 | 值 | 来源 |
|---|---|---|
| 真实 MiMo 执行 | **308 局 / 10 034 请求 / CNY 5.55809328** | `docs/v14/live-results.json` |
| 父实验 | 43 | 同上 |
| 账本完整性 | started 308 = settled 308；**0 重复结算、0 孤儿** | 同上 |
| 未知消费 | 4 局（`unknown_spend`，按预留保留、**未重试**） | DCR-V14-05 |
| 离线测试 | **1791 passed** | `docs/v14/validation-report.md` |
| 类型/规范 | `mypy src` 334 文件 0 issues；`ruff check .` clean | 同上 |
| 冻结校验 | freeze 9/9 unchanged；recompute 1093/1093；independent 0 违规 | 同上 |
| 验收脚本 | `verify_v11` 7/7、`verify_v12` 15/15、`verify_v13` 18/18、**`verify_v14` 15/15** | 同上 |
| 浏览器 | `e2e_lab` 通过（含 V14 新断言）；`a11y` 浅/深色 0 critical/serious/moderate | 同上 |
| 远端 CI | `lab-e2e` 为**阻断**门禁，切换后**连续 24 次成功** | `docs/v14/ci-evidence.md` |

## 3. 这一阶段真正立住的 4 条研究结论

### 3.1 规划（`planning.v2`）：唯一可复现的正向结论

| 地图 | 模型 | 关闭 | 开启 | 备注 |
|---|---|---:|---:|---|
| MAP-16 | `mimo-v2.6-flash` | 0/25 | **14/22** | 7 局截尾（请求上限），不计作失败 |
| MAP-16 | `mimo-v2.6-pro` | 2/12 | **12/12** | 含**留出 seed 3**：`0/3 → 3/3` |
| MAP-18 | flash | 2/9 | 4/9 | 方向一致、幅度小 |
| MAP-26（天花板） | flash | 9/9 | 9/9 | **无增益也无损害** |
| MAP-14（推理地板） | flash | 0/9 | 0/9 | **救不回来** |

失败模式可解释：`off` 臂在 MAP-16 上 25 局全部 `NODE_CAPACITY_CONFLICT`，
`pro` 在留出 seed 上 **2–3 次决策即 `DEADLOCK`**。成本：每成功局 ¥0.021–0.050。

**边界**：单机制（会车/侧线/重调度）× 2 模型；缺“规划有害”的对照图。

### 3.2 记忆（`memory.v2 route_log`）：瓶颈是“记了不用”，不是“记不住”

- 90 请求：两臂 0/10；150 请求：seed 2 **2/9 → 8/8**，seed 0/1/3 两臂全 0。
- 公开轨迹归因（65 局）：写入在所有 seed 都成功（`route_recall` 0.19–1.0），
  但**只有 seed 2 的折返数下降**（16.4 → 5.0）。
- **负向实验**：`route_write_every` 2→1 把 recall 提到 **0.977**，折返数不降（28.0 vs 25.2）、成功 0/9。
- 结论：**记录可用性不是瓶颈，策略是否据此行动才是**（DCR-V14-08/09）。

### 3.3 MAP-22 的失败来自移动预算，不是请求预算

最优解只需 10–14 步，但公开移动预算是 **44 步**；150 请求档的失败局仍以
`MOVE_BUDGET_EXHAUSTED` 结束（决策 46–70）→ 抬请求上限不延长可走步数（DCR-V14-06）。

### 3.4 反思（`reflection.v2`）：暴露已解决，效果无可检出差异

| 轮次 | 结果 |
|---|---|
| MAP-22 @90（Pilot） | `triggered = 0` → `NO_TREATMENT_EXPOSURE`（DCR-V14-04） |
| MAP-19 @90（换图，先离线诊断 8/9/9 次触发） | on 臂 3/9 局触发，但两臂 0/9（该图为地板） |
| MAP-22 @150，n=13/臂 | 3/13 vs 7/13（当时误读为“方向性正向”） |
| **MAP-22 @150，n≈33–36/臂（最终）** | **16/36 (44.4%) vs 15/33 (45.5%)，Fisher p = 1.0** |

**自我更正（DCR-V14-10）**：n=13 的“正向”是噪声，已改为 `NO_DIFFERENCE`。
该样本量足以检出 54% vs 23% 量级效应（约需 37/臂），所以“未重现”本身有信息量；
要排除 15 个百分点内的效应需约 170 局/臂。

## 4. 用户已接受的 3 项非阻断例外

| # | 例外 | 状态标签 | 为什么不阻断 |
|---|---|---|---|
| 1 | Provider 后台账单未提供 | `BLOCKED_EXTERNAL` / `NO_EXTERNAL_BILL_PROVIDED` | 本机账本自洽（308/308、0 重复、0 孤儿、¥5.55809328 按登记价目表）；仅缺外部交叉核对 |
| 2 | MiMo 采样支持未登记，配对全为 `DESCRIPTIVE_ONLY` | `UNKNOWN`（`SamplingProvenance.support`） | 结论已按“描述性”表述，未宣称因果；这是能力边界而非缺陷 |
| 3 | 效果结论不是“涨点” | `LIVE_EVIDENCE_VERIFIED` 部分 | 提纲明确 `LIVE_EVIDENCE_VERIFIED` **不要求策略涨点**，只要求分母合法、可比性与机制暴露证据 |

## 5. 这一阶段修掉的 6 个实质缺陷（都是“会误导结论”的）

| 编号 | 缺陷 | 影响 |
|---|---|---|
| P0-2-a | `validity_markdown` 把缺失的 `mechanism_triggered` 渲染成 `0/N` | 六图“机制从未触发”是伪造的否定证据 |
| P0-2-b | `live-budget-proposal.md` 逐行 221 写成 229；方案 B 写 150 局 | 预算申请不可信（已改为 221 局 / ¥10.97，B 186 局 / ¥5.60） |
| DCR-V14-01 | 历史 CSV 缺 `contract_version` / `prompt_hash` | MAP-22 跨契约无法在数据层区分 → `POOLED_ACROSS_PROTOCOLS` 禁止合并 |
| DCR-V14-03 | `memory.v2.bottleneck()` 在 `env_write` 下用写入次数比路线长度 | 完整写入被判成“记录过短” |
| V14 配对口径 | `condition_comparison` 把 effective `prompt_hash` 当硬不匹配 | on/off 臂全被判 `INCOMPARABLE`（LIVE 时才暴露）→ 改比 `base_prompt_hash` |
| DCR-V14-10 | n=13 的二项对比被当作方向性证据 | 已在扩大样本后自我更正 |

## 6. 明确的“未做 / 不能做”（不许含糊）

1. **不做第三阶段结论**：没有新策略版本、没有第二个模型家族、没有显著性级证据。
2. **不给架构排名**：V12 起的所有数据都显示同条件翻转率 22–25%，本阶段没有推翻这一点。
3. **不改冻结资产**：`worlds/scenario_v8`、`v10/runtime`、V8/V9/V10 账本与历史 trace 全程未改。
4. **不补的外部项**：macOS 实机、Ollama、真机读屏、Provider 后台账单 —— 按用户指示暂缓或环境不可得。
5. **不把 SIMULATED 当效果证据**：所有 SIMULATED 结果在文档里都标了模式。

## 7. 第三阶段候选清单（供下一轮决定，本阶段不启动）

按“能改变结论 / 成本”排序：

| 优先级 | 候选 | 为什么值得做 | 预估成本 |
|---|---|---|---|
| P0 | **策略侧修“记了不用”**：给 `memory.v3` 加显式“按记录返程”子目标 | 唯一已知的真实瓶颈（DCR-V14-08/09 已证明配置层修不好） | 工程为主 + 每臂 ≥10 局验证 |
| P0 | **第二个模型家族验 planning** | planning 是唯一强信号，目前只有 MiMo 两个档位 | 4 图 × 2 臂 × 3 seed ≈ ¥1 |
| P1 | **负向对照补“规划有害”图** | 现缺“off 能成功、on 反而变差”的实例 | 需先离线筛图（零费用）+ 18 局 |
| P1 | **trace 落 `contract_version` / `prompt_hash`** | DCR-V14-01 的根因；不修则跨版本分析永远靠文件名猜 | 工程小改 + 回填脚本 |
| P2 | 反思功效补到 170 局/臂 | 只有在“必须排除 15pp 内效应”时才值得 | ≈ ¥8+ |
| P2 | MAP-30 请求上限优先扩容 | 第一档瓶颈已确认为请求数 | 需新预算档批准 |

## 8. 复现入口（外部可重跑）

```bash
# 工程与事实边界（零外部请求）
uv run python scripts/verify_v14.py --report runs/v14/selfcheck.json
uv run pytest -q
uv run ruff check . && uv run mypy src

# 冻结与历史复算
uv run python -m agent_arena.v10.freeze verify
uv run python -m agent_arena.v10.recompute --check
uv run python -m agent_arena.v10.independent_check --check

# V11–V14 验收
uv run python scripts/verify_v11.py
uv run python scripts/verify_v12.py
uv run python scripts/verify_v13.py
uv run python scripts/verify_v14.py

# LIVE 数据的只读复算（需要本机 runs/v14/live，已在 .gitignore）
uv run python scripts/summarize_v14_live.py --write
uv run python scripts/analyze_v14_map22.py --write

# 浏览器（无 API Key）
uv run --with playwright python scripts/e2e_lab.py --start --port 8512
```

期望：`verify_v14` 15/15；pytest 1791 passed；freeze unchanged；recompute 1093/1093；
independent 0 违规；v11/v12/v13 = 7/15/18；E2E `{"ok": true}`。

## 9. 文档索引

| 文件 | 内容 |
|---|---|
| `docs/v14/README.md` | 版本入口与状态 |
| `docs/v14/final-report.md` | 实际结果、负面结果、剩余问题 |
| `docs/v14/live-report.md` | 真实 MiMo 执行报告（308 局） |
| `docs/v14/live-results.md` / `.json` | 逐组/逐 seed 数据明细 |
| `docs/v14/map22-instances.md` | MAP-22 实例差异归因（公开轨迹） |
| `docs/v14/gap-audit.md` | 19 项逐项状态 |
| `docs/v14/release-checklist.md` | 交付验收清单 |
| `docs/v14/decisions.md` | D-V14-001…005、DCR-V14-01…10 |
| `docs/v14/validation-report.md` | 全部实际运行的命令与结果 |
| `docs/v14/ci-evidence.md` | 远端 CI 逐条证据（24 次连续成功） |
| `docs/v14/experiment-protocol.md` | 可比性、重复、门禁、批准边界 |
| `docs/v14/data-validity.md` / `pairing-audit.md` / `budget-audit.md` / `validity-diff.md` | 数据口径复算 |
| `docs/v14/agent-studies.md` | 三个 v2 策略的机制证据 |
| `docs/v14/map-audit.md` | MAP-30 三维阶梯与候选图 |
| `docs/v14/failure-and-capability.md` | 锚点、能力缺口、结论强度 |
| `docs/v14/engineering-boundaries.md` | 性能、异常负载、导出、SDK、账本 |
| `docs/v14/live-plan.md` | 方案 A 预注册（后续阶段的预算模板） |
| `docs/v14/screenshots/` | 7 张真实浏览器截图 |
