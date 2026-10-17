# V8 最终验收

- 冻结：`4cd8a14131b9ca2022575badd93667d79864efd8d77d77ebc2a9957c9876661b`，commit `4ffbdeb2e6d22abfd340b9ea1aff73fade979674`。
- 离线门禁：30/30；154/154 指标；55 条 Oracle；85 条冻结 fixture + 12 条补充用例。
- 正式 MiMo：**90/90**；缺口 0 局；总费用 ¥1.25363556。
- 冻结 hash 一致性：通过
- commit 版本分布：{'223e532ed9b9613ba96e06d129b41fb1f52b37bc': 63, '4ffbdeb2e6d22abfd340b9ea1aff73fade979674': 27}

## 1. 30 图定稿表

| world | map | 难度 | 独特机制 | rule_hash | runtime | metrics | oracle | 3 局 | 状态 |
|---|---|---|---|---|---|---|---|---|---|
| spaceship | MAP-01 | 简单 | 破损的曙光号 | `b0b4cf2c14e9` | verified | 5/5 | verified | 0/3 | finalized |
| spaceship | MAP-02 | 中等 | 双重警报 | `f48f10bc47fd` | verified | 5/5 | verified | 0/3 | finalized |
| spaceship | MAP-03 | 困难 | 最后的百步 | `ba6ee7abcbb1` | verified | 5/5 | verified | 0/3 | finalized |
| lighthouse | MAP-04 | 简单 | 潮汐密道 | `88500e992c3b` | verified | 5/5 | verified | 1/3 | finalized |
| lighthouse | MAP-05 | 中等 | 三束信号 | `4aa810269535` | verified | 5/5 | verified | 0/3 | finalized |
| lighthouse | MAP-06 | 困难 | 暴风眼 | `2adb4f3322d0` | verified | 5/5 | verified | 3/3 | finalized |
| abyss | MAP-07 | 简单 | 逆流阀门 | `1183d0dea109` | verified | 5/5 | verified | 0/3 | finalized |
| abyss | MAP-08 | 中等 | 看不见的裂缝 | `9a3827c2f5fe` | verified | 7/7 | verified | 0/3 | finalized |
| abyss | MAP-09 | 困难 | 深海连锁故障 | `603948debd2f` | verified | 5/5 | verified | 0/3 | finalized |
| polar | MAP-10 | 简单 | 最后一桶燃料 | `d4bddf5702e6` | verified | 5/5 | verified | 0/3 | finalized |
| polar | MAP-11 | 中等 | 失联的小队 | `86334e9a3fa6` | verified | 5/5 | verified | 0/3 | finalized |
| polar | MAP-12 | 困难 | 极夜三十天 | `ec0b473f08d1` | verified | 5/5 | verified | 0/3 | finalized |
| pyramid | MAP-13 | 简单 | 四神之门 | `0481b734b73d` | verified | 5/5 | verified | 2/3 | finalized |
| pyramid | MAP-14 | 中等 | 说谎的祭司 | `1c352a0fd891` | verified | 5/5 | verified | 0/3 | finalized |
| pyramid | MAP-15 | 困难 | 会变化的迷宫 | `7d8322b90d7c` | verified | 5/5 | verified | 3/3 | finalized |
| subway | MAP-16 | 简单 | 单线会车 | `47548b6c5585` | verified | 8/8 | verified | 0/3 | finalized |
| subway | MAP-17 | 中等 | 早高峰 | `9e9985a2238a` | verified | 4/4 | verified | 0/3 | finalized |
| subway | MAP-18 | 困难 | 故障传播 | `aa446dfaa631` | verified | 8/8 | verified | 0/3 | finalized |
| volcano | MAP-19 | 简单 | 温度临界点 | `28b181b4b82e` | verified | 4/4 | verified | 0/3 | finalized |
| volcano | MAP-20 | 中等 | 冷却网络 | `983f83987d11` | verified | 4/4 | verified | 2/3 | finalized |
| volcano | MAP-21 | 困难 | 喷发倒计时 | `59675a2c8240` | verified | 4/4 | verified | 3/3 | finalized |
| jungle | MAP-22 | 简单 | 没有地图的森林 | `e856cec6daf4` | verified | 7/7 | verified | 0/3 | finalized |
| jungle | MAP-23 | 中等 | 迷雾中的遗迹 | `7579ca9aa3fa` | verified | 4/4 | verified | 1/3 | finalized |
| jungle | MAP-24 | 困难 | 消失的道路 | `394665914bb5` | verified | 4/4 | verified | 2/3 | finalized |
| lunar | MAP-25 | 简单 | 第一次出舱 | `51e3acc1edab` | verified | 4/4 | verified | 0/3 | finalized |
| lunar | MAP-26 | 中等 | 失败的维修计划 | `a0de5a1957c0` | verified | 7/7 | verified | 0/3 | finalized |
| lunar | MAP-27 | 困难 | 月面联合行动 | `b993858b9d0b` | verified | 4/4 | verified | 0/3 | finalized |
| castle | MAP-28 | 简单 | 消失的王冠 | `ce443167b19d` | verified | 4/4 | verified | 0/3 | finalized |
| castle | MAP-29 | 中等 | 不可靠的证人 | `9549fbc011f9` | verified | 4/4 | verified | 0/3 | finalized |
| castle | MAP-30 | 困难 | 30 午夜审判 | `f53fe656d63d` | verified | 7/7 | verified | 0/3 | finalized |

