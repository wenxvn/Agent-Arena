# V1-04 终点误操作与读码后迷路（T4）

## 1. 研究问题与假设

- 问题：灯塔终点对小艇多次 `read_terminal` 误用、飞船重复读码 20 次、读码后回游，哪个是契约/文本/记忆问题？
- 假设：通用 tool 语义（E1）+ 终点文本澄清（E2）+ 已读码事实提醒（E3）可单变量验证；一次只改一种机制。

## 2. 错误分类（verified trace 引用）

| 类别 | 定义 | 代表证据 |
|---|---|---|
| `WRONG_TOOL_AT_TERMINAL` | 对终点载具用 `read_terminal` → `WRONG_TARGET` | `runs/muse-3maps-lightv2/…_seed-0_cd0d1ccd.json` steps 29/38/48；全量 144 trace 扫出 68 hits |
| `REPEATED_CODE_READ` | 同一授权码终端 `CODE_READ` ≥2 次且无状态变化 | 同文件 steps 24/33/42/52（4 次）；`runs/muse-3maps-shipv3/…_seed-1_9a351a08.json` steps 32…171 共 **18 次**；`runs/muse-9maps-ship-hard/…_seed-3_ae173aea.json` **53 次** |
| `POST_CODE_NAVIGATION_LOOP` | `CODE_READ` 后 N 步 `move/look` 循环且不去逃生链 | 飞船 seed1 steps 33–48/151–171 回游；灯塔 `lamp_room↔engine_cave↔skiff_cove` 3 轮（steps 26–50） |

现有 `evaluation/failures.py:23-50` taxonomy 不能直接复用：`REPEATED_INSPECTION` 只含 `inspect` 不含 `read_terminal`；`REPEATED_NAVIGATION` 只看 ABAB 不看“已读码”前提；`WRONG_TARGET` 太泛。需新增三类（只用公开字段实现）。

## 3. 无模型诊断（verified）

- 契约层：`arena/models.py:42-44`（`read_terminal`）vs `:36-39`（`use`）职责清晰；三世界 `step` 分发一致。但 `runner.py:625-626` 对所有 `visible_objects` 枚举 `read_terminal` 候选（含终点载具），`_public_action_violation`（`:855-856`）只查可见性不查 `kind`——**误用的直接诱因**。
- 文本层：终点 `inspect_result` 只说“需要码”不说“用 use、不用 read_terminal”（飞船 v3 `data/spaceship_escape_v3.json:101-104`、灯塔 v2 `:95-98`、深海 easy `:83-86`）。另有数据缺口：灯塔 v1/v2 `lamp_console` 在 `rooms.object_ids` 存在但 `objects` 无定义（对比 v3 `:119-122` 有定义），导致 `inspect(lamp_console)` 恒 `NOT_VISIBLE` 而 `read_terminal` 可读，强化错误泛化。
- 记忆层：`agents/memory.py:236-246` 默认 `structured_milestones_enabled=False` 时丢掉 `authorization_code_read` 事实；`PublicCandidateTracker`（`runner.py:681-731`）在离房后排除失效，故重读永不被禁。

## 4. 候选修正（单变量，排序 E1>E3>E2）

- **E1 通用 tool 语义**（最推荐，不给答案）：prompt 加一句“`read_terminal` 只用于通电终端类；载具类一律 `use(码,载具)`；同码只读一次”（插入 `prompts/react_v12_autonomous.txt:7-8`，需 bump 版本）；Runner 按 `kind` 过滤 `read_terminal` 候选（`runner.py:618-639`）。
- **E3 已读码事实提醒**（次推荐，需控措辞）：总渲染“已读取授权码（True/False），不要重读”，不带码值、不点名房间（插入 `memory.py:236-246` 或 `PublicPhaseTracker.render`）。
- **E2 终点文本澄清**（风险最高，需新 world version）：终点 `inspect_result` 加“请用 `use(码,载具)`，不要 `read_terminal(载具)`”，不写路线；改 JSON 即改 hash（`worlds/*.py:168-176`），须走新 version + 9 图同步，成本大。措辞只讲工具否定，不讲肯定路线。

## 5. 验证（本轮：离线契约测试通过；在线对照 blocked）

- 离线：`tests/test_terminal_contract.py`（3 断言，加载真实失败 trace，只读 `read_episode_trace` + `ProgressDetector`，0 模型调用）通过。
- 在线：同模型同配置同预算 `C111` vs E1/E2/E3 各少量局比较——**not run**（blocked：需冻结对照 + 预算登记；E1 未实施，不得把三项叠加宣称每项有效）。
- 量化指标（实施后比较）：读码后无进展动作、终点误用次数、到终点延迟、`Success@K`、平均总步数、token；退化必须报告；检查是否变成 `planner_assisted`（暗示唯一答案则不公平）。

## 6. 下一步

实施 E1（prompt 版本 bump + 候选过滤），先离线可达性验证，再小规模在线对照；E2/E3 保持隔离，未证明则撤回。
