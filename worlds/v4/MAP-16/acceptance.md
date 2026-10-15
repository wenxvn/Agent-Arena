# MAP-16 设计验收

状态：`DESIGN_COMPLETE_PENDING_RUNTIME`。固定路网、列车方向、泊位/区段容量、两套手工方案、四条失败轨迹和边界轨迹均已完成逐项纸面审查；该状态不代表V4运行时验收。

## 已完成核对

- [x] 固定 `A—X—M—Y—B` 与 `M—D` 侧线；两列车目标相反，X/M/Y/D均容量1，主线和侧线泊位分开计数。
- [x] 明确预订先于原子移动、区段每tick容量1、反向交换禁止、泊位空出与填入可同tick原子交班。
- [x] 手工时刻表分别为a先入侧线与b先入侧线；每表6 tick并到达对端，没有换皮路线或自动排程生成路径。
- [x] 离散有限状态审计从实际图和方向规则枚举28个可达无碰撞位置组合，其中(a=A,b=X)、(a=Y,b=B)两态无安全完成路径；两条人写路线都是六tick，BFS全状态最短解为六tick，最优差距0。
- [x] F01两路汇入M以 `NODE_CAPACITY_CONFLICT` 失败；F02对向申请XM以 `HEAD_ON_SWAP` 失败；F03驶入占用的D以 `SIDING_CAPACITY_CONFLICT` 失败；前三者失败时车位与tick均不变。
- [x] F04无物理冲突地进入(a=A,b=X)后以 `DEADLOCK` 终止，更新状态但不与预约/泊位冲突混淆。
- [x] B01由 `(a=D,b=M)` 同tick执行 `D→M` 与 `M→X`，原子结算合法，末态 `(M,X)`。
- [x] seed0两次重放均生成32行Oracle；SHA-256均为 `0EBA8AB27EEC3144ADBA6E404818EBDEB701C0ED51D5AF0E8781CE3B5C6B704B`。
- [x] 公共schema仅含固定公开路网、当前列车位置、目标和当前预约；Oracle、已算路线与死锁裁判不进入Observation。

## 已完成复核

- [x] F01–F03三种具体冲突因果和不移动/不增tick结算；F04不可恢复死锁因果。
- [x] B01容量端点交班与不同区段使用。
- [x] seed0两种方向次序重复生成相同Oracle字节。
- [x] 人工复核公开观察字段没有裁判答案、已算路线或未来调度建议。

## 环境实现后

运行时须实测 reservation ownership、区段反向冲突、占位原子更新、deadlock可达性、固定seed状态hash和所有手写轨迹。当前纸面调度或离散图枚举不等于环境、Agent、Provider、Benchmark已验收。
