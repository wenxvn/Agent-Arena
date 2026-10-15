# MAP-24 环境实现后验收用例

本设计阶段不运行pytest；以下是实现阶段的精确验收规格。

1. Reset位置A/tick0，Agent只看到A的直接邻接和本地动作结果，不收到全局拓扑、桥坍塌tick、潮位相位或未来事件表。
2. A-B、B-C、C-D、D-E、E-A均为1 tick；A-F、F-C各为2 tick。图边双向。
3. 每个tick动作结束后先处理到tick8的事件，再构造结果Observation；A-B与B-C永久关闭，桥B保留为孤立节点。
4. C到B于tick7出发、tick8抵达后因Agent停在B而受困；B到A同一时段抵达后则已离开B，不受困；tick6出发的C到B于tick7正常可走。
5. 潮道周期4、每周期连续开2 tick；具体offset由seed确定但不返回Agent。只在D/E测量，耗1 tick并仅报告结果tick的本站状态。
6. D-E开放时出发耗1 tick通过；关闭时原地失败并耗1 tick。失败后的tick与潮态照常推进。
7. `probe_bridge`只可在B用一次、耗2 tick，只报告当时桥状况，不返回未来坍塌时间；`record_route`耗1 tick并保存动作开始时的本站邻接快照。
8. 路线笔记不随事件自动改写；到达相关节点后观察只能刷新当前位置直接邻接，不能同步地图其他部分。
9. C遗迹与D河岸各一个指定物资，各取用1 tick；只有同时携带两件到A且tick不超过24才成功。
10. F01–F03的状态、携带物资、重复次数和终止原因与`failure_traces/cases.yaml`逐项一致。
11. 连续检查seed 0–3潮位相位offset 0–3；每一相位都能通过本地测量与等待或改走F，在deadline前完成，不把offset写入Oracle。
12. 相同seed0完整重放时动作、局部邻接、事件结算时刻、潮位读数、路线笔记和交付tick一致；Oracle不得含私有事件表。
