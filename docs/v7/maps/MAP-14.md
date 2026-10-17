# MAP-14｜金字塔｜中等｜说谎的祭司

```yaml
map_id: MAP-14
world: pyramid
nominal_level: 中等
capability_primary: truth_logic
source_commit: 766ec82529d4ee2499dde9592452eb68592f4637
source_map_spec_hash: bbf61c4856f98d1a6e4dd623239ea5c364e2a71f7a7394e6fad4eb20c3148543
source_design_hash: 112ee6690ab21bdd4cdc8399e5818d8e73cbb7065afabfe40a2b8eabe2c057ab
design_status: DESIGN_COMPLETE_PENDING_RUNTIME
review_status: human_approved
reviewed_at: 2026-10-17
reviewed_by: human
runtime_status: design_only
metric_status: registered_design
```

## 1. 测量构念与不可替代玩法

测“真假陈述的一致性推理”。三名祭司各持两条固定命题；恰有一名**任何命题都说真话**，另外两名**任何命题都反报**。提问只返回 Yes/No，每条牌只能问一次，整局最多 4 问。Agent 要从档案、答案与“唯一诚实者”假设中确定锁型（A 日轮/B 月牙/C 星井）与诚实者，再到 J 提交。核心不是自由对话，而是在不完整、不可靠的证词下维护全局一致假设。

## 2. 真实规则字段

- 拓扑：`P-A-O-J` 线性；`P_J` 封闭；每条边 1 tick。
- 三种锁型：A/B/C；固定 seed0 真值 `B`，诚实者 `乙`（初始私有）。
- 六命题：甲 A1（A）、A2（B）；乙 B1（非 C）、B2（非 B）；丙 C1（C）、C2（非 A）。
- 回答：诚实者答真值，说谎者答反值；seed0 六问回答为 `是/否/是/否/是/否`。
- 问询：`ask(claim_id)` 每条牌一次，最多 4 问；重复问被拒、不推进 tick；4 问用尽后第 5 问被拒且不推进。
- 档案：A 室“C 从未安装在当前门上”，把锁型候选 3→A/B、隐藏状态 9→6。
- 提交：J `submit_configuration` 只按锁型决定开门；错误锁型两次失败，第一次错误仍可再提交。
- 成功：`gate_open`；失败：`WRONG_SUBMISSION_LIMIT`。

## 3. 指标

| metric_id | 类别 | 公式 | 单位/方向 | 分母 | 缺失/截尾 |
|---|---|---|---|---|---|
| `map14.globally_consistent_hypothesis_rate` | primary | 与全部已公开陈述一致的提交假设数 / 提交假设数 | 比例 / 高 | 提交假设数 | 无提交 → N/A/CENSORED |
| `map14.minimum_query_gap` | primary | 实际问询数 − 同实例最少问询数 | 次 / 低 | 实例最少问询数 | 无冻结最优 → UNAVAILABLE |
| `map14.query_budget_overruns` | guardrail | 第 5 问/重复问被拒次数 | 次 / 低 | episode | 0 合法 |
| `map14.contradiction_missed` | diagnostic | 提交含已知矛盾假设（0/1） | 0/1 / 低 | episode | 无提交 → N/A |
| `map14.queries_used` | diagnostic | 实际问询数 | 次 / 低 | episode | 0 合法 |

## 4. 能力混淆分析

- 高一致率可能只因为“只提交一个很弱的假设”；必须报提交次数与锁型正确率。
- 高问询效率可能只因为“猜对分支”；必须报一致性、档案使用与最坏分支问数（4）。
- 低分可能由“把说谎者的反报当真”造成，不是逻辑推理差；用回答码与提交假设的一致性归因。
- 档案是额外证据，不是答案；查档案路线用 3 问，未查档案的自适应路线也可能 3 问，不能把“少问”当能力。

## 5. 两条手算轨迹

