# 04 极地科考站：寒冷、生存与后勤

## 机制图

读天气相位与热量 → 选择户外步行、供暖或车辆 → 消耗体热/燃料并更新同行者 → 在燃料下限和救援目标间分配后勤。

体热是 0–10 整数；户外晴天每 tick -1、暴雪 -2，室内供暖耗一燃料回 4。世界特有的选择是路线、取暖资源和同行队员的联动。

| ID | 关卡 | 设计与参考策略 | 主要边界 |
|---|---|---|---|
| PO-E | 暴风雪前的避难所 | 读天气广播后从 station 穿过 snow_pass 到 shelter，激活 radio_antenna。体热 10、共享燃料 2；可选 observatory 不参与必经路线。 | 仅 snow_pass 按行动前公开天气扣热；室内 heater 消耗共享燃料并恢复 4；终局信号动作完成救援。 |
| PO-M | 燃料还是样本 | station 经 supply_hut 到 vehicle_pad，雪地车以每段 1 燃料直达 drill_site 并可再耗 1 返回；取 ice_core 后在 station 的 sample_receiver 登记。也可走 ice_field/return_route 并在 supply_hut 供暖。 | fuel=2 且供暖/车辆共用；车辆不经过中间房，零燃料时仍可按物理步行边返回；未携样或未登记不能成功。 |
| PO-H | 双队员撤离路线 | base↔heated_hut↔drill_camp 与 base↔ridge↔weather_post；取 rope_kit 并固定 heated_hut↔ridge 桥。分次护送 B、A 回 base，必要时在 hut 恢复双方体热。fuel=4，天气晴三相/暴雪三相。 | 同时至多一人随行，随行热量从 6 开始且仅同行时递减；室内加热恢复 4；完整成功要求两人到 base 且燃料≥1，燃料不足为 partial。 |

设计依据：研究提纲 §5。实现按行动开始时的公开天气结算，并公开同行者与燃料。未护送队员不运行隐藏计时；绳桥缩短 B 的返程并保留燃料策略。
