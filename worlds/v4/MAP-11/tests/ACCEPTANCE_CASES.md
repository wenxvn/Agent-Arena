# MAP-11 Phase 1 测试用例草案

以下是环境实现后待执行的规则测试，不是当前已运行测试。

1. Reset：B/P/S与B/D/Q/S两条不相交路线、补给箱8、随身0/容量8、两人体温10、队员计时15、当前天气clear。
2. B执行 `resupply(q)` 耗1 tick且只转移；短路整圈8单位、长路整圈6单位；剩1时申请移动边成本2/1不足均不能负扣。
3. 短路常载每段1 tick/2补给，负重返程每段2 tick/仍2补给；长路常载每段3 tick/1补给，负重返程每段4 tick/仍1补给。
4. 隐藏quiet/unstable先验各0.5，逐短段暴风率0.1/0.6；scout耗2 tick且 `P(rising|quiet)=.2`、`P(rising|unstable)=.8`。
5. scout后 falling forecast=.2、rising=.5；每个已观测short crossing用storm/clear似然递推posterior及forecast；Observation不得包含regime、未来storm mask或seed fixture。
6. 短边每次穿越基础体温−1，storm额外−5；长边每段体温−1且无storm；只影响当时与该暴露路线在场/同行的人。
7. `rest`只在B/D/Q，耗1 tick/1随身补给，给在场者+2、上限10；未救队员不回血，计时仍递减。
8. 队员计时1时启动1 tick救援必须先到0并失败；计时2时完成后余1并成功；救援后不再递减。
9. 重放Oracle `quick_short_seed0`：tick8返回、补给耗8、体温6/7；`scout_then_long_seed7`：tick25返回、余生命2、体温4/7。
10. F01/F02/F03分别以 `SUPPLY_SHORTAGE@7`、`BODY_HEAT_DEPLETED@10`、`TEAM_LIFE_EXPIRED@15` 终止。
11. 固定10 seed均匀夹具复核气象态、signal似然与短段事件数；相同seed/行动序列重复reset-replay应生成相同状态hash。
