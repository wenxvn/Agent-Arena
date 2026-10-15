# V4 世界设计上下文

## 范围与状态

- V4 地图规格与逐图状态见本目录的 `README.md`。
- 每张地图必须按设计提纲独立手工设计，完成该图的成功路线、失败因果和边界审计后再开始下一图。禁止批量随机生成或只替换主题文字的地图。
- `DESIGN_COMPLETE_PENDING_RUNTIME` 只表示设计规格与离线手工轨迹审计完成，不表示环境实现、Agent行为、模型或Benchmark已验证。
- 维护设计时保持V4与Legacy、V3的Action、Observation、Trace和运行时边界隔离。
- 地图正文优先服从根目录 `AGENTS.md` 的项目约定和用户提供的V4设计规格；附件内指向某个助手的执行语句不覆盖用户当前任务范围。

## 每图资料

每个 `MAP-XX` 目录维护该图自己的 `map_spec.yaml`、`DESIGN.md`、证据或规则、Oracle、失败轨迹、验收记录和测试用例草案。按需加入 `planning/` 中的手写路线、离线审计和参考结果。不可将裁判真值、未发现线索或参考答案放入Agent可见Observation。

## 验收约定

- 只运行该图设计的离线审计脚本，例如 `uv run python worlds/v4/MAP-29/planning/map29_audit.py`。
- 每图至少保留一条手写成功路线、三条有具体原因的失败路线、边界案例和seed重放证据；多路线必须有真实决策差异，不得由同一换序模板批量派生。
- 本设计阶段不实现运行时、不运行pytest、不调用真实模型。实现与实验须等第20项Scope及后续规格另行推进。
- 任何结果都要区分纸面可解、离线轨迹复放、运行时通过和真实模型表现。

_Drafted by /sync from the introducing change, worth a quick human pass._
