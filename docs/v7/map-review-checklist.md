# V7 逐图人工复核清单

> 本清单用于**人工**审阅。DeepSeek 可以完成 `self_review` 与 `second_pass_check`，但不能冒充人工签署。未签署前，所有地图 `review_status = pending_human_review`。

## 1. 六项独立复核（每项提交证据，不勾选）

### R1 机制唯一性

- 与同世界另两图分别写 ≥120 字差异；
- 指明不同的状态变量、动作因果、不可逆失败模式；
- 仅替换地图名、场景名、数值 → 不合格。

**证据位置**：设计卡“与同世界差异”小节。

### R2 指标必要性

- 解释该主指标为何能测构念、为何通关率不足；
- 给出至少两个“分数不同但通关状态相同”的手算轨迹；
- 指出什么反例会让该指标产生误导。

**证据位置**：设计卡“能力混淆分析 / 反例”小节。

### R3 数据可计算性

- 逐字段定位 trace 来源；
- 需要新事件时先定义只读 instrumentation，不改规则；
- 无运行时只能提交规范与伪数据单元测试，不得声称真实验证。

**证据位置**：设计卡“可计算性与来源字段”小节 + extractor。

### R4 可解性/最优性

- 分别记录可行路线、独立算法下界/最优证明、缺失证明；
- 构造可行解不等于全局最优；
- MAP-18 不能把 18/18 服务率等同于延误最优。

**证据位置**：设计卡“Oracle/求解状态”小节。

### R5 公平与无泄漏

- 对照不把最优动作、未来事件、隐藏真值送入 prompt；
- 同实例条件对照除预登记处理外一致；
- 私有字段只在离线裁判/指标复算中使用。

**证据位置**：设计卡“泄漏负例”小节 + `scripts/validate_v7_metrics.py`。

### R6 难度校准

- 简单/中等/困难各有具体增加的认知维度；
- 不能只延长倒计时或增加空走步数；
- 若旧设计不符，提 DCR，不私改规则。

**证据位置**：设计卡“难度定位”小节 + `difficulty-rubric.md`。

## 2. 审阅状态

| 状态 | 含义 |
|---|---|
| `design_draft` | 只有想法，未形式化 |
| `self_review` | 执行模型自审完成，证据齐全 |
| `second_pass_check` | 第二遍机器/人工辅助核对完成（仍非签署） |
| `pending_human_review` | 等待人工签署（默认） |
| `human_approved` | 人工审阅者明确签署 |
| `changes_requested` | 人工要求修改或 DCR |

本轮 30 图统一：`review_status = pending_human_review`。

## 3. 逐图人工签署表

| 地图 | 机制唯一性 | 指标必要性 | 可计算性 | 可解性 | 无泄漏 | 难度 | 人工签署 |
|---|---|---|---|---|---|---|---|
| MAP-01 | 待审 | 待审 | 设计态 | 纸面 | 待审 | 待审 | `pending_human_review` |
| MAP-02 | 待审 | 待审 | 设计态 | 纸面 | 待审 | 待审 | `pending_human_review` |
| MAP-03 | 待审 | 待审 | 设计态 | 纸面 | 待审 | 待审 | `pending_human_review` |
| MAP-04 | 待审 | 待审 | 设计态 | 纸面 | 待审 | 待审 | `pending_human_review` |
| MAP-05 | 待审 | 待审 | 设计态 | 纸面 + DCR | 待审 | 待审 | `pending_human_review` |
| MAP-06 | 待审 | 待审 | 设计态 | 纸面 | 待审 | 待审 | `pending_human_review` |
| MAP-07 | 待审 | 待审 | 设计态 | 纸面 | 待审 | 待审 | `pending_human_review` |
| MAP-08 | 待审 | 待审 | ✅ trace | ✅ 求解器 | 待审 | 天花板待处理 | `pending_human_review` |
| MAP-09 | 待审 | 待审 | 设计态 | 纸面 | 待审 | 待审 | `pending_human_review` |
| MAP-10 | 待审 | 待审 | 设计态 | 纸面 | 待审 | 待审 | `pending_human_review` |
| MAP-11 | 待审 | 待审 | 设计态 | 纸面 | 待审 | 待审 | `pending_human_review` |
| MAP-12 | 待审 | 待审 | 设计态 | 离线搜索 | 待审 | 待审 | `pending_human_review` |
| MAP-13 | 待审 | 待审 | 设计态 | 约束审计 | 待审 | 待审 | `pending_human_review` |
| MAP-14 | 待审 | 待审 | 设计态 | 真值表审计 | 待审 | 待审 | `pending_human_review` |
| MAP-15 | 待审 | 待审 | 设计态 | 规则审计 | 待审 | 待审 | `pending_human_review` |
| MAP-16 | 待审 | 待审 | ✅ trace | ✅ BFS | 待审 | L1 天花板 | `pending_human_review` |
| MAP-17 | 待审 | 待审 | 设计态 | Pareto 审计 | 待审 | 待审 | `pending_human_review` |
| MAP-18 | 待审 | 待审 | ✅ trace | 构造解（非最优） | 待审 | 地板待处理 | `pending_human_review` |
| MAP-19 | 待审 | 待审 | 设计态 | 热审计 | 待审 | 待审 | `pending_human_review` |
| MAP-20 | 待审 | 待审 | 设计态 | 流量审计 | 待审 | 待审 | `pending_human_review` |
| MAP-21 | 待审 | 待审 | 设计态 | 决策审计 | 待审 | 待审 | `pending_human_review` |
| MAP-22 | 待审 | 待审 | ✅ trace | ✅ BFS | 待审 | L3 待重复 | `pending_human_review` |
| MAP-23 | 待审 | 待审 | 设计态 | 信息审计 | 待审 | 待审 | `pending_human_review` |
| MAP-24 | 待审 | 待审 | 设计态 | 地图更新审计 | 待审 | 待审 | `pending_human_review` |
| MAP-25 | 待审 | 待审 | 设计态 | 流程审计 | 待审 | 待审 | `pending_human_review` |
| MAP-26 | 待审 | 待审 | ✅ trace | ✅ 恢复尾搜索 | 待审 | 恢复地板 | `pending_human_review` |
| MAP-27 | 待审 | 待审 | 设计态 | 协同审计 | 待审 | 待审 | `pending_human_review` |
| MAP-28 | 待审 | 待审 | 设计态 | 证据审计 | 待审 | 待审 | `pending_human_review` |
| MAP-29 | 待审 | 待审 | 设计态 | 证词审计 | 待审 | 待审 | `pending_human_review` |
| MAP-30 | 待审 | 待审 | ✅ trace | ✅ 构造解 | 待审 | 调查地板 | `pending_human_review` |

## 4. 人工审阅时必须回答的问题

1. 该图究竟测什么？哪些指标直接对应能力？
2. 失败是模型、接口、不可解还是预算截尾？
3. 对照条件除目标机制外是否等价？
4. 是否存在跨实例稳定差异？样本量是否足够？
5. 能否用更强模型/独立算法/简单启发式建立难度梯度？
6. 是否值得投入真实 API 成本？若否，是改设计还是停用？

## 5. 退回条件

- 30 卡有批量换名痕迹；
- 跨地图直接比较原始分数；
- 难度仅改步数/倒计时；
- MAP-18 静态调度地板被忽略；
- MAP-26 靠赠送资源“修复”；
- MAP-30 把调查与记忆混为一谈；
- 没有实际运行就写“测试通过”；
- 任何未经授权付费 API。
