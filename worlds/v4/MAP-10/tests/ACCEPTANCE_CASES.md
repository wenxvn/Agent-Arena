# MAP-10 Phase 1 测试用例草案

以下为环境实现后待执行的规则测试，不是当前已运行测试。

1. Reset：B/E/W/T 拓扑，B库燃料12、随身0/容量5、基地温度5、供暖开、E发电机关、seed0。
2. 燃料装载只在 B，耗1 tick并从B库转移；装载5成功、装载6不转移且触发超载规则。
3. tick1装载不触发供暖扣款；tick2且供暖开启/B库有油时正好扣1、温度不变。
4. 每个偶数 tick若供暖关闭或库中无油，温度减1；温度从1降至0立刻终止，不能在之后发报成功。
5. 普通边步行成本分别为 B-E=4、E-T=3、B-W=1、W-T=1；仅 E-W 可驾驶且耗1 tick/2随身燃料。
6. 驾驶双向重复穿越 E-W 时每次均扣2；随身燃料2可完成移动、余0。
7. E点携带3燃料启动发电机后余0且不消耗B库；携带2时执行1 tick失败校验、不扣燃料并以 `GENERATOR_FUEL_SHORTAGE` 终止。
8. T发报要求发电机在线；离线以 `GRID_OFFLINE` 终止，在线发报耗1 tick并在热量结算后验证温度。
9. 重放 `walk_keep_fuel`：tick10成功、基地余4、随身0、温度5；重放 `snowmobile_shortcut`：tick8成功、基地余3、随身0、温度5。
10. 重放 F01/F02/F03，终态分别为 `GENERATOR_FUEL_SHORTAGE@4`、到达T后 `BASE_FROZEN@10`、`BASE_FROZEN@24`。
11. 对同一 seed=0 和同一动作序列重复 reset/replay，逐 tick账本、路线、终态与状态 hash一致。
