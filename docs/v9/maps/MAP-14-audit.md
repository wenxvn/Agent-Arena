# MAP-14 逐图审计（说谎的祭司）

## 0. 元数据

| 项 | 值 |
|---|---|
| 地图 / 世界 / 难度 | `MAP-14` / pyramid / 中等 |
| condition | `default` |
| `rule_hash` | `1c352a0fd891f588c267746134491cfdd74c53489846547b4754d2d1154b80a2` |
| `scenario_hash` | `61267f92369922d2d30914a51cf765ff6cc500fe18845137751827b0fa7393d0` |
| `prompt_hash` | `e7bd106cf4984266d975356902274932050725e1c012bf9f058dfe0de0327806` |
| `metric_schema_hash` | `87e805885613bafae1ce9f81dd0fbf78611589ba6439449d65cde98a956f6673` |
| 决策预算 | 38 |
| V8 三局 | 0/3 成功；三局全部 `decision_budget_reached`，各 38 步，`termination_reason=None` |

| rep | run_id | status | 决策 | `queries_used` | `globally_consistent_hypothesis_rate` | `minimum_query_gap` | `contradiction_missed` | `query_budget_overruns` |
|---|---|---|---|---|---|---|---|---|
| 0 | `V8-MAP-14-R0-20261017T084136Z-c801fa6a` | decision_budget_reached | 38 | 0 | 0/0 → N/A | 0 | 0 | 0 |
| 1 | `V8-MAP-14-R1-20261017T084459Z-a2091da8` | decision_budget_reached | 38 | 0 | 0/0 → N/A | 0 | 0 | 0 |
| 2 | `V8-MAP-14-R2-20261017T084729Z-e554717a` | decision_budget_reached | 38 | 0 | 0/0 → N/A | 0 | 0 | 0 |

数据来源：`runs/v9/evidence/MAP-14.json`、`docs/v9/run-index.csv`、`docs/v8/maps/MAP-14-final.md`、`worlds/v4/MAP-14/{map_spec.yaml,evidence_or_rules.yaml,acceptance.md,oracle_trace.jsonl}`、`src/agent_arena/worlds/scenario_v8/maps/map14.py`、`runs/v9/baselines/MAP-14.json`、三局 `judge_metrics.json`。

> 证据管线限制（本图尤重）：`src/agent_arena/v9/evidence.py::_compact_action` 的保留字段白名单不含 `claim_id`，证据包里三局的 `ask` 动作全被写成 `{"tool": "ask"}`，无法看出问的是哪条命题。本审计的 `ask` 动作引用一律取自原始 `agent_trace.jsonl`（`{"claim_id": "A1", "tool": "ask"}`），并已在 §7 标注。这是 V9 证据层的缺陷，不是 V8 行为。

## 1. 能力构念

一句话：在"只有一名祭司如实、其余两人逐命题反报"的有限真值结构下，用不超过 4 次提问把"锁型 × 诚实者"九态假设收敛到可提交的锁型，并在审判门承担最终验证。

- 成功行为：`GATE_OPENED`。注意成功**只由锁型决定**，与是否正确指认诚实者无关（fixture `correct_lock_with_wrong_priest_still_opens_gate`）。
- 明确反例：
  - 把答案当字面真值（不建模说谎者）；
  - 只凭一次提问或档案直接提交；
  - 在第 5 问上继续尝试（会被拒且不耗 tick，属无效动作而非失败）。
- 同世界递进位置：pyramid 的**中等档**。它比 MAP-13（全真静态约束）多了两层：信息不可靠（真假证词）与信息需要主动获取（问询预算）；比 MAP-15 少了"规则随相位变化"。本图是三图里唯一同时含"不可靠信息 + 主动查询"的关卡。

## 2. 机制与因果链

本图专属因果链：

```
起始 P（tick 0，六张命题卡可见：A1 A2 / B1 B2 / C1 C2）
  → 关键决策①：在 P 用 ask(claim_id) 提问（每人两条固定命题，只有答 yes/no）
  → 关键决策②：移动到 A 执行 read_archive → 公开 ARCHIVE_NOT_C（排除锁型 C）
  → 关键决策③：移动到 O 执行 compare_evidence(choice, person_id, support) → 只封存假设，无对错反馈
  → 关键决策④：移动到 J 执行 submit_configuration(choice) → 正确则 GATE_OPENED，错误计 1 次
  → 终局：GATE_OPENED / WRONG_SUBMISSION_LIMIT（第 2 次错交）
```

