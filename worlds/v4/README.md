# V4 手工关卡设计

状态：30/30 逐关手工设计与离线固定轨迹审计完成，全部为 `DESIGN_COMPLETE_PENDING_RUNTIME`。V4 与现有 V3 隔离；本阶段只交付设计规格，不添加环境实现，不启动真实模型实验。

每张图单独完成后才开始下一张。设计状态 `DESIGN_COMPLETE_PENDING_RUNTIME` 只表示逐关设计材料和纸面轨迹已自审，不等于可运行、确定性测试通过或 Benchmark 有效。未实现前不使用 `VERIFIED`。

| 地图 | 主题 | 主能力 | 设计状态 |
|---|---|---|---|
| MAP-01 | 破损的曙光号 | 前置依赖规划 | DESIGN_COMPLETE_PENDING_RUNTIME |
| MAP-02 | 双重警报 | 突发事件后的重规划 | DESIGN_COMPLETE_PENDING_RUNTIME |
| MAP-03 | 最后的百步 | 长时程目标保持与阶段记忆 | DESIGN_COMPLETE_PENDING_RUNTIME |
| MAP-04 | 潮汐密道 | 周期预测与跨动作时序 | DESIGN_COMPLETE_PENDING_RUNTIME |
| MAP-05 | 三束信号 | 单路供电的共享资源调度 | DESIGN_COMPLETE_PENDING_RUNTIME（含窗口 DCR） |
| MAP-06 | 暴风眼 | 预报信息价值与风险预算决策 | DESIGN_COMPLETE_PENDING_RUNTIME |
| MAP-07 | 逆流阀门 | 指定顺序的级联水流因果预测 | DESIGN_COMPLETE_PENDING_RUNTIME |
| MAP-08 | 看不见的裂缝 | 主动实验设计与停止决策 | DESIGN_COMPLETE_PENDING_RUNTIME |
| MAP-09 | 深海连锁故障 | 跨系统因果控制 | DESIGN_COMPLETE_PENDING_RUNTIME |
| MAP-10 | 最后一桶燃料 | 多用途资源预算 | DESIGN_COMPLETE_PENDING_RUNTIME |
| MAP-11 | 失联的小队 | 风险策略 | DESIGN_COMPLETE_PENDING_RUNTIME |
| MAP-12 | 极夜三十天 | 跨周期经营 | DESIGN_COMPLETE_PENDING_RUNTIME |
| MAP-13 | 四神之门 | 约束满足 | DESIGN_COMPLETE_PENDING_RUNTIME |
| MAP-14 | 说谎的祭司 | 真假逻辑 | DESIGN_COMPLETE_PENDING_RUNTIME |
| MAP-15 | 会变化的迷宫 | 奇偶相位下的抽象规则迁移 | DESIGN_COMPLETE_PENDING_RUNTIME |
| MAP-16 | 单线会车 | 单线预约、避让站与死锁规避 | DESIGN_COMPLETE_PENDING_RUNTIME |
| MAP-17 | 早高峰 | 多目标时刻表优化与共享瓶颈调度 | DESIGN_COMPLETE_PENDING_RUNTIME |
| MAP-18 | 故障传播 | 在线恢复调度、告警配对与跨线恢复 | DESIGN_COMPLETE_PENDING_RUNTIME |
| MAP-19 | 温度临界点 | 两tick阀门时滞下的热状态预测与负荷控制 | DESIGN_COMPLETE_PENDING_RUNTIME |
| MAP-20 | 冷却网络 | 损耗水路分配与热区供冷 | DESIGN_COMPLETE_PENDING_RUNTIME |
| MAP-21 | 喷发倒计时 | 噪声时序线索下的风险采样 | DESIGN_COMPLETE_PENDING_RUNTIME |
| MAP-22 | 没有地图的森林 | 局部观察、空间记忆与巡回探索 | DESIGN_COMPLETE_PENDING_RUNTIME |
| MAP-23 | 迷雾中的遗迹 | 线索信息价值与补给受限探索 | DESIGN_COMPLETE_PENDING_RUNTIME |
| MAP-24 | 消失的道路 | 地图事实更新与动态绕行 | DESIGN_COMPLETE_PENDING_RUNTIME |
| MAP-25 | 第一次出舱 | 安全流程与强类型工具依赖 | DESIGN_COMPLETE_PENDING_RUNTIME |
| MAP-26 | 失败的维修计划 | 错误归因、反馈后自我纠错与备件预算 | DESIGN_COMPLETE_PENDING_RUNTIME |
| MAP-27 | 月面联合行动 | 长时程工具与资源协调、货位顺序、远程救援依赖 | DESIGN_COMPLETE_PENDING_RUNTIME |
| MAP-28 | 消失的王冠 | 跨来源证据整合与目击误认纠正 | DESIGN_COMPLETE_PENDING_RUNTIME |
| MAP-29 | 不可靠的证人 | 提问选择与证词来源评估 | DESIGN_COMPLETE_PENDING_RUNTIME |
| MAP-30 | 30 午夜审判 | 长间隔证据记忆与谨慎决策 | DESIGN_COMPLETE_PENDING_RUNTIME |

