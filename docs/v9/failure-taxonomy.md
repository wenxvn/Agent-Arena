# V9 失败分类与首因统计

- 数据：V8 正式 90 局（`docs/v9/run-index.csv`）+ 30 份逐图审计 + `runs/v9/baselines/`
- 口径：n=3 只作重复运行描述；首因是“最接近终局、删去后最可能改变结局的原因”，不是唯一原因
- 术语：A 环境规则缺陷；B 公开信息不足；C schema/接口误导；D 决策预算/horizon；E 策略规划错误；F 资源管理错误；G 记忆/推理错误；H 采样/运行异常；I 证据不足

## 1. 首因分布（30 图，按图计）

| 首因 | 图数 | 地图 |
|---|---:|---|
| A 规则缺陷 | 0 | 无“规则本身不可执行”的图；MAP-18 的 `step_limit=12` 计入 D |
| B 公开信息不足 | 13 | 03、06、09、10、12、14、15、17、22、26、28、29、30 |
| C 接口误导 | 4 | 05、07、08、16 |
| D 预算/horizon | 1 | 18 |
| E 策略规划 | 11 | 01、02、04、11、13、19、20、23、24、25、27 |
| F 资源管理 | 1（多为次因） | 11、27（次因） |
| G 记忆/推理 | 0（多为次因） | 04、24（次因） |
| H 运行异常 | 0 | 90 局正式结果无 provider 错误 |
| I 证据不足 | 0 | 每图至少 2 条 Trace 可读 |

> 多因说明：例如 MAP-11 首因 E/F（没装补给），次因 B（补给成本未公开）；MAP-16 R0 首因 E，R1/R2 首因 C。上表按“该图最主要的、可修复的阻塞”归类。

## 2. 22 张 0/3 图的根因分组

| 组 | 地图 | 共同特征 | 修复方向 |
|---|---|---|---|
| 公开信息硬缺口 | 07、09、10、12、26、28、29、30 | 必需字符串/阈值/边名只在源码或设计稿里；失败发生在首 2–10 步 | 补公开词表/规则，改 prompt hash；不改规则 |
| 接口语义误导 | 05、08、16、17 | 动作名与真实前置不符，错误码无梯度；试错消耗大量决策 | 补语义说明 + 统一错误码 |
| 构念可绕过/实例选择 | 06、14、15、21 | 成功路径不要求核心机制；随机或 1 步策略可通关 | 换 cohort/成功判据/公开信息条件，需用户裁定 |
| 预算/horizon 错配 | 18 | 声明 46、实际 12；拒绝动作也消耗 horizon | 解耦 step_limit 与 horizon，需改 V4 规则 |
| 记忆通道缺失 | 03、22 | 需要跨步记住代码/地图，但 runner 只保留 5 条动作历史，无 agent-owned note | 增加 note 通道或公开记忆 schema |
| 纯策略/资源失败 | 19、20、23、24、25、27 | 规则与公开信息基本可用，失败可定位到具体决策 | 保持规则；补指标/少量公开信息 |

**结论（RQ1）**：22 张 0/3 中，约 **13 张** 的首因是公开信息/接口（B/C），**1 张** 是预算（D），**8 张** 是策略/资源（E/F）。因此“0/3 = 能力为零”在本批数据上不成立；至少一半以上的 0/3 不能直接解释为能力结论。

## 3. 逐图首因与状态

