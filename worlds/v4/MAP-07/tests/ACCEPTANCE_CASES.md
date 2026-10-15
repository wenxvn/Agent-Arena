# MAP-07 Phase 1 测试用例草案

这些是待环境实现的规则验收，不表示已执行。

1. Reset 水位为 A6/B2/C4/D0、阀全闭、泵关闭，阈值边界 8 安全。
2. 开 v1 后同 tick 开 v2，刚从 A 流入 B 的水可继续由 v2 输至 C；同理 v3 可处理该 tick 刚进入 C 的水。
3. v4 只允许 C→A，且在 v3 后对剩余 C 水结算；不能把同一份水重复转移。
4. 每轮依次处理 v1/v2/v3/v4 后才从 D 泵出最多 2；启动泵的当前 tick 已耗 2 单位功率。
5. 检查水位 8 不失败、水位 9 触发对应舱室溢流；F01/F02/F03 首次失败舱分别 A/C/B。
6. 水位 A/B/C 连续满足 `≤2` 一次时 streak=1，不终止；任何一次高于2归零；第二个连续低水 tick成功。
7. `inspect(water_levels)`、`inspect(pipe_diagram)` 和 `interact(control_panel,predict_next_levels,...)` 都耗1 tick并照常结算流水，不存在免费侦察。
8. `downstream_first` 与 `upstream_staged` 的逐步水位、完成 tick、泵能耗与峰值 C 符合 JSONL。
9. 同 seed、相同控制序列重放输出相同水位、泵排量、成功/失败 reason code 与状态 hash。
10. 预测绝对误差记入 judge-side score，不读取 `note`、不改变水位，不泄露到 Agent 观察。