位置绑定（源码硬约束，**prompt 未公开**）：`ask` 仅 P（`map14.py:270`）、`read_archive` 仅 A（`map14.py:252`）、`compare_evidence` 仅 O（`map14.py:288`）、`submit_configuration` 仅 J（`map14.py:318`）。越界一律返回 `TARGET_NOT_VISIBLE`。

- 可以绕过核心机制的动作：
  - `compare_evidence` 完全不参与成功判定且不返回信息，**可以整局省略**（消融 `no_compare` 9 步仍 `GATE_OPENED`）。
  - `ask` 也可以整局省略：3 种锁型 + 1 次错交容错 ⇒ **盲交两种锁型有 2/3 概率开门**。实测 `blind_two_submissions` 在正式 seed 0 上 **5 步通关**（决策 4 交 A 被拒不致命，决策 5 交 B 开门）。
  - 档案只排除 C，等价于把 3 选 1 变成 2 选 1，不构成必要条件（`adaptive_without_archive` 8 步也能成功）。
- 机制在三条轨迹中的实际触发：
  - `ask`：**0/3 触发**（三局 `queries_used=0`；另有 3 次 `ask` 在错误的房间被拒）。
  - `compare_evidence`：**0/3 触发**（三局 `comparison_record=null`、`sealed_hypotheses=[]`）。
  - `read_archive`：2/3 成功（R0 决策 27、R2 决策 34；R1 两次都在错误房间，`archive_read=false`）。
  - `submit_configuration`：0/3 成功触发（R2 决策 17 在 P 提交 → `TARGET_NOT_VISIBLE`）。
- 触发所需最小动作数：11（Oracle 带档案）或 8（Oracle 不带档案）；公开启发式 10；规则盲的盲交路径 5。

## 3. 公开/隐藏信息矩阵

| 信息 | 模型是否可见 | 何时可见 | 是否足以合法解题 |
|---|---|---|---|
| 六条命题文本 `public_statement_cards` | 是 | 仅在 P（其他房间为空） | 是（文本即命题） |
| `question_answers[{claim_id, speaker, answer}]` | 是 | 每次成功 `ask` 后 | 是（原始答案） |
| `archive_record_if_read` | 是 | A 处 `read_archive` 后 | 部分（只排除 C） |
| `questions_used` / `questions_remaining` | 是 | 每步 | 是 |
| `comparison_record` | 是（回显自己封存的假设） | `compare_evidence` 后 | 否（无反馈） |
| `wrong_submissions_remaining` | 是 | 每步 | 部分（语义歧义见 §6） |
| system prompt：动作名与形状、"最多问 4 条命题、最多错交 1 次" | 是 | 开局 | 形状层面 |
| **"恰有一名祭司如实、另两人逐命题反报"** | **否（未公开）** | 永不在 prompt/Observation 出现 | 只能从场景名"说谎的祭司"猜 |
| 位置绑定（ask@P / archive@A / compare@O / submit@J） | **否（未公开）** | 只能靠 `TARGET_NOT_VISIBLE` 反推 | 可试错发现 |
| `configuration` / `truthful_priest` / 真值表 / `minimum_queries` | 否 | 永不 | 不需要（可由答案推） |
| Oracle 路径、指标 id | 否 | 永不 | — |

两条关键结论：

1. 本图的核心推理规则**未公开**。`map14.py` 的模块 docstring 与 `worlds/v4/MAP-14/map_spec.yaml` 的 `truth_rule` 都写明"恰一名如实、其余逐命题反报"，但 V8/V9 的 system prompt 只写了"在审判门提交正确锁型；整局最多问 4 条命题，最多错交 1 次"。公开侧唯一线索是场景标题「说谎的祭司」。因此"从公开信息导出九态一致假设"这一步在当前接口下**不成立**，只能靠先验猜规则或走盲交旁路。
2. 位置绑定同样未公开，且它是三局浪费决策的直接原因（§7）。

## 4. 可解性与可观察性

- Oracle：2 个用例（`archive_then_ask` 11 步、`adaptive_without_archive` 8 步），`oracle_ok=2/2`。
- **仅凭公开信息**是否存在可执行策略：
  - 严格读：不存在"能导出唯一锁型"的公开策略，因为真假规则未公开（见 §3）。这在能力构念上属 B 类缺口。
  - 但存在不依赖该规则的可行策略：`submit(A) → submit(B)`，2/3 概率；正式 seed 0 的隐藏锁型是 `B_crescent`，所以这条 5 步路径**在本实例上直接成功**（`runs/v9/baselines/MAP-14.json` 的 `blind_two_submissions`，`GATE_OPENED`，5 步，0 问）。
  - 若接受"从场景名推断规则"这一先验，`public_heuristic` 在 10 步内给出唯一锁型（§5）。
