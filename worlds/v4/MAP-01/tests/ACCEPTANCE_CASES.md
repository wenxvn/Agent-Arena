# MAP-01 Phase 1 测试用例草案

此目录当前只有测试设计，没有环境代码、可执行测试或测试结果。

1. 初始状态精确包含 B、氧余量 18、断供 0、总容量 6 和船壳未修。
2. 基础负荷加任一 2 格支路为 5，应可路由；两条支路同时开启总负荷 7，应以 `POWER_CAPACITY_CONFLICT` 拒绝且保留原电路。
3. 按成功 oracle 运行，18 个动作终止为 `scenario_success`；每步状态 hash 可重复。
4. 在 W-P 服务边关闭时尝试移动，消耗 1 tick 且位置不变；修船壳后同一 edge 可用。
5. 断供 3 个 tick仍可恢复；第 4 个连续断供 tick以 `OXYGEN_SUPPLY_INTERRUPTION_LIMIT` 失败。
6. 船壳未修时复位主电源，以 `BUS_RESET_WITH_HULL_OPEN` 终止；不得改写为普通拒绝。
7. 氧余量每个供氧关闭的结算 tick减 1，开启期间不变；到 0 时失败。
8. 每个对象只暴露其合法 choices；提交/交互失败反馈不含未来事件或 oracle 信息。
9. 同 seed 与动作序列两次重置重放，逐步 state hash、事件码和 Observation 字节一致。
10. Trace 与 Observation 中不出现 `judge_dependency_counters`、失败案例、oracle 路径或最优路线标签。