## 2. 逐图验收结论

每图 `MAP-XX-final.md` 记录机制、公开/私有字段、动作契约、结算顺序、失败码、主要指标、Oracle、fixture 与三局原始结果。验收条件为：

- design_frozen：规则与 hash 已冻结；
- runtime_verified：Oracle 真实回放成功、确定性、终止不变性与泄漏检查通过；
- metrics_verified：登记指标 154/154 有来源、五态与分母规则正确；
- three_valid_mimo_runs：三次正式运行均有 trace/judge/V8 metrics/usage，且不是接口误导或无效 schema 导致的无效轨迹。

正式运行前有五次预跑作废：`pre_timeout_001`（wall-clock 上限过紧）、`pre_vocab_001`（01–06 交互词表缺失）、`pre_vocab_full_001`（其余字符串枚举缺失）、`pre_map01_rule_001`（MAP-01 供氧硬规则未公开）与 `pre_location_001`（交互对象位置未公开）。五者均归档在 `runs/v8/aborted/`，不计入正式 90 局；修复后已重新冻结。

## 3. 未解决风险

- 0/3 地图的真实原因是模型策略、机制陷阱还是接口负担，需要逐 trace 归因；本报告不把 0/3 解释为能力为零。
- 六张 V4 适配图复用 V6 冻结场景；V7 已记录的天花板/地板仍在，V8 没有通过改规则消除。
- 独立第二路径核对：MAP-01–06 的 Oracle 来自 V4 论文轨迹，六张适配图使用 V7 已发布手算值；其余 18 图的 fixture 与 extractor 同源，尚未建立完全独立的第二实现，列为 V9 改进项。
- 三次重复不是独立场景 seed；不能外推为总体成功率。
- MAP-08/16/18/22/26/30 的条件含公开先验/后验或案卷，属于信息可用性条件，不宣称纯推断能力。
- 全仓仍有 676 条历史 Ruff 问题（冻结的 `worlds/v4` 与旧脚本），V8 作用域已通过。

## 4. 缺口与后续 V9 建议

正式 90 局均有结果；无接口或预算缺口。

V9 建议：

1. 对 0/3 地图做逐 trace 的接口/策略归因，区分“不会做”与“没看懂契约”。
2. 在独立预算与预登记下，对地板/天花板地图增加重复数或条件对照，而不是改规则。
3. 把 MAP-08/18/26 的已知地板与 V6/V7 结果做纵向对照，检验实例与条件差异。
4. 若需要总体成功率，使用分层抽样与多 seed 环境实例，不把同图三次重复当独立样本。