- 是否存在"只有知道隐藏规则才能避免秒失败"：不成立。三局都没有秒失败（0 次错交），失败形态是**从不使用关键动作**。
- 因此：不是 `INTERFACE_BLOCKED`（盲交路径可通），也不是 `BUDGET_BLOCKED`（10 步 vs 38 步）。

## 5. 预算可行性

| 对象 | 步数 | 结果 |
|---|---|---|
| Oracle `archive_then_ask` | 11 | `GATE_OPENED` |
| Oracle `adaptive_without_archive` | 8 | `GATE_OPENED` |
| `public_heuristic`（档案 + 2 问 + 比对 + 提交） | 10 | `GATE_OPENED`，`rate=1.0`，`queries_used=2` |
| 消融 `no_compare` | 9 | `GATE_OPENED`，`rate` N/A |
| 消融 `blind_two_submissions` | 5 | `GATE_OPENED`，0 问 |
| `legal_random` 20 seed | 全部 38 | 0/20 成功 |
| MiMo R0 / R1 / R2 | 38 / 38 / 38 | 0 / 0 / 0 |

`legal_random` 分布：20 seed 全部 `decision_budget_reached`、38 步；`invalid_actions=150`、`rejected_actions=459`；`queries_used` 0–2（中位 1）；`globally_consistent_hypothesis_rate` **20/20 N/A**（`compare_evidence` 的 `support_evidence_ids` 被采样成字符串，形状必被拒，随机基线永远无法封存假设）。

判定：**不是预算不够，是模型没做对**。38 步是 10 步解法的 3.8 倍；即使完全不做推理，盲交也在第 5 步结束。三局把 89%（R0 34/38）的决策花在 P→A→O→J 的往返移动上，从未在正确位置发出 `ask`。

补充的"信息增益"核算（回答"查询与比较是否真的提供信息增益"）：

- `ask`：有增益，且是**唯一**有反馈的机制。9 个隐藏状态在 6 条命题上的答案码可区分；给定档案时，**2 个问题**（如 B1+B2）即可唯一定出锁型；不用档案时需要 4 问。本实例（`B_crescent/B_priest`）要唯一确定完整九态需 **3 问**（judge `minimum_queries=3`）。4 问预算充足。
- `compare_evidence`：**零信息增益**。源码返回 `HYPOTHESIS_SEALED_WITHOUT_JUDGMENT`，不校验、不返回剩余候选数，只回显调用方自己写入的候选。它测的是"代理是否愿意把假设写下来"，不是推理质量。

## 6. 指标

| 指标 | kind | 公式（登记） | 分母 | 三局取值 | 状态 |
|---|---|---|---|---|---|
| `map14.globally_consistent_hypothesis_rate` | primary | consistent_hypotheses / submitted_hypotheses | 封存假设数 | 0/0 | `not_applicable`（三局） |
| `map14.minimum_query_gap` | primary | queries_used − minimum_queries(instance) | 实例最少问询数 | 0 | `valid` |
| `map14.queries_used` | diagnostic | count(ask) | episode | 0 | `valid` |
| `map14.query_budget_overruns` | guardrail | count(QUERY_BUDGET_EXCEEDED) | episode | 0 | `valid` |
| `map14.contradiction_missed` | diagnostic | 1 if submit contains known contradiction else 0 | episode | 0 | `valid` |

- 计算事件：`metrics()` 只读 `sealed_hypotheses`、`answers`、`submissions`、`counters`，没有独立 extractor。
- **未通关仍有意义的连续主指标**：只有 `queries_used`（但它的方向是 lower_is_better，见下）。`globally_consistent_hypothesis_rate` 在"从不比对"时没有任何取值，`minimum_query_gap` 在"从不提问"时被夹到 0。
- **三局主指标全 N/A 的原因**：`globally_consistent_hypothesis_rate` 的分母是 0，**真分母为 0**（三局 `sealed_hypotheses=[]`），不是投影口径问题。V9 的重投影（`runs/v9/rescore/MAP-14.json`）对它没有做任何改动，三局 `changed={}`。
- 三个可复现的指标缺陷：
  1. **`minimum_query_gap` 的下限把"欠问"变成最优**。实现是 `max(0, len(answers) - minimum_queries)`。R0 的 judge 里 `minimum_queries=3`、`answers=[]`，`0-3=-3` 被夹成 **0**，即"一个都不问"拿到 lower_is_better 指标的**最优值**。同一局 `queries_used=0` 也是 lower_is_better 的最优值。两个主/diagnostic 指标同时奖励"不问"。
  2. **`globally_consistent_hypothesis_rate` 依赖一个无反馈动作，且可被重复封存刷高**。分子按 `sealed_hypotheses` 逐条计，重复封存同一个一致假设只会让分母与分子同步增长（率恒 1.0）；它无法区分"推理正确"与"把已知答案抄一遍"。同时 23/23 非启发式 episode（20 随机 + 3 MiMo）都取不到值，说明该指标在真实运行中基本不可用。
  3. **`contradiction_missed` 在"从不提交"时恒为 0**，三局的 0 是**空真**，不含信息。