| map | 世界 | 难度 | V8 | 首因 | 次因 | 标签（审计 §9） | 状态 | 优先级 |
|---|---|---|---|---|---|---:|---|
| MAP-01 | spaceship | 简单 | 0/3 | E | G/C | MEASUREMENT_VALID | VALIDATED | P2 |
| MAP-02 | spaceship | 中等 | 0/3 | E | B | MEASUREMENT_VALID, METRIC_DEFECT | VALIDATED | P2 |
| MAP-03 | spaceship | 困难 | 0/3 | B（记忆通道） | E | INTERFACE_BLOCKED, METRIC_DEFECT, RULE_DEFECT | NEEDS_REDESIGN | P0 |
| MAP-04 | lighthouse | 简单 | 1/3 | E | G | CONSTRUCT_BYPASS, METRIC_DEFECT | NEEDS_REDESIGN | P1 |
| MAP-05 | lighthouse | 中等 | 0/3 | C | B | MEASUREMENT_VALID, METRIC_DEFECT | VALIDATED | P1 |
| MAP-06 | lighthouse | 困难 | 3/3 | B（实例 seed） | — | CONSTRUCT_BYPASS, METRIC_DEFECT | NEEDS_REDESIGN | P0 |
| MAP-07 | abyss | 简单 | 0/3 | C | — | INTERFACE_BLOCKED, INCONCLUSIVE | BLOCKED | P0 |
| MAP-08 | abyss | 中等 | 0/3 | C | E | MEASUREMENT_VALID, CONSTRUCT_BYPASS, INCONCLUSIVE | NEEDS_REDESIGN | P1 |
| MAP-09 | abyss | 困难 | 0/3 | B | C | INTERFACE_BLOCKED, CONSTRUCT_BYPASS, INCONCLUSIVE | BLOCKED | P0 |
| MAP-10 | polar | 简单 | 0/3 | B | E/C | MEASUREMENT_VALID, INTERFACE_BLOCKED | NEEDS_REDESIGN | P1 |
| MAP-11 | polar | 中等 | 0/3 | E/F | B | MEASUREMENT_VALID, INTERFACE_BLOCKED, CONSTRUCT_BYPASS | NEEDS_REDESIGN | P1 |
| MAP-12 | polar | 困难 | 0/3 | C | B/E | INTERFACE_BLOCKED, METRIC_DEFECT | BLOCKED | P0 |
| MAP-13 | pyramid | 简单 | 2/3 | E | C | MEASUREMENT_VALID, METRIC_DEFECT | NEEDS_REDESIGN | P2 |
| MAP-14 | pyramid | 中等 | 0/3 | B/构念 | E | MEASUREMENT_VALID, CONSTRUCT_BYPASS, METRIC_DEFECT | NEEDS_REDESIGN | P0 |
| MAP-15 | pyramid | 困难 | 3/3 | 构念（goal 泄露） | — | CONSTRUCT_BYPASS, RULE_DEFECT, METRIC_DEFECT | NEEDS_REDESIGN | P0 |
| MAP-16 | subway | 简单 | 0/3 | C/E | B | MEASUREMENT_VALID | VALIDATED | P1 |
| MAP-17 | subway | 中等 | 0/3 | B | E/G | MEASUREMENT_VALID, METRIC_DEFECT | VALIDATED | P1 |
| MAP-18 | subway | 困难 | 0/3 | D | E/G | BUDGET_BLOCKED, RULE_DEFECT, CONSTRUCT_BYPASS, METRIC_DEFECT | NEEDS_REDESIGN | P0 |
| MAP-19 | volcano | 简单 | 0/3 | E | B | MEASUREMENT_VALID, METRIC_DEFECT, CONSTRUCT_BYPASS | NEEDS_REDESIGN | P1 |
| MAP-20 | volcano | 中等 | 2/3 | E | — | MEASUREMENT_VALID, CONSTRUCT_BYPASS, METRIC_DEFECT | NEEDS_REDESIGN | P1 |
| MAP-21 | volcano | 困难 | 3/3 | 构念 | — | CONSTRUCT_BYPASS, METRIC_DEFECT, INCONCLUSIVE | NEEDS_REDESIGN | P0 |
| MAP-22 | jungle | 简单 | 0/3 | B/D | E | BUDGET_BLOCKED, CONSTRUCT_BYPASS, INTERFACE_BLOCKED, METRIC_DEFECT | NEEDS_REDESIGN | P0 |
| MAP-23 | jungle | 中等 | 1/3 | E | B | MEASUREMENT_VALID, CONSTRUCT_BYPASS, METRIC_DEFECT, INCONCLUSIVE | NEEDS_REDESIGN | P1 |
| MAP-24 | jungle | 困难 | 2/3 | E | G | MEASUREMENT_VALID, CONSTRUCT_BYPASS, METRIC_DEFECT, INCONCLUSIVE | NEEDS_REDESIGN | P1 |
| MAP-25 | lunar | 简单 | 0/3 | E | C | MEASUREMENT_VALID, METRIC_DEFECT | NEEDS_REDESIGN | P1 |
| MAP-26 | lunar | 中等 | 0/3 | B | C | INTERFACE_BLOCKED, METRIC_DEFECT, INCONCLUSIVE | NEEDS_REDESIGN | P0 |
| MAP-27 | lunar | 困难 | 0/3 | E/F | — | MEASUREMENT_VALID | VALIDATED | P2 |
| MAP-28 | castle | 简单 | 0/3 | B | — | MEASUREMENT_VALID, INTERFACE_BLOCKED | NEEDS_REDESIGN | P1 |
| MAP-29 | castle | 中等 | 0/3 | B | — | MEASUREMENT_VALID, INTERFACE_BLOCKED | NEEDS_REDESIGN | P1 |
| MAP-30 | castle | 困难 | 0/3 | B | C | MEASUREMENT_VALID, INTERFACE_BLOCKED, METRIC_DEFECT | NEEDS_REDESIGN | P1 |

## 4. 为什么“困难图更容易”

本批 30 图里，困难层 11/30 成功，简单层 3/30。逐图证据显示这不是“困难图更简单”，而是：

1. **三张困难图被旁路**：MAP-06（seed 0 无风暴）、MAP-15（goal 直接给规则）、MAP-21（直达撤离早于最早喷发）贡献了 9/11 的困难层成功。
2. **简单图被接口卡住**：MAP-07（`control_panel`）、MAP-09（隐藏短路阈值）、MAP-10（隐藏燃料分仓）在简单层，失败发生在 2–30 步内，不是能力差异。
3. 因此“难度标签与通关率”在本批数据上**不构成单调关系**；V9 不按成功率重标难度，而是把三张旁路图与四张接口图分别处理。

## 5. 证据边界

- 每图都引用了至少 2 段真实 Trace；三局同 seed、同 prompt，n=3 不能区分个体差异与固定陷阱。
- 首因分类是**研究判断**，不是统计推断；多因图已标出次因。
- 没有把 Oracle 成功率当成模型能力；Oracle 只证明“存在合法路径”。
- 没有把 `human_approved` 写进任何图；所有 V9 状态均为 `agent_reviewed` 级，等待用户复核。