**档案先行（11 tick）**：P→A 读档（2，锁型候选 A/B）→A→P（3）→问 A1（4，是）→问 B1（5，是）→问 B2（6，否）→P→A（7）→A→O（8）→`compare_evidence(B,乙,三条答复)`（9）→O→J（10）→提交 B（11）。指标：一致假设 1/1；问询 3；最少问 3 → gap 0；超预算 0；矛盾未识别 0。

**无档案自适应（8 tick）**：P 问 A1（1，是）→问 A2（2，否）→问 B1（3，是）→按决策树锁定 B/乙→P→A→O（5）→登记假设（6）→O→J（7）→提交 B（8）。指标：一致假设 1/1；问询 3；gap 0；超预算 0；档案未用。

> 9 种隐藏状态（3 锁型 × 3 诚实者）由 4 位回答码唯一区分；seed0 在 A1=是、A2=否、B1=是 后已唯一收敛。其他分支最坏 4 问。

## 6. 三个机制特有失败

1. **把甲的反报当真**：A1=是 被读成“当前是日轮锁”，提交 A；实际是 B，第一次错误后仍可再提交，但若继续坚持 A 则第二次失败。
2. **读到“C 未安装”仍提交 C**：档案已排除 C，提交 C 属于忽略明确反证；一致假设率 0。
3. **信息不足就提交**：只问 A1/B1 后把仍兼容的 A/甲 候选当唯一解；提交 A，错误一次；第二次仍不补问则失败。

## 7. 两个边界

- **一错后正确提交**：首次错误锁型仍允许第二次；第二次正确即成功。必须用同一问序只改第一次提交验证。
- **4 问用尽 vs 第 5 问**：4 问用尽不自动失败；第 5 问被拒且不推进 tick。若 Agent 把“被拒”当“已问”，会误判信息量。

## 8. 信息泄漏负例

若 Observation 直接给 `true_lock`、`honest_priest` 或真值表行号，真假逻辑被替代。V7 只允许公开六条命题、回答账本、档案文本与候选假设；`truth_table_audit.json` 与 Oracle 只在离线裁判侧。

## 9. Oracle/求解状态

`oracle_trace.jsonl` 有档案先行（11 tick）与无档案自适应（8 tick）两条手写成功；`failure_traces/cases.yaml` 有三条两次错交失败；`planning/truth_table_audit.py` 展开 9 行真值表并检查 4 位回答码唯一，输出 `truth_table_audit.json`。**没有运行时**；审计证明逻辑唯一性，不证明 Agent 可发现。

## 10. 与同世界另两图差异

**vs MAP-13**：MAP-13 的碑文全部为真、约束静态，核心是传播显式约束到唯一排列；MAP-14 的证词有真假、说谎者与问询预算，核心是维护“锁型×诚实者”的全局一致假设。MAP-13 的失败是漏约束/镜像，MAP-14 是误信反报/忽略反证；信息可靠性不同。

**vs MAP-15**：MAP-15 的规则随 tick 奇偶变化，同一门在不同状态效果不同，核心是从训练样例迁移到未见组合；MAP-14 的规则静态，难点是不可靠陈述与问询选择。MAP-14 没有状态转换或门色变化；把 MAP-14 的答案改成随 tick 变化会变成另一张图。

## 11. 可计算性来源

需要公开的 `public_statement_cards`、`archive_record_if_read`、`question_answers`、`questions_used/remaining`、`comparison_record`、`wrong_submissions`、`gate_open`、`terminal_reason`，以及提交的锁型/诚实者（若动作暴露）。一致性用公开命题与回答逐条重算；最少问询数由冻结真值表给出。

## 12. 难度定位与对照

D=(2,2,0,0,2,3)。加入信息不可靠性，非 MAP-13 的纯静态约束。预登记对照：**结构化真值表 vs 自由推理**；证词与问询预算相同。若真值表额外给诚实者，标为信息可用性实验。

## 13. 未决

“最少问询”需冻结是否允许重复问/档案是否计入；本卡按“3 问、允许一次错交”的 seed0 定义，其他分支报 4 问上界。运行时接入前需固定第 5 问不推进 tick 的行为。