- 区分能力：成功维度上，盲交（5 步、0 问）与真推理（10 步、2 问）都是 `GATE_OPENED`；`rate` 上盲交 N/A、启发式 1.0；`queries_used` 上盲交 0 优于启发式 2。也就是说现有指标把"不问就猜中"排得**不差于**"问对了再交"。属 `LOW_DISCRIMINATION`（对推理与盲猜不可分）。

## 7. 三次轨迹归因

### R0（`...-c801fa6a`，38 步，预算耗尽）

- 决策 1：`{"edge_id": "P_A", "tool": "move"}` → `MOVED:A`，`{"location": "A", "public_statement_cards": {}, "tick": 1, "visible_edges": ["A_O", "P_A"]}`。
- 决策 2：`{"edge_id": "P_A", "tool": "move"}` → `MOVED:P`——到了档案所在的 A，**没有读档案就立刻折返**。
- 决策 3：`{"tool": "read_archive"}` → `TARGET_NOT_VISIBLE`，`{"tick": 3}`（人在 P）。
- 决策 27：`{"tool": "read_archive"}` → `ARCHIVE_NOT_C`，`{"archive_record_if_read": {"evidence_id": "ARCHIVE_NOT_C", "text": "星井锁C从未安装在当前审判门上。"}, "tick": 27}`。
- 决策 28：`{"claim_id": "A1", "tool": "ask"}` → `TARGET_NOT_VISIBLE`，`{"tick": 28}`（人在 A，问询只在 P）。
- 决策 35：`{"claim_id": "A1", "tool": "ask"}` → `TARGET_NOT_VISIBLE`，`{"tick": 35}`。

首因/首次偏离：决策 1–3。它先用一步走到 A（档案就在那），再用一步离开，然后在 P 尝试读档案。之后整局在 P/A/O/J 之间往返：`MOVED:A`×12、`MOVED:O`×14、`MOVED:J`×5、`MOVED:P`×3，共 34 次移动、38 个决策，**0 次提问、0 次比对、0 次提交**。它在决策 6、14、16、20、30 都到过 J（可提交）而没提交，在决策 2、11、23 都到过 P（可提问）而没提问。

失败链：位置-动作绑定错误 → 唯一有反馈的动作（`ask`）一次也没成功执行 → 没有任何证据 → 不能提交 → 预算耗尽。

替代解释：预算不足（否，10 步可解）；接口误导（部分，位置绑定未公开）；策略规划错误（主要，模型到了正确节点却不使用节点专属动作）。

### R1（`...-a2091da8`，38 步，预算耗尽）

- 决策 3：`{"edge_id": "O_J", "tool": "move"}` → `MOVED:J`。
- 决策 4：`{"edge_id": "J_O", "tool": "move"}` → `EDGE_NOT_ADJACENT`，`{"tick": 4}`（**虚构了一条反向边 id `J_O`**；真实边是 `O_J`）。
- 决策 10：`{"tool": "read_archive"}` → `TARGET_NOT_VISIBLE`（人在 P）。
- 决策 36：`{"tool": "read_archive"}` → `TARGET_NOT_VISIBLE`（人在 J）。

首因/首次偏离：决策 4 的虚构边 id，与决策 3 到 J 后不提交同源——它没有把"当前位置能做什么"当决策依据。R1 是唯一**整局没读到档案**的一局（`archive_read=false`），也是唯一 0 次 `TARGET_NOT_VISIBLE` 里含 `EDGE_NOT_ADJACENT` 的一局。38 步里 35 步是移动、2 步错位档案、1 步错边。

失败链：动作-位置不匹配 + 虚构边 id → 无证据 → 预算耗尽。

