# MAP-17 设计验收

状态：`DESIGN_COMPLETE_PENDING_RUNTIME`。固定路网、需求矩阵、车队位置、两份不同的手工时刻表及乘客等待/能耗账本均已按动作复核；不代表V4运行时、Agent或模型验收。

## 完成核对

- [x] 环线A-B-C-D-A、B-E-F支线与双向共用BC区段；4列车、每站2车泊位、每车3座、12 tick、18能耗上限。
- [x] 五组手工OD客流合计10人；t0同时到达；明确每tick未登车等待累计、抵站卸客、停站/换线装客事件序。
- [x] 手工时刻表的路线、登车清单与资源账经专用回放器核对：准点点10/10、wait16、energy11、交付tick6；节能点8/10、wait38、energy8、交付tick6。
- [x] F01反向共用BC以 `SHARED_SEGMENT_CONFLICT` 失败；F02第三车争B站两泊位以 `PLATFORM_CAPACITY` 失败；失败tick的位置和能耗不部分提交。
- [x] F03安全但只送6/10人，等待60、能耗6，在tick12以 `DEADLINE_SERVICE_BELOW_80` 失败。
- [x] B01精确80%端点通过；两参考向量互不支配；公开原始指标与归一化欧氏距离公式，不声称全局Pareto最优。
- [x] seed0两次生成24行Oracle一致，SHA-256为 `9A4733EC00AB5D68FFFE24D38D7968E2E326B9C7E541846D85EDEE5A43FC4CB5`；公开观察包括拓扑/当前需求，但没有未来时刻表或参照Pareto点。

## 环境实现后

测试所有区段容量、同时卸客/进站站台结算、OD登车清单、转乘完整等待tick、12tick截止、能耗18边界和seed状态hash。离线手工调度与纸面指标不代表运行时、Agent或模型结果。
