# MAP-06 Phase 1 测试用例草案

以下为运行时实现后的规则验收草案，不是当前已执行测试。

1. 十个基础 seed 按联合表 reset；天气真值和预报在同 seed 重开局不变，短/长各 5 个且预报正确 8 个。
2. 初始位置 Q；M-Q、Q-P 单程各 1 tick，M-G、G-P 各 2 tick；无未列连边。
3. `inspect(forecast)` 只能在 Q 使用，恰耗 2 tick；同 seed 重复查看返回同一读数，不增加准确率。
4. 短暴风的暴露移动与未加固维修不增加风险；长暴风 Q-P/G-P 每旅行 tick +1，未加固维修每 tick +3。
5. `harden` 仅在 G 有效、耗 3 tick；仅保护下一次维修，不消除 G-P 旅行风险；维修结束后 shield 清零。
6. 累计风险 4 仍可执行；任何子步骤使风险达到 5 或以上时立刻以 `RISK_BUDGET_EXCEEDED` 终止。
7. 修复在 tick 14 结束且风险不超预算时成功；在 tick 14 结束仍未修复时以 deadline 失败。
8. 同 seed 四类 forecast/weather 联合结果的动作风险、时间和 success 与手写期望表相同。
9. 以 `U=100*success-7.2*tick-risk_points` 逐 seed 计算，不以成功率单独替代风险/时间；输出十 seed 平均值。
10. 正确天气对照仅能在对照组开启；基线 Observation 不含 `storm_type`、seed 类别或未来天气真值。
11. `evacuate` 在 M/Q 可作为安全退出，终态不是地图成功，风险不被伪造为零。