### R2（`...-e554717a`，38 步，预算耗尽）

- 决策 17：`{"choice": "A_sun_wheel", "tool": "submit_configuration"}` → `TARGET_NOT_VISIBLE`，`{"tick": 17}`（人在 P，提交只在 J）。
- 决策 34：`{"tool": "read_archive"}` → `ARCHIVE_NOT_C`，`{"archive_record_if_read": {"evidence_id": "ARCHIVE_NOT_C", "text": "星井锁C从未安装在当前审判门上。"}, "tick": 34}`。
- 决策 35：`{"claim_id": "A1", "tool": "ask"}` → `TARGET_NOT_VISIBLE`，`{"tick": 35}`。
- 决策 38：`{"claim_id": "A1", "tool": "ask"}` → `TARGET_NOT_VISIBLE`，`{"tick": 38}`。

首因/首次偏离：决策 17。这是三局里唯一一次主动提交，但发生在 P。它到过 J（决策 3、13、20、31）却不在 J 提交；读到档案（决策 34）后又在 A 连问两次（35、38）。

三局的共性：**都到过正确的节点，但都没在正确节点执行正确的动作**；三局合计 114 个决策，`ask` 成功 0 次、`compare_evidence` 0 次、`submit_configuration` 成功 0 次。R0/R2 的 4 次 `ask`（各 2 次）全部打在 A，说明模型把"证据/档案所在地"当成了"问询地"。

重复证据的限度：三局失败形态一致（移动循环 + 位置错配），但错误动作不同（R1 虚构边、R2 错位提交）。n=3 只能说明这是**系统性**位置绑定失败，不能区分个体差异与固定陷阱。

## 8. 失败分类

| 局 | 首因 | 次因 | 可信度 | 证据位置 |
|---|---|---|---|---|
| R0 | **E 策略规划错误**（到 P 不问、到 J 不交、到 A 不读） | **C 接口误导**（4 个动作的位置绑定未公开） | 高 | 决策 1–3、27–28、35 |
| R1 | **E**（虚构边 `J_O`、到 J 不提交、整局不读档案） | C（同上） | 高 | 决策 3–4、10、36 |
| R2 | **E**（在 P 提交、读档案后在 A 提问） | C（同上） | 高 | 决策 17、34–35、38 |

不采用 **D（预算/horizon）**：Oracle 8/11 步、启发式 10 步、盲交 5 步，38 步不构成约束；三局也不是"跑满 38 步但接近答案"，而是 0 次关键动作。
**B（公开信息不足）** 作为构念层问题成立（真假规则未公开），但不构成行动阻塞，故列为次生问题而非首因。

## 9. 标签

- `MEASUREMENT_VALID`：成功判定、终止码与 `decision_count` 三者一致（`docs/v9/baseline-audit.md` 的 90/90 复算），0/3 是真实失败而非统计伪影。
- `CONSTRUCT_BYPASS`：`blind_two_submissions` 以 5 步、0 问、0 比对在正式 seed 0 上 `GATE_OPENED`（`runs/v9/baselines/MAP-14.json`）。3 锁型 + 1 次容错 ⇒ 盲赢概率 2/3，本地 seed 0–8 扫描实测 6/9 成功。也就是说"证词推理"不是通关的必要条件。
- `METRIC_DEFECT`：`minimum_query_gap` 的 0 下限把欠问变成最优（R0：0 问 / `minimum_queries=3` → gap 0）；`globally_consistent_hypothesis_rate` 在 23/23 非启发式局不可用且可被重复封存刷高；`contradiction_missed` 在从不提交时空真为 0。
- `LOW_DISCRIMINATION`：现有指标无法把"盲猜中"与"推理后提交"分开，`queries_used` 甚至奖励 0 问。
- 不选 `BUDGET_BLOCKED`（10 步可解）、`INTERFACE_BLOCKED`（盲交可通）、`RULE_DEFECT`（运行时行为与 map_spec 一致）。

## 10. 最小可证伪修复（无证据不修改）

**旧公开信息**：prompt 只给动作名/形状与"最多问 4 条、最多错交 1 次"；不给真假规则，也不给位置绑定。

**证据与根因**：(a) 3/3 局从未成功 `ask`，其中 3 次 `ask` 打在 A → 位置绑定未公开；(b) 5 步盲交在正式实例上通关 → 成功判据不要求推理；(c) 两个主指标在"不问不比对"时取最优或 N/A → 指标与构念方向不一致。

