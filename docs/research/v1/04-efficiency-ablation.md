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

## 5. 验证（E1 在线对照完成，有效，保留）

- 离线：`tests/test_terminal_contract.py`（3 断言）+ `tests/test_e1_prompt_contract.py`
  （4 断言：规则存在、无码值、无地图 ID、无路线暗示）通过；全套 177 passed。
  E1 实现提交 `15834c2` 即实验代码版本标记（prompt 仍署 `react_v12_autonomous`，
  新旧靠 `base_prompt_hash` 区分：旧 `5dc2038b…` vs E1 `44229085…`）。
- 在线 EXP-E1（memory+E1, H5 R1 P1, B60, 飞船 v1, seeds 0–4）：**5/5 成功**，
  步数 35/29/31/28/30（均值 30.6），`invalid=0`，5 局**零 `read_terminal(载具)` 误用**，
  读码次数 2/1/1/1/1（读到即走，不重读）。
  对照 C111（同模型同 world 同 B60 同 H/R/P，旧 hash）：3/5，步数 36/35/60/60/45（均值 47.2）。
  按 seed 配对：0: 36→35、1: 35→29、2: 60→31、3: 60→28、4: 45→30——**5 格全部持平或更好**。
  token 效率：E1 均值 input 42k/output 16.6k vs C111 65k/34k（约 −35%/−50%）。
- 公平性：E1 文本经诚实性契约（无码值/地图 ID/路线），属通用 tool 语义，不构成
  `planner_assisted`（无下一动作建议、无路线）。未叠加 E2/E3，单变量归因成立。
- 结论：**E1 有效，保留**（prompt 第 7 条不撤回）。E2/E3 保持隔离未实施；
  REPEATED_CODE_READ 在 E1 组已消失（读码 ≤2 次），E3 暂无实施必要，记 deferred。
- 成本：6 次尝试（pilot 44 步 + 5 局）≈ input 260k / output 105k tokens，无中断。

## 6. 下一步

## 6. 下一步

实施 E1（prompt 版本 bump + 候选过滤），先离线可达性验证，再小规模在线对照；E2/E3 保持隔离，未证明则撤回。
