# MAP-17 运行时实现后验收用例

这些用例留给Phase 1环境实现后执行；当前没有运行时或pytest结果。

1. Reset seed0：公开A-B-C-D-A与B-E-F；四车位于A/C/D/F且各3座；t0固定5组OD共10人，时间窗12、能耗18。
2. 每个timetable tick内放行同时结算；B-C两方向共用一段，区段每tick最多一车。
3. 每站至多停放2列车；离站与同tick进站按原子终态泊位数核验。
4. 每个release消耗1能量并前进一段；stop、switch_line、delay各占1tick、不耗能；B外switch拒绝且无部分执行。
5. B站默认线路为环线；驶入支线BE前须以 `switch_line(branch)` 换线，换线站停可同时按登车清单服务乘客。B站跨车转乘乘客至少等待一个完整tick。
6. stop或switch_line只按玩家提供的合法OD清单登车，不超剩余队列、座位或目的地；抵站时目的地匹配的乘客自动卸下计入服务率。
7. 未登车乘客在每tick操作前各累加1等待单位；tick12评价服务，剩余未服务需求等待值累计至12。
8. F01反向同时走BC返回 `SHARED_SEGMENT_CONFLICT`，失败tick不动、不耗能、不加等待。
9. F02站台有两列车时再让第三列进B，返回 `PLATFORM_CAPACITY`，该tick所有列车与登车清单均不部分执行。
10. F03在tick12送达6/10人，能耗6且无碰撞，仍以 `DEADLINE_SERVICE_BELOW_80` 失败。
11. B01能耗策略在tick12送达8/10，恰为80%，必须成功；F站未服务的2人等待12 tick。
12. 重放准点与节能Oracle：分别应为 `(100%, wait16, energy11, delivery6)` 与 `(80%, wait38, energy8, delivery6)`，两点互不支配。
13. Pareto距离逐项按公布范围归一化，对两个参照点自身距离为0；不得把它们宣称为全局最优前沿。
14. 同动作序列seed0两次执行：每tick队列、列车位置、载客、等待、能耗、交付数、终止码及状态hash一致。
15. 观察只包含当前需求、位置、剩余预算、当前操作与已发生结果；不含Oracle未来操作、参考Pareto点或裁判分数。