- 候选 A（**补公开信息**，P1）：在 `V9_PUBLIC_ADDENDA["MAP-14"]` 增加两句——"恰有一名祭司对每个命题如实回答，另外两名对每个命题给出相反答案；`ask` 只能在 P、档案只能在 A 读取、比对只能在 O、提交只能在 J"。预期：把"猜规则 + 猜位置"从构念里剔除，三局那 9 次 `TARGET_NOT_VISIBLE`（读档 4、提问 4、提交 1）应消失；不改变规则与难度。反例/风险：prompt hash 变更，V8 90 局不能与新臂直接混算，必须记录 arm 并单列对照。
- 候选 B（**规则改动，P0，需 DCR**）：把 `wrong_submission_limit` 从 2 降到 1（错一次即失败），或把锁型从 3 种扩到 4 种。预期：盲赢概率从 2/3 降到 1/4 以下，`blind_two_submissions` 不再能过。反例/风险：改 `rule_hash`，所有 V8 Trace 不可回放，必须重跑 Oracle/fixtures/基线；且与 MAP-13/15 的"容错"叙事需要统一。
- 候选 C（**指标口径**，P1）：`minimum_query_gap` 去掉 `max(0,·)` 或把欠问直接记 `UNAVAILABLE`；`queries_used` 改为与正确性配对的效率指标（例如"达到正确锁型所用问数 / 最少问数"）；`globally_consistent_hypothesis_rate` 增加"最后一次封存 + 最终提交正确"的联合口径，并对重复封存去重。预期：盲交不再拿满分。反例/风险：跨图指标口径一致性需要 Batch 5/6 统一。
- 优先级：B（P0，直接影响构念）> A（P1）> C（P1）。**不建议加预算或加问询次数**——本图的瓶颈是"从不使用动作"，不是额度。

## 11. 基线与独立复算

`runs/v9/baselines/MAP-14.json`：

| 基线 | 成功 | 步数 | `queries_used` | `rate` | `min_gap` | `contradiction_missed` |
|---|---|---|---|---|---|---|
| Oracle ×2 | 2/2 | 11 / 8 | 3 / 3 | 1.0（fixture 值） | 0 | 0 |
| `legal_random` ×20 | 0/20 | 38（全部耗尽） | 0–2（中位 1） | 20/20 N/A | 0 | 0 |
| `public_heuristic` | 1/1 | 10 | 2 | 1/1 = 1.0 | 0 | 0 |
| 消融 `no_compare` | 1/1 | 9 | 2 | 0/0 N/A | 0 | 0 |
| 消融 `blind_two_submissions` | 1/1 | 5 | 0 | 0/0 N/A | 0 | 0 |

独立复算：

- `queries_used`：按原始 Trace 手数"结果码以 `ANSWER:` 开头的 `ask`"= **0**（R0 的 `ask` 是 `TARGET_NOT_VISIBLE`，不计入账本），与 `metrics()` 的 0 一致。
- `globally_consistent_hypothesis_rate`：judge 的 `sealed_hypotheses=[]` → 0/0 → `None`。这不是投影伪影，是真分母 0；V9 重投影对三局 `changed={}`。
- `minimum_query_gap`：judge `minimum_queries=3`、`answers=[]` → `0-3=-3` → 实现 `max(0,-3)=0`。手算暴露了 §6 的下限缺陷。
- 盲赢概率：3 种锁型、2 次提交容错 ⇒ 顺序试两种不同锁型必命中其中之一，概率 2/3；正式实例隐藏锁型为 `B_crescent`（R0/R1/R2 的 judge 都是 `B_crescent`/`B_priest`），所以 A→B 的第二次提交必中。实测 5 步 `GATE_OPENED`。
- 最少问询数：对 9 态 × 6 命题穷举答案码，最小区分集大小在 2–3 之间（本实例为 3）；带档案（排除 C）时只要 2 问即可唯一定出锁型。

判别力：成功维度 `LOW_DISCRIMINATION`（盲猜与推理同为 1）；`rate` 维度只有启发式有值；`min_gap` 与 `queries_used` 方向相反于构念。结论：本图需要 §10 的 B+C 才可能恢复区分度。

## 12. V9 状态

`NEEDS_REDESIGN`，优先级 **P0**。

一句话理由：3 锁型 + 1 次错交容错使 5 步盲交在正式实例上直接通关（2/3 盲赢），"真假证词推理"不是通关的必要条件；同时两个主指标在"不问不比对"时取最优或 N/A，无法把推理与盲猜分开。
