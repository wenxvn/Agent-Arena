# 0011. 七个新世界：十世界三十图

**日期**：2026-10-11
**状态**：Accepted（研究对照用）

## 摘要

在现有 3 世界 9 图之外新增 7 个世界（极地科考站/沙漠金字塔/废弃地铁/
火山观测站/丛林遗迹/月球基地/古堡），每个世界仍分简单 6 房/中等 8 房/
困难 10 房三档，共 21 张新图。规则代码零改动：同一套六工具、
同一谜题链（诊断/开盖/换芯/读码/逃生）、同一 `Action` schema、
同一 `Observation`/`WorldState` 隔离。新世界不是纯换皮：
每张图有独立拓扑、独立读码点、独立工具深度和独立诱饵位置，
最优公开路径长度各不相同（11–22 步）。

## 难度对照表

| 世界 | 简单（6 房） | 中等（8 房） | 困难（10 房） |
|---|---|---|---|
| 极地科考站 `polar-escape` | `polar-escape-easy-zh`（`POLAR-214`，11 步） | `polar-escape-v1-zh`（`POLAR-537`，19 步） | `polar-escape-hard-zh`（`POLAR-862`，21 步） |
| 沙漠金字塔 `pyramid-escape` | `pyramid-escape-easy-zh`（`SAND-107`，11 步） | `pyramid-escape-v1-zh`（`SAND-429`，15 步） | `pyramid-escape-hard-zh`（`SAND-756`，17 步） |
| 废弃地铁 `subway-escape` | `subway-escape-easy-zh`（`METRO-118`，13 步） | `subway-escape-v1-zh`（`METRO-440`，15 步） | `subway-escape-hard-zh`（`METRO-783`，21 步） |
| 火山观测站 `volcano-escape` | `volcano-escape-easy-zh`（`MAGMA-203`，13 步） | `volcano-escape-v1-zh`（`MAGMA-515`，19 步） | `volcano-escape-hard-zh`（`MAGMA-948`，17 步） |
| 丛林遗迹 `jungle-escape` | `jungle-escape-easy-zh`（`VINE-126`，13 步） | `jungle-escape-v1-zh`（`VINE-463`，20 步） | `jungle-escape-hard-zh`（`VINE-791`，22 步） |
| 月球基地 `lunar-escape` | `lunar-escape-easy-zh`（`LUNAR-134`，12 步） | `lunar-escape-v1-zh`（`LUNAR-572`，14 步） | `lunar-escape-hard-zh`（`LUNAR-908`，16 步） |
| 古堡 `castle-escape` | `castle-escape-easy-zh`（`CROWN-142`，13 步） | `castle-escape-v1-zh`（`CROWN-386`，19 步） | `castle-escape-hard-zh`（`CROWN-927`，21 步） |

## 拓扑设计（每世界不同）

- 极地：环形捷径（简单图工具间与诊断间直连成环）；中等工具藏在维修间之后；
  困难工具下沉到冰窖，读码回站前厅。
- 金字塔：菱形双通道（沙道/器物库两条路进机关墓室）；中/难读码点在勘测角，
  修好后就近读码再折返；诱饵岔道开在工具间旁。
- 地铁：干线加侧线（工具间/壁画站台/排水房都是干线侧线）；中等读码在维修角；
  困难排水房开在配电室旁，读码回站厅。
- 火山：工具在起点隔壁（拿完即跑长途）；困难读码在地震角，省去折返。
- 丛林：工具间是必经之路（中/难去神庙机房必须穿过补给库）；读码回营地，
  困难最优 22 步为全场最长。
- 月球：三角回路（隧道/备件库/遥测角互联）；诱饵气闸开在起点旁；
  中/难读码在遥测角，中等最优仅 14 步。
- 古堡：长链加狱后藏宝（简单工具在熔炉房之后；中/难工具与诱饵塔楼都在
  熔炉房之后，修前可误入）；读码回城门大厅。

## 决策

- 7 个新模块（`worlds/polar.py` 等）复用深海站规则形状，只换定义与文本；
  里程碑 `key_items` 为各世界双工具，诱饵不在清单内。
- 简单图读码终端在维修间（修好即读即走）；中/难读码终端在起点或诊断间，
  由拓扑决定，不统一。
- 21 张新 JSON 全部版本化（`easy-zh`/`v1-zh`/`hard-zh`），旧 9 图一字节未动；
  `create_environment` 新增 21 对 selector。
- 每世界一个测试文件，共 56 项：房间数、双向出口、selector 身份、
  精确步数公开通关、终端规则与逃生门禁、诱饵不挡路、维修顺序与发射守卫。

## 非目标

- 不新增工具、不新增规则类型；不为新世界定制 prompt、记忆或规划逻辑。
- 真实模型在新图上的 benchmark 另行安排，不在本 spec 验收内。

## 验收条件

- [x] 21 张新图：房间数、双向出口、读码前隐藏逃生出口的规则测试通过。
- [x] 21 张新图：公开动作序列通关（11–22 步，见上表）；新码生效、诱饵不挡路。
- [x] 全套 249 passed（含 56 项新测试），旧世界行为不变。