每个地图目录保存 `DESIGN.md`、`map_spec.yaml`、`evidence_or_rules.yaml`、手工 oracle、三条失败轨迹、设计验收记录和 Phase 1 测试用例草案。Oracle 与失败轨迹属于裁判侧资料，绝不能进入 Agent Observation、prompt 或 Trace。

## 设计边界

- V3 的 `scenario_v3` selector、Action、Observation、Trace 和十个家族定义保持不变。
- V4 计划使用隔离的 `scenario_v4` contract，沿用 `move`、`inspect`、`interact`、`wait`、`submit` 这些结构化动作形态；每关可用操作以自身 schema 为准。
- 不运行真实 Provider。环境实现与运行时回放属于后续阶段。
- 附件中的候选数值允许在不改变主能力、胜利谓词或拓扑的情况下精化；任何这种修订都逐图解释，不以外观换名替代机制。

## 逐关进度

| 地图 | 完成项 | 待办 |
|---|---|---|
| MAP-01 | 拓扑、状态、动作、事件顺序、胜负条件、手写成功轨迹、3 条失败轨迹、边界与专属测量 | 环境实现后回放、hash、Observation 泄漏和实际规则测试 |
| MAP-02 | 事件触发、两种目标优先顺序、8 tick 现场救援界限、两条手写成功轨迹、3 条失败轨迹与事件边界 | 环境实现后回放、hash、事件结算顺序和 Observation 泄漏测试 |
| MAP-03 | 两层 9 节点、五阶段依赖、一次性 K7 记忆、两条手写成功轨迹（30/31 tick）、3 条资源与记忆失败轨迹 | 环境实现后回放、hash、一次性观测和两个时间边界测试 |
| MAP-04 | 8 节点潮道/绕行结构、周期与动作成本、两条 14/15 tick 成功轨迹、三条逐动作失败轨迹；已修正失败轨迹在 deadline 后继续行动的问题 | 环境实现后回放、hash、六种潮相边界、deadline 顺序与观察隔离验证 |
| MAP-05 | 四节点单路供电、三条不同旅行成本、校准断电保留、两种非支配手写调度（tick 31/29）、三条窗口失败轨迹；原始窗口不可行已提交手算 DCR | 实现前处理窗口 DCR；环境实现后穷举/Pareto、逐步回放、窗口端点与截止顺序测试 |
| MAP-06 | 四节点独特暴露/遮蔽风险拓扑、十 seed 精确 80% 预报、三策略效用手算（24.9/27.0/27.3）、四段成功分支与三种失败因果 | 环境实现后逐 seed 重放、14 tick 与 4 点风险边界、效用权重/先验敏感性验证 |
| MAP-07 | 四舱按 v1→v2→v3→v4 顺序即时级联、泵后排水；两种手写调度 tick 6/8（泵能耗 12/10），三条逐步溢流失败分别锁定 A/C/B | 环境实现后复核可变水位级联、8/9 边界、稳定计数及同 seed 重放 |
| MAP-08 | 六舱环+X/Y 不同分割的传感器；两种诊断树，成功在 tick 6–12；12 seed 等先验与偏置先验下首测价值变化；三条错修/超压失败 | 环境实现后做初始观测等价、测试签名、熵与压力边界枚举 |
| MAP-09 | 四舱跨系统漏水/短路、抽水/发报共享电池、断电/供氧/连续通信耦合；preserve 保泵 tick 13 与 sacrifice 弃舱 tick 9 两种手写成功方案；三条动作级失败轨迹；补明低电发报校验耗1 tick不扣电 | 环境实现后复核闸门和水位顺序、电量恰好3/不足3、连续供氧与状态哈希 |
| MAP-10 | 基地油库与随身燃料分仓；长坡步行 tick10/余4油，对比 W-E 雪地车捷径 tick8/余3油且温度均保持5；燃料严格守恒，三种供暖/运输失败和偶数 tick 热结算边界 | 环境实现后核对多 tick 行进期间结算、温度0终止顺序、超载和固定 seed 重放 hash |
| MAP-11 | 分离的短险/长安全路；四段短路冻伤与隐藏天气态；噪声侦察信号及每次已见晴/暴风后的 Bayesian 后验更新；解析风险率与手工分层10-seed夹具；快救援、侦察分流、背风长路三种计划及补给/冻伤/生命窗失败 | 环境实现后核对belief递推、暴风受伤对象、负重返程、计时边界和seed重放 hash |
| MAP-12 | 固定极夜30日库存账；H-E-G-S-L及两条支路；每日2动作与供暖/口粮双连续欠供；温室/科研三日周期、7日维护；MAP12专属DFS搜索出一条有界可行日历；手工研究优先/安全垫策略各30日，日状态账与资源守恒；三种动作因果失败与边界案例 | 环境实现后核对日结算序、资源及动作上限、两成功trace和三失败trace的固定seed状态hash；当前仅纸面重放 |
| MAP-13 | C-N/E/S/W星形拓扑；明确物理图与N-E-S-W逻辑序；24排列唯一解和逐条删约束必要性（2/5/2/4）；第五方向钉解镜像映射；约束传播/系统枚举两条手写20 tick成功路径、三条逐动作失败轨迹 | 环境实现后验证碑文泄漏、验证无提示、错排第3次边界与固定seed重放hash |
| MAP-14 | P-A-O-J线性图与封闭P-J；固定三锁型×三真话者九态真值表；四问码唯一，自适应最坏4问；档案将候选9→6；两条手写11/8 tick成功路，三条两次错交失败，封存比对不反馈 | 环境实现后复核回答真值、问题/错交预算、错误无反馈、9态唯一与固定seed状态hash |
| MAP-15 | 手工四色互补规则、A/B/C/T四组专属布局、同墙异相位对照；两条不同策略成功路线逐动作Oracle；三条失败路线与可达的最后资源/第二次测试错边界；规则约束审计、固定seed0两次Oracle生成SHA-256一致 | 环境实现后验证Observation隔离、奇偶与错误结算顺序、固定seed状态hash和Agent迁移表现 |
| MAP-16 | A—X—M—Y—B主线与M—D侧线；手工定向路由和原子预约/结算规则；a、b先后避让两套独特六tick方案；28个无碰撞位置状态枚举、2个不可恢复死锁、最短makespan六tick/最优差距0；三条冲突与一条死锁失败、原子交班边界、seed0 32行Oracle字节重放 | 环境实现后验证安全resolver、节点/区段容量、deadlock检测与固定seed状态hash |
| MAP-17 | A-B-C-D-A环线、B-E-F支线与BC双向共享段；4车/5组OD共10人；准点/节能两份独立手写12tick表；回放指标分别为(10人,等待16,能耗11)与(8人,等待38,能耗8)，两锚点互不支配；三条容量/服务失败、80%端点、seed0 24行稳定Oracle | 环境实现后验证并行事件、转乘等待、站台/能耗/截止边界及状态hash |
| MAP-18 | 三线六车/18人故障场景、闭塞与复开边界、无故障可行时刻表、告警/无告警配对3乘客tick延误差、跨线泊位链、等修复与取消折返两类手写恢复；3条失败逐步回放、3个边界、36行seed0公开Oracle双次hash一致（`DDD11F97…BB3AA33`） | 环境实现后测试同步事件、闭塞私有信息、泊位与区段原子resolver、turnback锁和seed状态hash |
| MAP-19 | C_CTRL/HX_A/HX_B/HX_C/P热区网络；固定max(0,T+load−cooling)及tick+2阀门队列；逐区读温、当前带状Observation与36个一步预测；提前冷却/延迟中停机降载两种策略产能48/30；精确20分第三条方案；三类热失控、温度10/产能20/阀预算边界；36行Oracle seed0双次回放（`2BDD37D9…8EB4D6E`） | 环境实现后验证阀命令成熟顺序、温度等号与熔断、读数隔离、产能边界和seed状态hash |
| MAP-20 | S到A/B/C限流支管与A-B/B-C双向旁路；固定20%损耗和十分之一整数流量；A区保护/动态轮换两种水热策略（产能56/59）及精确15分方案；72分线性能量松弛上界；三类失败、三处边界；30行seed0专属Oracle双次字节一致（`02A88075…237547`） | 环境实现后验证支管/总源预算、旁路转送与损耗、区阀原子约束、热边界、精确读数隔离和seed状态hash |
| MAP-21 | O-R-W-S-E采样链与O-E六tick直撤路；喷发隐藏时刻12/16/20及一次2tick有噪测量，Bayes信息增益0.138nats；R/W/S三级样品与一tick包装加固；四条独立路线期望100/105/112/120分，信号分流政策112.02分、存活率96%；三条因果失败与tick12同刻到达边界；15行seed0公共Oracle双次hash一致（`13125598…4B205EA`） | 环境实现后验证隐藏时刻与似然采样、posterior更新、计时中断、样品包装/计分、同tick撤离和seed重放 |
| MAP-22 | 12节点15边人工森林图、12种唯一路标（4个相似三叉口细节对照）、局部方位/禁止全图查询；A-L最短唯一往返8步、两条节点不相交路；无记忆贪心J-K循环；外部记忆18步全边巡回写27条证据卡；完整DFS恰好30步回营；三条失败、30/31边界；18行seed0公开Oracle双次hash一致（`85404A0A…86752D6`） | 环境实现后验证局部可见性、观察/写记忆事实门、无自动返程、目标追踪和30步终止顺序 |
| MAP-23 | 三种真入口的成组私有线索画像；北林/河谷二分线索、山脊精确线索及低成本直接试探；四策略×三变体逐步补给账、信息增益/补给效率、三条因果失败和真入口正补给边界；9行seed0公开Oracle稳定审计（`01DCF7D5…CF4E3E8`） | 环境实现后验证seed隐藏变体、付费线索、缓存/调查顺序、受困判断和Observation隔离 |
| MAP-24 | 六节点七边手工图；桥于tick8移除A-B/B-C、局部潮窗相位隐藏、F慢路常开；桥抢运tick7/探桥更新tick14/山路潮窗tick11/旧笔记恢复tick15四条手算路径；三类因果失败、桥上与tick24/25边界、四相位潮窗离线审计；11行seed0 Oracle双次hash一致（`33C3799D…D992CFEF`） | 环境实现后验证事件顺序、局部地图刷新、受困判断、潮窗相位和截止端点 |
| MAP-25 | H-T-A-S气闸/EVA链；两种tick17、耗氧6的手写成功顺序；typed工具6/6有效；三条失败轨迹与六个氧气/Schema边界；16行seed0 Oracle稳定离线审计（`84B061A7…28E0DF1`） | 环境实现后验证气闸危险动作顺序、工具schema、逐tick氧气、零氧返舱与诊断隔离 |
| MAP-26 | T-D-A-B诊断/维修链；三seed固定故障与九项确定测试；先诊断tick11/反馈回滚纠错tick16两条成功路线，均留1枚备件；盲换、重复同错加价、忽视测试三类失败；六个库存/重试/一致性边界；12行seed0 Oracle稳定审计（`9040C1B0…69C7016`） | 环境实现后验证seed真值隔离、测试确定性、错误替换反馈、回滚恢复、重试计数和备件终止条件 |
| MAP-27 | 五节点远近道路；二格货舱、14电/18氧、一次性充能；先修中继tick25/余电0氧3与先稳定伤员tick20/余电2氧6两条独立成功策略；缺医疗包、误判稳定状态、无充电远路被困三条失败；六个充能/货位/返程/氧气/seed边界；18行seed0 Oracle稳定审计（`991B3D81…339E2634`） | 环境实现后验证载荷与道路原子成本、一次充电、relay救援门槛、被困判定和全目标回基地 |
| MAP-28 | H-V-G-K-S-V环路和A档案支线；锁日志/鞋印/登记/目击四种来源；Celine、S-V、21:06/21:14唯一真相证明；每个主张需双来源；先物证与先证词两条tick20手写成功调查、三条终局失败和六个边界；21行seed0 Oracle稳定审计（`8F0FFFFB…AD313887`） | 环境实现后验证证据局部披露、ID记录门、来源类别支持、时间和路径enum、一次提交与不泄漏真相 |
| MAP-29 | H连接L/K/Y/G，四名NPC固定知识/偏差；8问预算、重复答案固定耗预算；广泛询问19 tick/7问与高信息优先13 tick/3问；三条具体终局失败和六个问题/证据边界；14行seed0 Oracle稳定审计（`8D0B3CD1…BDA02C931`） | 环境实现后验证固定问答表、观察只含已问答案、NPC位置、八问预算、证据门、truth-neutral拒绝和Oracle重放 |
| MAP-30 | H-B-K-Y一层、L-A-T二层、K-T密道与H-J法庭；早期Q4将M-4解为Mara；B/K/T三事件的物证/条件证词链与4格结构化案卷；事件顺序25 tick、物证先行32 tick、渐进时间线34 tick三条手写成功路线；三条独立失败与一次错告恢复、Q4长间隔、NPC解锁、第40 tick边界；26行seed0 Oracle双次hash一致（`D35E73E4…64E3DDBE4`） | 环境实现后验证近期窗口/案卷边界、条件访谈、证据提交、错误指控次数、tick40结算顺序和终局隐私 |
