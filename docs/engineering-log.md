# Agent Arena 工程事件记录

## 2026-10-13 修复 Linux CI 的 mypy 平台类型误报

事件：GitHub Actions run #65/#66 的 Ruff 通过，但 `mypy src` 失败并跳过 pytest。job annotations 未包含 stderr，日志下载需仓库高权限；本地 clean checkout 复现定位未依赖该日志。

改动：`budget.py` 的 Windows-only `msvcrt` 分支与已存在的 Linux `fcntl` 分支一致，在动态平台 API 边界增加 `cast(Any, ...)`；运行实现不变。

验证：锁定依赖的干净临时环境中，Windows 默认与 `--platform linux` 的 `mypy --no-incremental src` 均通过（各 49 个源文件）；Ruff 通过、全量 pytest 348 passed、`uv lock --check` 和 `git diff --check` 通过。修复 SHA 的 GitHub Actions 尚待验证，不提前报绿。

下一步：提交并推送此跨平台类型修复，检查对应 quality run；保持 S2 的 API 停止状态。

关联实现提交：待提交。

## 2026-10-13 BUDGET-03 通用 provider error，停止在线尝试

事件：最后一次登记的恢复运行 BUDGET-03 使用进程级 120 秒 request timeout；首个 v2 episode 的第 7 次请求以 `error_category=provider_error` fail closed。此前 6 次 usage 合计 10,043 tokens；失败请求按 25,156-token reservation 记账。账本为 7/488 requests、35,199 locally charged tokens，v2 汇总 0/2，v3 未启动。

改动与边界：BUDGET-01/02/03 的账本和 partial JSON/CSV 都保留。三账本合计 19/500 requests、100,137/4,000,000 locally charged tokens；三次失败 reservation 都不是 provider 实际 usage 证明。无 HTTP status；`provider_error` 无法从保存的 allowlisted 元数据进一步还原根因。按预登记不创建 BUDGET-04，不再发起该矩阵的 provider API 调用；S2 Gate 未完成，不推进 S3。

验证：读取 BUDGET-03 账本中的计数、状态、错误类别、预留额，以及 partial JSON 的零结果行；确认无 in-flight request、v3 目录不存在。没有追加 provider 请求。

下一步：保持三次失败尝试与预算记账在 registry 中可追溯；继续离线审计 V2 提纲和可完成的非 S3 工作。S2 在线证据仍不充分。

关联登记提交：`894f860`；BUDGET-03 执行使用推送 HEAD `d55ce2e`。

## 2026-10-13 BUDGET-02 timeout 与最后一次受限恢复登记

事件：使用安全错误分类实施 SHA `e884688e48c357eafc27251b994e3f6c805acb64` 启动 BUDGET-02；第一个 v2 episode 第 10 次请求被分类为 timeout，预算门禁封账并以 exit 2 停止。前 9 次 usage 合计 15,374 tokens，第 10 次按 25,478-token reservation 记账；BUDGET-02 合计 10 次 / 40,852 本地记账 tokens，v2 0/2，v3 未启动。和 BUDGET-01 合并为 12/500 requests、64,938/4,000,000 本地记账 tokens。

诊断：当前 OpenAI SDK request timeout 配置为 30 秒；budgeted CLI 强制 retries=0。timeout 类别来自保存的异常链分类，实际 provider usage 对第 10 次请求未知。原 BUDGET-02 登记规定错误后不再创建账本；基于本次已知 timeout 证据、仍未超出原总 cap/截止时间及用户要求继续维护，明确将该总体停止点修订为只再允许一个隔离的 BUDGET-03，不允许 BUDGET-04。

改动：BUDGET-02 ledger 和部分 JSON/CSV 原样保留；新预登记 BUDGET-03 使用剩余 488 requests / 3,935,062 tokens，唯一运行参数调整为进程级单请求 timeout 120 秒，其余条件和截止时间不变。新账本、输出目录、实现 SHA 与串行命令已写入 run registry。S2 Gate 仍未完成。

验证：仅读取 ledger 安全计数/状态、partial JSON 顶层摘要和 timeout 配置；未启动 v3 或其他 API 调用。待对 BUDGET-03 登记 commit/push 后，执行最后一次受限恢复；如果发生 provider error 则停止所有后续 API 尝试。

关联登记提交：`894f860`。

## 2026-10-13 provider error 安全分类与预算内恢复登记

事件：原 S2 M1 pilot 的第二次 provider 请求 unknown spend 封账；现有记录不足以区分 HTTP、连接或超时故障。

改动：budget ledger 新增 schema 2，采用固定错误类别与可选 4xx/5xx status；CLI 只显示这两个 allowlisted 字段，不记录或输出异常文本、response body、headers、prompt 或 credential。旧 schema 1 ledger 可验证后迁移；类别为基于异常链的 best-effort 诊断。独立复审没有硬性问题，补齐未知类别、无效/缺失状态码及类别不匹配的 fail-closed 负例。

验证：新增未知错误、HTTP status/敏感文本隔离、connection/timeout/invalid-response 分类、schema-1 迁移及篡改账本拒绝覆盖。定向测试 23 passed；全量 pytest 348 passed，Ruff 全仓、mypy 49 个源文件、`uv lock --check` 与 `git diff --check` 通过；没有 provider API 请求。

恢复安排：单独预登记 BUDGET-02，只使用原 request/token cap 的剩余 498 次和 3,975,914 tokens；绝对截止不晚于 BUDGET-01 的 deadline，使用新 ledger 与结果目录。登记 SHA、提交推送并完成门禁核对后再启动；发生新 provider error 时停止，不创建第三账本。

下一步：完成实施复审、冻结 SHA 和提交/推送 recovery 登记，再按原矩阵串行执行。S2 Gate 保持未完成。

关联实现提交：待提交。

## 2026-10-13 V2 S2 M1 pilot 因 provider error fail closed

事件：按冻结登记启动 Memory v2 的 seed 1；第 2 次 provider 请求报错后，budget guard 关闭账本并以 exit code 2 停止串行矩阵。

证据：请求 `af4ea921-3723-477a-b5e9-2b5a44d9d76e` 完成，usage 为 input 749 / output 760；请求 `087ee418-82cf-4a67-8cad-7e2f6bd21c33` 状态为 `unknown_spend_after_provider_error`，按预留 22,577 tokens 记账。ledger 为 2/500 requests、24,086/4,000,000 tokens，`provider_error_unknown_spend`，无 in-flight request。该 token 总额是本地预算记账，不代表 provider 确认消耗。

结果：v2 benchmark 汇总 0/2 episode、0 条结果行、无完成 trace；v2 seed 2 与 v3 两个 seed 未启动。部分 JSON/CSV、ledger 与请求 ID 均保留在本地 `results/`，不重置、不以同一 budget experiment ID 重试。没有 GPU 运行。

只读核查：OpenAI adapter 将 SDK exception 包装成通用 `DecisionProviderError`，budget wrapper 再包装成通用 `ProviderBudgetExceeded`；ledger 按 spec 不保留 provider 响应或异常元数据。因此无法从当前运行证据确定根因；该分类缺口与实际 provider 侧故障是两件事。

下一步：先评估是否需要添加仅含 allowlisted exception class / HTTP status 的安全分类，再单独登记任何恢复运行；不重置当前 ledger。S2 Gate 保持未完成，不能据此计算模型成效。

关联实现提交：`0d3bb0ba0b81ca682ea714941de7b5bd17fd03f9`；运行状态登记提交：`23b1bf2e9ad909370f9a2a2b34599b73750f71ca`。

## 2026-10-13 V2 seeded world identity hash 稳定性修复

事件：pilot 的两次 CLI 前置检查均在 world identity 门禁被拒绝；未到 provider adapter，没有 API 请求、预算账本或 benchmark 输出。

原因：同一 seeded flex world 在不同 Python 进程中得到不同 hash。隔离 `PYTHONHASHSEED=1/2` 后复现为 Pydantic 将 `FlexMilestone.key_items` 这个 `frozenset` 按迭代顺序序列化为数组。

改动：hash 前对 `key_items` 和 `trigger_reasons` 排序；新增跨进程、跨 hash seed 回归；运行登记表将使用修复后实测的稳定 hash。

验证：跨进程 `PYTHONHASHSEED=1/2/3` 下，seed 1、2 均得到 `bd1f77eabdcd032e80dbbaaad29163e85cbea34caf7486c22babcb3b85cb8373`；Ruff、mypy 49 个源文件、`uv lock --check` 通过，全量 pytest 339 passed，`git diff --check` 通过。没有真实 provider API 请求。

下一步：登记并发布修复后的源代码 SHA，随后启动同一组预算受限 pilot。

关联实现提交：`0d3bb0ba0b81ca682ea714941de7b5bd17fd03f9`。

## 2026-10-13 V2 S2 Provider Budget Guard 与 pilot 前置门禁

事件：完成 fail-closed provider request/token 预算门禁，并修复 provider 身份校验、活跃请求恢复和未完成 episode Trace 边界。

原因：S2 受限真实 pilot 需要跨 episode、跨 CLI invocation 的共享额度；并发启动不能误关正在运行的账本，预算或 provider 失败也不能伪装成完成局。

改动：新增持久化预算账本、请求输出上限、expected provider/model/world/prompt 身份冻结、OS invocation/request leases、terminal status 与关闭原因校验、截止时间后 usage 记账、预算异常传播、不落未完成 Trace，以及预算中断或后续 cell 身份不匹配时保留已完成 benchmark 汇总并非零退出；登记表记录共享 cap 与执行命令，并要求 pilot 后逐条核对账本事件。

验证：Ruff 通过；mypy 49 个源文件无问题；全量 pytest 338 passed；`uv lock --check` 通过；`git diff --check` 通过。未发起真实 provider API 请求，未读取或输出 `.env` 内容。

下一步：按登记表启动共享预算内的 Memory v2/v3 配对 pilot；pilot 结果仍须以真实 trace 和账本逐条核验。

关联实现提交：`0a09a4f479cd8b6ba49dd0eeefed80a47d623c06`。

前置核验更正：以 `118e8e…` 和随后单进程计算值 `418ccc…` 启动的两次 CLI 检查均因 world identity 不匹配而拒绝；API 尝试数为 0，未创建账本或结果目录。复现发现两值都不是稳定 identity，根因与修复见上方“V2 seeded world identity hash 稳定性修复”事件。provider/model 与 prompt 身份检查匹配。

## 2026-10-13 V2 S2 Memory v3 离线实现与 pilot 门禁

事件：按 S1 seeded 长尾证据实现可选 Memory v3 Spatial/Event，并完成离线验证。

原因：V2 提纲要求先验证公开房间/边/frontier 与因果事件记忆，同时保持 Memory v2 默认行为；真实实验必须有可执行的全局请求数和 Token 预算。

改动：新增 spec 0014、Memory v3 reducer/renderer、CLI/config 版本选择、可选逐步记忆统计、审计表统计字段和离线回归 fixture；补充 V2-03 报告及 S2 pilot 预登记。另保留有界的完整公开访问房间集合，避免 v2 的 12 项有损地点列表漏掉已访问房间后误报 frontier。

验证：Ruff、mypy（48 个源文件）通过，pytest 316 passed；Trace 审计仍为 518 个文件、474 个唯一 episode。没有真实模型调用或 GPU 运行。检查 provider 代码确认目前不存在跨局 request/token 预留器，且非所有决策 provider 都有单请求输出上限，因此 pilot 明确 blocked。

下一步：补齐 fail-closed 全局预算门禁并验证所选网关遵守输出限制；完成受限 pilot 前不推进 S3。

关联实现提交：`5cea009`。

## 2026-10-13 V2 S1 既有 Trace 离线审计完成

事件：完成 V2 S1 离线瓶颈盘点，产出可复现脚本、CSV/JSON 审计产物和 Top 5 假设报告。

原因：需要将本机既有 trace 按 attempt、配置、地图家族、seed 角色分层，避免将网关中断、重跑和行为结果合并成单一成功率。

改动：新增 scripts/audit_v2_traces.py 与对应测试；扫描 runs/ 和 results/ 下 518 个文件，去重为 474 个 episode_id，44 个副本无冲突；生成 docs/research/v2/assets/trace-audit.csv、trace-audit.json 和 02-bottleneck-audit.md。产物排除 decision_reason；报告区分 provider_error、step_limit 与成功 trace，记录 seeded 长尾、终端读取、use 工具配对、重复失败动作及 progress 代理指标。

验证：Ruff 通过；mypy 48 个源文件通过；pytest 305 passed；GitHub Actions #57 quality job 全部通过。审计为离线读取，0 次 LLM 调用、0 次 GPU 运行。

下一步：S2 先验证 M1 空间/边/frontier 与公开里程碑的 Memory v3 假设；配置固定前不启动对照。

关联实现提交：a372dce。报告和聚合产物随本记录提交。

## 2026-10-13 V2 S0 CI 门禁修复并通过

事件：清理基线 HEAD 的 Ruff 与 mypy 问题，并使 CI 测试不依赖本机生成数据。

原因：初始 Actions #54 的 Ruff 失败阻止 mypy/pytest；修复后的 #55 暴露 9 项测试依赖被 Git 忽略的 runs/ 与 results/。

改动：完成类型与 Ruff 修复；将 UI 测试输入改为临时目录和合成 trace/CSV，保留本机生成数据和用户目录。

验证：本地 Python 3.13.16 / uv 0.13.0 临时环境的 Ruff、mypy（48 个源文件）、pytest（303 passed）、uv lock --check 和 git diff --check 均通过。GitHub Actions #56 quality job 全部通过。

下一步：进行既有 Trace 的 S1 离线审计，按来源和条件拆分首条记录代理、删失与行为结果。

关联提交：d9d13e4、d40f3e6；[run #56](https://github.com/wenxvn/Agent-Arena/actions/runs/38358490666)。

## 2026-10-13 只读研究 UI 维护与边界收紧

事件：修复空步骤 Trace 的分页边界，并收紧只读 UI 对 Trace 与 benchmark CSV 的文件路径边界。

原因：真实启动时单页滑块因 `min_value == max_value` 抛错；代码审查发现 CSV 可指向任意路径、Trace 符号链接可能越出实验目录，且 CSV 深度需遵守一级子目录约定。

改动：单页直接使用第 1 页；Trace 校验最终路径并限制为实验目录直接子文件；CSV 仅允许 `runs/`、`results/` 根目录或一级子目录；README、架构、scope 与 Agent 上下文同步只读 UI 能力、启动方式和最新状态。

验证：`PYTHONPATH=src py -3.11 -m pytest -q` 为 304 passed；浏览器页面可见，Streamlit health 返回 HTTP 200；`git diff --check` 通过；两项独立审查复查无新增问题。当前主机未安装 `uv`、Ruff、mypy，标准 Python 3.13 检查未运行。

下一步：扩大 seeded 实例覆盖并分析长尾步数；新在线实验需先登记预算和固定对照条件。

关联提交：`1bae22c`。

## 2026-10-11 V1 缺口续作：T6 跨任务证据、E1 新世界验证、UI 四视图

事件：V1 收官后并行会话续作三项——flex pilot 真实 30/30 + seeded 15/15
（跨任务迁移成立，seeded 长尾 232/159 步）；187 成功 trace 离线 E1 扫描
（终点误用 0、重读 4 次，E1 泛化成立但无新世界对照组）；UI 只读 MVP 升级
4 视图（回放分页/矩阵总览+Success@K/错误热点/条件对照）。
原因：SUMMARY 点名的三项未做（跨任务泛化、E1 新世界复验、前端优化）；
T7-Reflection deferred 为合法终态，不硬做。
改动：新增 `docs/research/v1/08-cross-task-and-e1.md`（不碰已冻结 00–07
与 SUMMARY）；`ui/present.py` +4 纯函数、`ui/app.py` 4 视图；
UI 测试 10 新增/同步。
验证：`PYTHONPATH=src python -m pytest -q` 全套通过；E1 扫描零新调用。
下一步：全量 seeded 推广与跨任务泛化讨论（V1 T6）；commit/push。
关联提交：`a3ec4f5`。

## 2026-10-11 pilot/seeded 7 配置真实模型 35/35 通关

事件：6 张 flex pilot + 飞船 seeded 共 7 配置 × 5 seeds 获 35/35 成功；
seeded 图出现 232/159 步长尾（工具分置双容器迫使多趟奔波），固定图无此现象。
原因：用户要求把剩下的图全部跑完；同获胜组合，21 并发池一次通过，
无网关限流、无补跑。
改动：仅实验运行；新增 `scripts/run_flex_matrix.py`；trace 在
`runs/muse-flex-*`（本地生成物）；spec 0012、scope §K 更新。
验证：逐局 trace 离线汇总：月球分支 35.8/seeded 97.0、古堡并行 47.6/
seeded 48.6、金字塔反转 35.6/seeded 62.8、飞船 seeded 41.0，非法输出 0。
下一步：全量 seeded 推广与跨任务泛化讨论（V1 T6）。
关联提交：`9a2d9d1`。

## 2026-10-11 旧三世界 9 张重制图建成，全套 293 passed

事件：边集审计确认旧 9 图换皮后，用 9 张独立拓扑新版本替换它们在 10×3
矩阵中的位置（旧图冻结，selector 保留）；途中修好新旧版本 selector
撞车（abyss/light 走各家序列号）与两处测试路线 bug。
原因：用户要求去换皮，否则测试没意思；新 10×3 = 9 重制 + 21 新世界图。
改动：9 个 JSON + 三引擎各追加 V4/V5/V6（abyss 为 V2/V3/V4）定义与环境类
+ `worlds/__init__.py` 新增 9 对 selector + 3 个新测试文件（22 项）+
spec 0013；旧 30+6 图一字节未动。
验证：`PYTHONPATH=src python -m pytest -q` 293 passed；9 图公开通关
（20/13/12、22/21/16、24/19/17），诱饵/门禁/陷阱项全过。
下一步：9 重制 × 5 seeds 真实模型矩阵（45 局，21 并发池，不停到全通），
再与 105/105 合并为新 150 局报告；commit/push。
关联提交：`98d50ab`。

## 2026-10-11 新 10×3 矩阵 150/150 完成

事件：9 张重制图 45/45（第一波 42/45，3 局网关中断第二波补齐），
与 21 图 105/105（同条件：memory + history5 + recovery + phase + 不限步 +
`muse-spark`，seeds 0–4）合并为新 10×3 矩阵 150/150。
原因：用户要求去换皮后跑满 10×3×5，不停到完；21 图沿用已有 105/105，
只新跑 9 重制 45 局。
改动：仅实验运行；`scripts/run_redesign_matrix.py`（多轮池式执行）已提交；
trace 在 `runs/muse-redesign-*`（本地生成物）；scope §L 更新。
验证：逐局 trace 离线汇总：重制三图均值飞船 31.6/38.4/44.4、
灯塔 24.2/41.2/51.2、深海 24.2/33.4/34.4，全部随难度单调递增，
非法输出 0；旧 9 图 45/45 封存。
下一步：pilot/seeded 图真实模型对照（预算登记后）。
关联提交：`59064c5`。

## 2026-10-11 flex 引擎与 6 张 pilot 图建成，全套 271 passed

事件：按用户确认的四个优化方向交付：flex 参数化引擎（分支/并行/反转）、
难度三杠杆打标（spec 0012 表格，离线）、3 张 pilot 图各带 1 个深诱饵、
3 张 seeded 图（工具双容器分配）。
原因：105/105 证明单链已无瓶颈，需验证换任务结构后能力是否还在；
全部走新版本，旧 30 图与 V1 基线不受影响。
改动：`worlds/flex.py` + 6 个 JSON + `worlds/__init__.py` 新增 6 对 selector
+ `arena/models.py` 加 `CELL_STAGED`（加法）+ 3 个新测试文件（22 项）+
spec 0012；测试抓到 `_escape` 不查电源的旧假设 bug 并修复。
验证：`PYTHONPATH=src python -m pytest -q` 271 passed；6 图公开通关
（19/22/16）、分支任一供电、并行缺件断电、无电读码/无电禁逃、
seeded 确定性/差异性/可解性全部通过；本机无 ruff/mypy/uv。
下一步：pilot 图真实模型对照（预算登记后）；全量 seeded 推广待定。
关联提交：`6577388`。

## 2026-10-11 新 21 图真实模型 105/105 通关

事件：Muse 自主组合（memory + history5 + recovery + phase，不限步）在 7 个
新世界 21 配置 × 5 seeds 获 105/105 成功，七图均值步数全部随难度单调递增。
原因：验证新图可通关且难度梯度成立；首波 105 并发触发网关系统性限流，
104 局开局中断，全部 trace 保留并降并发重跑。
改动：仅实验运行，无代码改动；新增 `scripts/run_21maps_matrix.ps1`、
`scripts/run_episode.py`、`scripts/rerun_21maps_pool.py`、
`scripts/summarize_21maps.py`；trace 在 `runs/muse-21maps-*`（本地生成物，
不进 Git）；scope §J 更新。
验证：离线汇总 21 配置全部 5/5，非法输出总共 1 次；尝试分母=首波 105 +
重跑 104 + 补跑 4（含 1 冒烟，另计）。
下一步：把 105/105 纳入 V1 提纲 T2 离线重评与 T6 泛化讨论；commit/push。
关联提交：`452d2b1`。

## 2026-10-11 十世界三十图建成，全套 249 passed

事件：新增极地/金字塔/地铁/火山/丛林/月球/古堡 7 个世界，各分三档难度，
共 21 张新图；每张图独立拓扑与读码点，最优公开路径 11–22 步。
原因：用户要求从 3 世界扩到 10 世界，且明确不要纯换皮。
改动：`worlds/{polar,pyramid,subway,volcano,jungle,lunar,castle}.py`（规则复用，
只换 definition）+ 21 个版本化 JSON + `worlds/__init__.py` 新增 21 对 selector
+ 7 个新测试文件（56 项）+ spec 0011；旧 9 图一字节未动。
验证：`PYTHONPATH=src python -m pytest -q` 249 passed（含 56 项新测试）；
21 张图全部公开动作序列通关，新码生效、诱饵不挡路；本机无 ruff/mypy/uv，
只跑了 pytest。
下一步：真实模型新图 benchmark（预算登记后执行）；commit/push 本轮全部改动。
关联提交：`e8da39d`。

## 2026-10-11 V1 提纲在线收官（33 次尝试，全部提交）

事件：用户批准在线对照后，完成 C011/C010/React-C111/E1/Pctx/SeedSmoke 全部在线格；
T7-B UI MVP 实现；与并行会话的 7 世界扩展兼容共存。
原因：离线审计已定位缺口，低成本 pilot 逐个验证契约后放量。
改动：`docs/research/v1/`（00–07 + SUMMARY 定稿）、E1 prompt 第 7 条（保留）、
`worlds/variants.py` + seeded JSON + 注册、`ui/present.py` + `ui/app.py`、
7 个新测试文件；`docs/scope/scope.md` 收官状态。
验证：`PYTHONPATH=src pytest` 249 passed；在线 33 尝试全部记账；
`git diff --check` 通过；ruff/mypy 待 CI。
下一步：CI 全绿确认；E1 与消融结论在 7 新世界的复验；跨任务泛化与 Streamlit 部署。
关联提交：`050a31a/abafbe6/15834c2/5cb869e/ac9da24/7286a69/c733c45/a0166b3` + 本批收官。

## 2026-10-11 V1 提纲 S0–S1 完成、S2–S6 部分（离线先行、在线阻塞）

事件：按 `研究提纲/V1研究提纲.md` 执行 T1–T7；T1 CI 红灯修复与运行台账、T2 离线重评完成；T3–T7 审计/设计/离线契约测试完成，在线补测阻塞。
原因：把“45/45”从叙述变为可追溯证据；成本控制要求先离线后在线，不重跑已有完整实验。
改动：`tests/test_phase_tracker.py` 去未使用导入；新增 `docs/research/v1/`（00/01/02/03/04/05/06/07/SUMMARY + assets）；新增 `scripts/build_run_register.py`；新增 `tests/test_success_at_k.py`、`test_terminal_contract.py`、`test_phase_prior_audit.py`、`test_seed_replicate.py`；`docs/scope/scope.md` 加 V1 状态。
验证：`PYTHONPATH=src python -m pytest -q` 173 passed（159+14 新）；`build_run_register.py` 生成 144 行台账；`ruff/mypy/uv` 本机缺装，CI 全绿待 push 后确认；在线实验 0 次新调用。
下一步：push 后取 CI 链接；登记预算后补 C011/React-C111、E1 在线、P-v1-context、新实例冒烟。
关联提交：待提交（分 T1/T2/T3–T4/T5–T7 四批独立 commit）。

这份记录只保存重要的工程事件，不替代 scope、spec 或 Git 历史。

记录范围包括：阶段开始或完成、架构决策确认或修改、重要验证结果、阻塞及解决、开发优先级调整。

每条记录使用以下结构：

```text
## 日期 事件名称

事件：发生了什么
原因：为什么做
改动：主要文件或范围
验证：运行了什么，结果如何
下一步：接下来做什么
关联提交：Git commit，若有
```

## 2026-10-11 三图难度对齐地图完成，实跑进行中

事件：灯塔扩建为 8 房 v2（工具箱搬进地窖、诱饵房/物、新授权码），新增第三世界
深海站 v1（8 房飞船形拓扑、新名称新授权码）；三张图最优公开路径 16–19 步。

原因：此前只有飞船 v3（8 房难图）和灯塔 v1（6 房简单图），用户要求 3 张难度
相当的地图做测试，并把简单的灯塔加难。

改动：`worlds/data/lighthouse_escape_v2.json` + `LighthouseV2Definition`/
`LighthouseV2Environment`（规则复用）、灯塔储物箱可见逻辑按容器房间泛化、
`worlds/abyss.py` + `data/abyss_escape_v1.json`（新 id 新谜题文本，同规则形状）、
`worlds/__init__.py` 注册两对 selector、`cli.py` 类型标注；
`tests/test_lighthouse_v2.py`、`tests/test_abyss.py`；`docs/specs/0009-*`。

验证：全套 `pytest` 143 passed（含 11 项新测试）；灯塔 v2 16 步、深海站 19 步
公开路径通关测试通过，旧码/诱饵/隐藏出口拒绝行为均覆盖；本机无 ruff/mypy/uv，
只跑了 pytest。Muse 自主组合（memory + history5 + recovery + phase，不限步）
三张图 seed 0 实跑已在后台启动。

下一步：等三局实跑结果，成功则扩到 5 seeds 并归档，失败则分析 trace；
commit/push 本轮全部改动。

关联提交：待提交。

## 2026-10-11 三图自主通关对照完成

事件：Muse 自主组合（memory + history5 + recovery + phase，不限步）在三张
8 房图上全部取得通关样本：深海站 seed 0（41 步）、灯塔 v2 seed 0（56 步）、
飞船 v3 seed 2（113 步）/ seed 1（180 步）。

原因：验证三图难度对齐后 AI 是否都能自主通关。

改动：仅实验运行，无代码改动；trace 在 `runs/muse-3maps-*`（本地生成物，
不进 Git）。

验证：4 个 success trace（0 非法输出）+ 2 个飞船 seed 0 `provider_error`
trace（73/76 步，0 非法输出）。关键发现：飞船 seed 1 重读授权码 20 次、
游荡 150+ 步才逃生，不限步数是通关前提；新图一次过证明能力迁移而非背路线；
灯塔 v2 终点模型 3 次对小艇用错 `read_terminal`（inspect 文本措辞可优化）。

下一步：三图各补到 5 seeds 归档；考虑把逃生舱 inspect 文本改得更动作导向；
commit/push 本轮全部改动。

关联提交：`6deee65`。

## 2026-10-11 三档难度建成与 9 局全覆盖 9/9 成功

事件：每张地图设简单/中等/困难三档（简单复用 6 房图，困难新建 4 张 10 房图），
Muse 自主组合 9 局全覆盖（3 图 × 3 难度 × seed 0，不限步）9/9 成功。

原因：用户要求每图三档难度（当前 8 房为中等）并做多 AI 并行探索。

改动：4 个新地图 JSON（飞船 v4、灯塔 v3、深海简单/困难）、4 个规则复用
环境子类、`create_environment` 新增 4 对 selector（spec 0010）、4 个新测试文件；
9 并行实跑（独立网关 session），trace 在 `runs/muse-9maps-*`（本地生成物）。

验证：全套 `pytest` 159 passed（含 16 项新测试）；9 配置 × 5 seeds = 45/45 成功，
均值步数飞船 70.4/140.8/165.4、灯塔 39.8/49.4/105.8、深海 26.8/42.2/83.6
（三图均值全部单调递增，中位数飞船 42/147/100）。6 次网关 `provider_error`
重跑均恢复；37 并行未触发系统性限流。

下一步：终点 `read_terminal` 误用与读码后迷路的 prompt/文本消融；
Planning 配相同公开上下文；commit/push 本轮全部改动。

关联提交：待提交。

## 2026-10-11 飞船扩建 v3 与不限步数 5/5

事件：飞船扩建为 8 房 v3（诱饵 + 新授权码），`step_limit=0` 支持不限步数；Muse 自主组合在 v3 以 5/5 成功逃生。

原因：检验更大地图与诱饵下的探索效率；此前成功路径 35–57 步，30 步预算成为人为瓶颈。

改动：`worlds/data/spaceship_escape_v2.json`、`SpaceshipV2Definition`/`SpaceshipV2Environment`（规则复用，仅换 definition）、储物箱可见逻辑按容器房间泛化、`config` 允许 `step_limit=0`、Runner 循环与 CLI 显示适配；`tests/test_spaceship_v2.py`。

验证：全套 `pytest` 132 passed；19 步公开路径通关测试通过；Muse 自主组合 v3 5 seeds 5/5（152/125/153/93/65 步），trace 归档于 `results/muse-shipv3-unlimited(-s24)/`。中途一次后台进程静默死亡（seed 2–4 未跑），改用 `-u` 无缓冲输出并凭进程与 trace 双重确认存活后重跑解决。

下一步：Planning 配相同公开上下文；ReflectionAgent；Streamlit；commit/push 本轮全部改动。

关联提交：待提交。

## 2026-10-11 雾岛灯塔世界与迁移 5/5

事件：新增第二个确定性世界（雾岛灯塔，spec 0007），Muse 自主组合在新地图 5/5 成功逃生；阶段上下文泛化为世界声明里程碑，Runner 不再内置飞船知识。

原因：检验通关能力是否迁移到未见地图，而非背下飞船路线；灯塔首轮无 phase 时 0/5（死法与飞船一致），证明阶段标签不可或缺，倒逼其泛化。

改动：`worlds/lighthouse.py` + `data/lighthouse_escape_v1.json`、`worlds/__init__.py` 注册、`arena/models.py` 新增 `PublicMilestone`、`arena/environment.py` 新增 `public_milestones` 默认空、`evaluation/runner.py` 的 tracker 改里程碑驱动（飞船旧文本逐字保留）、`agents/planning.py` 不变、`cli.py` 类型标注更新；`tests/test_lighthouse.py` + `tests/test_phase_tracker.py`。

验证：全套 `pytest` 126 passed；灯塔 15 步公开路径通关测试通过；Muse 自主组合灯塔 5 seeds 5/5（27/28/28/55/57 步），trace 与 failure_analysis 归档于 `results/muse-lighthouse-h5rp(-s14)/`。

下一步：压缩成功路径回 30 步预算；Planning 配相同公开上下文；ReflectionAgent；Streamlit。

关联提交：待提交。

## 2026-10-11 首个真正自主通关

事件：Muse Memory 在 `--autonomous` 下 5 seeds 获 3/5 成功逃生（seed 0/1/4，36/35/45 步），全部 Action 由模型自主返回并校验。

原因：Phase 1–3 逐个证伪预算/历史/卡死恢复都不充分；Phase 4 加入公开阶段上下文后模型首次把授权码与逃生舱绑定，此前 15 局全倒在这一步。

改动：仅实验变量组合（history5 + stuck_recovery + phase_context + 60 步），无代码改动；结果归档于 `results/muse-memory-s60-h5rp/`（benchmark JSON/CSV + failure_analysis + traces）。

验证：trace `outcome=success`、`agent=memory`、终局动作为模型输出的 `use(ALPHA-731 → escape_pod)`；provenance 中 hints/candidates/selection/guard 全关；全新 seeds 5–9 复验 2/5（seed 5/9，均 57 步），可重复性确认；消融矩阵：history-only 0/5、phase-only 0/5、history+phase 1/5、三者组合 3/5。

下一步：单变量消融已完成（history/phase/recovery 互补）。后续方向：把成功路径压缩回 30 步预算（当前需 35–57 步）、PlanningAgent 配相同公开上下文、ReflectionAgent，以及 Streamlit。

关联提交：待提交。

## 2026-10-10 Windows + Muse provider 切换与自主基线

事件：真实实验 provider 从 Mac 本地 Ollama（`qwen2.5:7b`）切换为 Windows 下 OpenCode Zen 网关的 `muse-spark-1.3-contributor`；完成 React/Memory 各 5 seeds 自主对照，并适配网关严格 schema。

原因：换到 Windows 后本地 Ollama 需重装且 Python 仅 3.11（项目要求 3.13 + uv）；用更强 API 模型能更快取得首个深阶段样本，验证瓶颈是 grounding 还是模型规模。

改动：`src/agent_arena/config.py` 新增 `openai_session_id`（网关强制 `x-opencode-session` 请求头）、`src/agent_arena/llm/openai.py` 注入该头并把验证输出上限调到 1024（推理模型空回复问题）、`src/agent_arena/llm/protocol.py` 新增无 `$ref` 的 `decision_response_schema_strict()` 和全 required 的 `planner_response_schema_strict()`、`src/agent_arena/agents/planning.py` 增加 `""`→`None` 归一化；`.env`（本机）与 `.env.example` 更新；`docs/current-issues.md` 登记 Muse 基线。

验证：`verify-model --provider openai` 通过；Muse React 0/5（控制室/走廊循环，非法输出 0）、Memory 0/5（工具 3/5、电源 2/5、读码 1/5）；`uv` 不可用故用本机 Python 3.11 + `PYTHONPATH=src` 跑 `pytest`：118 passed。附带修好两个测试问题：本机 `.env` 会污染 CLI 测试（改走真实 provider 并挂起网络），新增 `tests/conftest.py` 做 env/dotenv 双隔离；验证输出上限 32→1024（推理模型空回复），同步更新 `test_openai_provider.py` 断言。Planning 5 seeds 曾因 Planner schema 被网关 400 而 `provider_error`，修复后正在重跑。

下一步：Muse 三组对照已完成（React/Memory/Planning 均为 0/5，无可重复成功样本）。下一步是失败步骤人工抽样 + 单变量消融（优先：PlanMonitor 重规划阈值、Executor grounding 约束），再决定 PlanningAgent v2、ReflectionAgent 和 Streamlit 的顺序。

关联提交：待提交。

## 2026-09-10 Planning v1 Failure Analysis 与 Evaluation v2 完成

事件：完成 PlanningAgent v1 的失败分析基础设施、Evaluation v2 和真实 5 seeds 独立重跑；v1 Planner→Executor 核心保持冻结。

原因：原始 Planning v1 在 `qwen2.5:7b` 下 0/5 成功，单纯的 persistent-state no-progress 指标无法区分首次获得公开事实与重复已知结果，必须先提高测量有效性再决定是否改 Agent。

改动：新增 episode-local `PublicFact`/`EpisodeKnowledge`、State/Epistemic Progress、结构化 `SuccessCriterion` 及 legacy evaluator、规则 Failure taxonomy、Trace schema v2、`analyze-trace(s)` CLI 和 Evaluation v2 benchmark 字段；生成 JSON/CSV 失败分析报告，并同步 scope、架构、研究摘要和当前问题记录。未引入 ReflectionAgent、Streamlit、第二个 world 或 PlanningAgent v2。

验证：`uv run ruff check .`、`uv run mypy src`、`uv run pytest -q`（116 passed）、`uv lock --check` 和 `git diff --check` 全部通过。Evaluation v2 固定 `qwen2.5:7b`、seed 0–4、30 步、autonomous 重跑为 0/5 成功；平均 Planner call ratio 85.3%、State Progress 0、Epistemic Progress 1、无进展动作 29、同子目标重复 Action 26。每局自动识别 3 次 rejected action 和 2 次 repeated failure。

下一步：扩展已完成的人工抽样到每局完整的 replan 后首个 Action，区分 vague/wrong subgoal、wrong action、forgotten fact 与 ineffective replan；随后在保持 v1、模型、world 和 prompt 不变的条件下进行单变量 grounding 或 exploration/recovery 验证，再决定是否创建 PlanningAgent v2 spec。

关联提交：`6504db8`。

## 2026-09-10 文档同步与 PlanningAgent 真实五个 seed 对照

事件：修正文档中已过期的实验契约描述，并完成 PlanningAgent v1 的本地真实模型固定 5 seeds 对照。
原因：`a308dd5` 和 `07f7457` 已关闭 world selector、公开循环状态、benchmark 指标和 planner feedback hash 等工程缺口，但持续文档仍将它们列为未完成；PlanningAgent 的真实研究验收也需要实际结果。
改动：更新 `README.md`、`研究总纲.md`、`docs/scope/scope.md`、`docs/current-issues.md`、`docs/autonomous-escape-experiment-plan.md`、`docs/model-passage-options.md` 和 Planning spec 验证记录；Ollama loopback 请求绕过系统代理，并补充 provider 回归适配。
验证：标准 `uv run agent-arena verify-model --provider ollama` 通过；`qwen2.5:7b`、`spaceship-escape-v2-zh`、temperature 0、30 步、seed 0 至 4、`--autonomous` 的 Planning benchmark 为 0/5 成功，平均重复动作比例 93.3%、连续 `look` 26 次、唯一公开状态 1 个、Planner 调用 28 次、子目标完成率 0%、总 token 141,445；96 项 pytest、Ruff、mypy 通过。
下一步：公开并分析 React、Memory、Planning 的成功/失败 trace，优先研究高层子目标到有效移动/工具动作的桥接；在取得可重复成功前，Reflection 和 Streamlit 继续后置。
关联提交：`a7aedf5`。

## 2026-09-09 PlanningAgent v1 工程闭环完成

事件：完成 PlanningAgent v1 的工程实现，形成独立的 Planner、结构化 PlanState、PlanMonitor、Executor integration、计划生命周期 Trace 和 Benchmark v3 指标。
原因：ReactAgent、MemoryAgent 和公开规则辅助已经显示长程任务缺少稳定子目标表示，需要在不读取 WorldState、不绕过 Action schema 的前提下验证显式 Planning 变量。
改动：新增 `src/agent_arena/planning/`、`PlanningAgent`、`planning_v1`/`planning_executor_v1` prompts；扩展 DecisionProvider 的 Planner contract；接入 Runner、Trace、Benchmark、CLI `--agent planning`；新增 0006 spec 和 Planning 专项测试。
验证：96 项 pytest、Ruff、mypy 全部通过；Fake provider seed 0 完成 20 个 Executor Action、4 个子目标；Fake 5 seeds benchmark 全部成功并写出计划成本和生命周期指标。随后探测本机 Ollama，`verify-model` 未通过，因此没有伪造真实模型结果。
下一步：使用真实本地模型在固定 5 seeds 下运行 React、Memory、Planning 和 `planner_assisted` 对照。Fake 成功不代表 Planning 自主能力，Reflection 和 Streamlit 继续后置。
关联提交：`07f7457`。

## 2026-08-19 研究状态文档同步

事件：同步日常研究摘要、scope 和当前问题记录，使其反映 Release 2 已完成以及纯模型自主通关基线已完成但未通过的事实。

原因：`研究总纲.md` 仍描述项目尚未创建源代码，scope 和问题记录的下一步也仍写为重新建立已完成的真实 Ollama 对照，容易使新对话从过期阶段开始工作。

改动：将当前阶段改为已完成 Foundation 至 Release 2；记录 `qwen2.5:7b` 下 ReactAgent 与 MemoryAgent 各 5 局、均未成功的通用 prompt 基线；将下一步收敛为不含谜题答案的通用运行时上下文或受控短期历史实验，并保留 Streamlit、PlanningAgent 和 ReflectionAgent 的后置条件。

验证：`uv run ruff check .`、`uv run mypy src` 和 `uv run pytest` 通过；pytest 共 49 项通过。

下一步：为通用运行时上下文或受控短期历史建立独立技术设计和公平实验对照，不能将结果并入纯模型基线。

关联提交：待提交。

## 2026-08-19 Hiyo 自主逃生复验与候选选择实验

事件：使用 Hiyo `gpt-5.6-terra` 复验纯 React/Memory，并实现公开候选选择 Agent 作为新的受限辅助变量。

原因：此前 Ollama 实验显示上下文提示和里程碑不能改变循环，需要确认更强模型是否能自主完成阶段转换，并分离输出协议、状态转移和动作语义三个失败层。

改动：新增 `candidate_select` Agent、候选选择 JSON contract、公开候选枚举与重复/拒绝动作排除、trace provenance 标记和 Fake 回归；补充 A7 实验记录。

验证：Hiyo React A0 seed 0 在 3 个有效动作后因 5 次 `missing_argument` 终止；Hiyo planner-assisted seed 0 19 步成功；候选选择 seed 0 无阶段上下文恢复主电源但 30 步未通关，加入公开阶段上下文后读取授权码但将授权码用于错误目标，仍 30 步未通关。代码验证通过 68 项 pytest、Ruff、mypy 和 `git diff --check`。

结论：更强模型改善了局部探索和协议稳定性，但没有形成可执行的长程状态转移。自主失败首要原因不是模型规模，而是缺少阶段目标到动作语义的桥接；`planner_assisted` 成功只能作为辅助上界。

下一步：先独立修复/测量 Hiyo 的结构化输出，再实验带目标类型约束的公开语义 guard，并固定 5 个 seed 运行 A7 组合变量。

关联提交：待提交。

## 2026-08-19 Hiyo Responses provider 与自主通关复验

事件：接入 Hiyo OpenAI-compatible relay 的原生 Responses API，并复验 `gpt-5.6-terra` 的辅助和纯自主逃生表现。

原因：CCSwitch 配置声明该中转站使用 `wire_api = responses`；此前 Chat Completions 兼容调用虽然可连接，但纯 Agent 在错误工具反馈后频繁输出非法 Action，不能排除协议适配差异。

改动：新增显式 `openai` provider，使用 `/v1/responses`、结构化 JSON 输出和 `store=false`；更新本机 `.env`、远程验证脚本及配置文档。保留 Fake 为仓库默认，避免无密钥 CI 误发真实请求。

验证：`gpt-5.6-terra` 模型验证通过；`planner_assisted` seed 0/1/2 共 3 局均在 19 步成功逃生、0 次非法输出；ReactAgent 和 MemoryAgent 的通用 `--autonomous` seed 0 均在第 2 步后达到 `invalid_action_limit`。Ruff、mypy 和 52 项 pytest 通过。

结论：该模型适合当前公开规划辅助演示，但尚不能作为纯自主通关模型。后续 benchmark 必须分开记录辅助与自主结果。

关联提交：待提交。

## 2026-08-19 自主失败变量拆解与环境恢复修复

事件：执行环境恢复、推理强度、公开动作候选和输出格式分类四项受控实验，定位自主逃生失败原因。

原因：此前自主基线在第一次错误工具后因终端永久从 Observation 消失而进入矛盾状态，且 trace 无法区分非法 Action 的具体结构原因。

改动：错误终端动作不再修改可见性；新增 `missing_argument` 等脱敏非法输出类别、`reasoning_effort`、`guarded` 公开动作候选开关和 Responses JSON Schema 可选模式。由于 Hiyo relay 对 JSON Schema 返回 400，默认保留 `json_object`，格式修正请求会收到安全的缺参类别。

验证：环境修复后纯自主 React 达到 30 步但仍循环；`reasoning=high` 达到 10 步后仍循环；`guarded` 能到储藏室并检查密封箱但在拾取前因缺参终止。Ruff、mypy 和 57 项 pytest 通过。

结论：当前主因是模型在公开拒绝反馈后的任务分解和状态更新不足，结构化输出约束不足是次要但可测因素；增加推理预算没有显示改善。下一步应优先做可公开验证的阶段/候选动作实验，并保持与纯自主结果分开。

关联提交：待提交。

## 2026-08-19 A1/A2 公开上下文实验

事件：将自主逃生失败分析固化为可复现实验设计，并实现有限公开历史（A1）和结构化里程碑记忆（A2）。

原因：需要区分上下文不足、状态表示不足与规划能力不足，避免继续堆叠 Spaceship 专用 prompt。

改动：新增实验记录 `docs/autonomous-escape-experiment-plan.md`；DecisionRequest 支持最近公开轨迹；Runner 支持窗口化历史并将开关写入 trace provenance；MemoryState 增加公开可推导的物品发现、面板、电源和授权码里程碑；CLI 增加 `--recent-history` 与 `--structured-milestones`。

验证：60 项 pytest、Ruff、mypy 全部通过。Ollama `qwen2.5:7b` 固定 seed 0 至 4、30 步实验中，A1 为 0/5，平均 9 次环境拒绝；A2 为 0/5，平均 5 次环境拒绝。A1 能到达反应堆但未稳定拾取工具，A2 在储藏室重复检查。

结论：有限历史改善了早期导航但不足以完成任务；单纯增加结构化字段没有改善行动选择。下一步优先实现公开动作约束和卡死恢复，并继续独立记录实验变量。

关联提交：待提交。

## 2026-08-19 A3/A4 公开约束与卡死恢复实验

事件：实现并复验公开语义动作校验（A3）和独立卡死恢复提醒（A4）。

原因：A1/A2 未改变成功率，需要区分动作参数非法与参数合法但无进展两类失败。

改动：Runner 新增 `--semantic-guard` 和 `--stuck-recovery`，trace provenance 记录两项开关；guard 只检查公开出口、可见目标和背包约束，不执行被拒绝 Action；新增独立决策预算防止 guard 循环无限请求。

验证：63 项 pytest、Ruff、mypy 通过。A3 seed 0 探针 30 步全部为环境拒绝，0 次语义 guard 拒绝；A4 seed 0 至 4 为 0/5，全部进入储藏室后重复检查密封箱。

结论：A3 不能处理公开参数合法但阶段无进展的循环；A4 能打破控制室初始循环并改善探索，但未完成工具拾取。下一步需要阶段状态与候选动作集合，或进入真正 PlanningAgent 实验。

关联提交：待提交。

## 2026-08-19 A5 公开具体候选动作实验

事件：新增 A5 `--candidate-actions`，将当前 Observation 可构造的具体 Action 参数列给模型。

原因：A3 只能拒绝公开非法动作，需要独立测量具体候选是否能减少缺参和不可见目标输出。

改动：Runner 根据公开出口、可见对象、背包和公开终端授权码生成候选列表；不提供路线、阶段或隐藏前置条件；trace provenance 增加候选开关。

验证：65 项 pytest、Ruff、mypy 通过。Ollama `qwen2.5:7b` seed 0/1 探针均 30 步到达 `step_limit`，0 次非法输出，仍在控制终端循环；因单局耗时较长，剩余 seed 未扩展。

结论：具体候选动作不能改变参数合法但阶段无进展的循环。下一步应进入公开阶段状态/候选集合实验或 PlanningAgent，而不是继续扩大动作格式提示。

关联提交：待提交。

## 2026-08-19 调整自主通关优先级并暂缓 14B

事件：确认 ReactAgent 和 MemoryAgent 的代码实现、Fake provider 路线和公平对照测试已经完成，但真实 Ollama 的纯模型自主通关仍未完成。用户使用 Mac M5 Air，`qwen2.5:14b` 暂不继续测试。

原因：`planner_assisted` 的成功依赖确定性公开阶段和下一动作建议，不能证明模型在没有谜题攻略式提示时具备自主规划能力。继续堆 Spaceship 专用提示词会把实验变成人工攻略执行，削弱研究结论。

改动：将“不依赖谜题攻略式提示的纯 ReactAgent 与 MemoryAgent 自主通关验收”提升为当前首要未完成任务，要求使用通用 prompt、相同 seed 和预算，并独立保存成功与失败 trace。将 14B 标记为受 M5 Air 资源限制而暂缓，不纳入当前实验矩阵。

验证：复核 `docs/scope/scope.md`、`docs/current-issues.md`、`docs/model-passage-options.md`、ReactAgent 与 MemoryAgent spec 及历史记录，确认两者已完成实现级验证，但真实自主通关验收没有完成。

下一步：先完成通用 prompt 下的 ReactAgent 与 MemoryAgent 真实 Ollama 对照，再根据 trace 决定是否需要运行时循环检测或其他独立实验变量；之后才进入 Streamlit。

关联提交：待提交。

## 2026-08-19 通用 Prompt 纯模型自主基线未通过

事件：完成 ReactAgent 与 MemoryAgent 的纯模型自主对照，各运行 5 局真实 Ollama 实验。

原因：验证模型能否不依赖 Spaceship 专用攻略提示、规划辅助或运行时循环提醒，仅根据公开 Observation 和结构化 Memory 完成任务。

改动：新增 `react_v12_autonomous` 通用 prompt。ReactAgent 和 MemoryAgent 默认使用该 prompt。新增 CLI `--autonomous`，关闭 Runner 的循环提醒，并在 trace provenance 中记录 `runtime_feedback_enabled=false`。`planner_assisted` 继续使用独立的 `react_v11` 和辅助路径。

验证：`qwen2.5:7b`、seed 0 至 4、每局 30 步。ReactAgent 0/5 成功，平均 30 步，每局 2 次环境拒绝，非法输出 0。MemoryAgent 0/5 成功，平均 30 步，每局 15 次环境拒绝，非法输出 0。Ruff、mypy 和 49 项 pytest 全部通过。

结论：纯模型自主通关仍未完成，但失败基线已经真实且可重复。ReactAgent 在初始观察后连续重复 `look`，MemoryAgent 在控制室和走廊之间反复读取不可见终端。问题集中在公开 Observation 的行动选择和失败后的状态更新，不是连接或 JSON 格式问题。

下一步：先设计不含谜题答案的通用运行时上下文或受控短期历史实验，并将其与当前基线独立比较；不得直接恢复 Spaceship 专用路线提示。

关联提交：待提交。

## 2026-08-17 架构决策确认

事件：项目采用 Python 3.13、uv、本地分层单体、CLI 和本地 JSON 文件作为第一版基础架构。

原因：先建立一个可重复的本地 Agent 研究闭环，避免过早引入服务、数据库和复杂编排。

改动：接受 `docs/specs/0001-project-architecture/`，明确 Environment、Agent、LLM、Evaluation 和 UI 的边界。

验证：架构检查清单已建立，真实模型调用被明确为手动验证，不进入默认 CI。

下一步：完成 Foundation scaffold。

关联提交：`c630729`

## 2026-08-17 Foundation scaffold 完成

事件：项目已经可以安装、运行 CLI、生成 Fake episode，并执行自动质量检查。

原因：为确定性的 Spaceship Escape 环境提供稳定的代码和测试基础。

改动：新增 `pyproject.toml`、`uv.lock`、`src/agent_arena`、RuntimeSettings、Fake provider、CLI、测试和 GitHub Actions。

验证：`uv lock --check`、Ruff、mypy 和 10 项 pytest 全部通过。`uv run agent-arena run` 成功生成 JSON episode，百炼模型验证也成功返回确认文本。

下一步：运行 `/architect Spaceship Escape 环境`，定义房间、工具、物品、非法动作和胜利条件。

关联提交：`fe42515`

## 记录规则建立

事件：增加工程事件记录文件和对应 workflow 规则。

原因：scope 只保留当前状态，spec 只保留技术决策，Git 只保留代码差异，三者无法单独表达重要事件的原因、验证和下一步。

改动：新增本文件，并在根 `AGENTS.md` 中定义记录范围、模板和提交前流程。

验证：`git diff --check` 已通过，工作区只包含预期的 `AGENTS.md` 和本文件改动。

下一步：后续每个重要阶段完成时追加一条简短记录。

## 2026-08-17 Spaceship Escape 环境设计确认

事件：确认第一个确定性世界的地图、公开工具、信息边界、谜题状态和逃生条件。

原因：环境规则必须先稳定，后续 Agent Loop、trace 和 benchmark 才有可信对照。

改动：新增 `docs/specs/0002-spaceship-escape/`，并将 scope 中的 Spaceship Escape 环境改为设计完成和实现中。

验证：完成设计访谈与独立只读交叉检查。九项契约空白已补齐，`git diff --check` 通过。

下一步：运行 `/develop Spaceship Escape 环境`，实现配置、Environment 和规则测试。

关联提交：待提交。

## 2026-08-18 本地模型规划辅助通关验证

事件：在保留纯模型失败基线的前提下，完成 `qwen2.5:7b` 的 `planner_assisted` 公开规划辅助通关。

原因：纯 ReactAgent 和 MemoryAgent 在收集工具、恢复电源后会重复公开动作；同时旧 prompt 错误要求所有 `use.item` 必须在背包，和控制终端返回授权码后使用授权码的环境规则冲突。用户目标是让 agent 实际完成逃生，因此需要验证公开辅助是否能稳定解决循环，同时不能把辅助结果伪装成纯模型结果。

改动：新增 `react_v11` prompt，区分维修物品与公开读取的授权码；新增独立的 `PlannerAssistedAgent` 和 CLI `--agent planner_assisted`。规划器只使用公开 Observation、ToolResult 和结构化 Memory 生成阶段/下一动作建议，模型仍选择并返回每个 Action；授权码仅在收到公开 `CODE_READ` 结果后提取。储物室规划优先拾取已出现物品，阶段建议放入最新公开请求，并在 trace 中用独立 agent/prompt 版本标记。

验证：Ruff、mypy 和 48 项 pytest 通过。`qwen2.5:7b`、`planner_assisted_v2`、seed 0/1/2 的 Ollama benchmark 为 3/3 成功，平均 19 步、0 次非法输出、0 次环境拒绝；结果文件为 `/tmp/agent-arena-planner-v11-benchmark/benchmark_20260818T080152Z_planner_assisted_3-seeds_3-episodes_defcc08a.json`。纯模型 MemoryAgent 的失败结果仍保持为独立基线。

下一步：规划辅助结果只用于稳定通关和演示，继续与纯 React/Memory 对照分开统计；若研究需要纯模型成功率，应单独研究更强模型或公开循环保护，不得把规划建议视为模型自主规划。

关联提交：待提交。

## 2026-08-18 用户本机复验与通关记录补充

事件：用户使用 `OLLAMA_MODEL=qwen2.5:7b` 和 `--agent planner_assisted` 在本机连续运行两次，均以 19 步成功逃生。

原因：确认前一轮实验不是临时环境或 Fake provider 结果，并为后续复现明确区分真实模型执行与规划器辅助。

改动：将完整问题、排查步骤、最终路线、复现命令、已完成能力和待办写入 `docs/model-passage-options.md`。确认两份 trace 的模型为 `qwen2.5:7b`、Agent 为 `planner_assisted_v2`，每个执行 Action 都经过模型响应和环境校验；没有程序代替模型执行动作。

验证：两份用户 trace 均为 `success`、19 个 `action_validated`、0 次非法输出、0 次环境拒绝。复核发现 `PublicLoopDetector` 仍可能因状态键缺少 `available_exits` 和 `last_action_result` 而误报合法回程，该问题列入后续任务，不影响本次通关结果。

下一步：先修复循环检测状态键并增加回归测试，再独立实现 `guarded` 模式；继续将纯模型、规则保护和规划辅助结果分开统计。

关联提交：待提交。

## 2026-08-18 本地模型策略验收

事件：完成 Ollama 原生 `/api/chat`、关闭思考、JSON Schema、逐步终端回显和本地模型对照验收。

原因：用户明确只使用本地模型，并希望关闭思考以降低每步延迟；需要区分接口故障与模型策略能力不足。

改动：将 Ollama 默认模型更新为 `qwen2.5:7b`；新增原生请求回归测试；调整 Memory 消息顺序；提示词升级到 `react_v8`，明确公开环境中的关键前置条件和重复动作限制。

验证：`qwen3:8b` 与 `qwen2.5:7b` 的 `verify-model --provider ollama` 均通过，40 项 pytest、Ruff、mypy 通过。`qwen3:8b` 和 `qwen2.5:7b` 均能输出合法动作，但在关闭思考时单局 30 步都未完成逃生；7B 在 `react_v8` 下能走到存储室并发现物品，随后仍会重复移动。当时 14B 下载因长时间网络停滞中止；后续已完成安装，结果见 2026-08-18 的复验记录。

下一步：当前验收结论为本地链路和可观测性通过，自动逃生策略未通过；后续应优先改进 Agent Loop 的重复动作约束或采用已验证的更强本地模型，而不是把失败局写成成功。

关联提交：待提交。

## 2026-08-18 轻量化链路与 14B 复验

事件：完成紧凑提示词、公开循环检测、运行时提醒、MemoryAgent 请求接入和 Spaceship Escape 无效目标收敛；随后复验已安装的 `qwen2.5:14b`。

原因：用户希望降低 16G Mac 的运行压力，同时确认 14B 是否能解决 7B 的长程循环问题。

改动：新增 `react_v9`，默认 Ollama 输出上限调整为 256 token；`DecisionRequest`、Runner、两种 provider 和 trace 增加公开运行时提醒；Environment 在终端误用、目标完成和授权码前置条件不满足时减少无效观察目标；新增循环检测及回归测试。

验证：`uv run ruff check .`、`uv run mypy src` 和 45 项 pytest 全部通过；`qwen2.5:14b` 的 `verify-model` 通过。固定 seed=0、MemoryAgent、30 步真实运行执行 30 步、0 次非法模型输出，但在恢复主电源后重复读取诊断终端，结果为 `step_limit`，未完成逃生。

下一步：将当前结果作为诚实的失败基线；若产品必须保证通关，应另行设计确定性任务阶段/Action Guard，不能继续只堆提示词规则。默认开发模型保持 `qwen2.5:7b`，14B 仅作对照。

关联提交：待提交。

## 2026-08-17 Spaceship Escape 环境完成

事件：完成第一个可手动通关的确定性 Spaceship Escape 环境。

原因：为后续 Agent Loop、Episode Trace 和 benchmark 建立可重复的环境基线。

改动：新增严格 Action 与 Observation 契约、六房间 JSON 定义、环境状态转换和规则测试。

验证：`uv run ruff check .`、`uv run mypy src` 和 25 项 pytest 通过，公开工具路径在 20 步内完成逃生。

下一步：设计 ReactAgent 与 Agent Loop。

关联提交：待提交。

## 2026-08-17 Release 1 Agent Loop 完成

事件：Release 1 的 ReactAgent、受限 Episode Runner、JSON Episode Trace 和 CLI 运行闭环完成。

原因：在进入 Memory 与 benchmark 前，需要一个可重复、可复盘且不会将不可信模型原文写入 trace 的基线 Agent。

改动：新增 `0003-react-agent-loop` spec、`ReactAgent`、百炼结构化决策适配、20 步 Fake 通关路径、Runner 状态机、脱敏原子 trace 写入和端到端测试；CLI `run` 不再生成 scaffold episode。

验证：`uv run ruff check .`、`uv run mypy src` 和 30 项 pytest 通过；`uv run agent-arena run --output-dir <temporary-directory>` 生成 `success` trace，含 20 个已执行动作和 0 个非法输出。

下一步：设计规则驱动的 MemoryAgent，并在固定世界、模型、提示词与步数预算下建立 Release 2 对照。

关联提交：待提交。

## 2026-08-17 百炼 Action 格式修复

事件：真实百炼运行曾连续输出带 `args` 包装的动作，现已通过 `react_v3` prompt 改为直接在 `action` 内提供工具参数。

原因：严格 Action schema 正确拒绝了非约定格式，但旧 prompt 只给出无参数工具示例，模型稳定选择了通用包装格式。

改动：升级 prompt 版本并列出六种工具的完整扁平 JSON 示例，明确禁止 `args`、`arguments` 和 `parameters` 包装字段；增加 prompt 约束回归测试。

验证：Ruff、mypy 和 31 项 pytest 通过。真实百炼运行从 3 次非法输出、0 个执行动作变为 0 次非法输出、30 个有效动作；该局因反复探索无电控制终端达到步数上限，说明格式问题已修复，而基线策略仍是后续 MemoryAgent 的研究对象。

下一步：设计 MemoryAgent，用结构化记忆降低重复观察和重复失败动作。

关联提交：待提交。

## 2026-08-17 Release 2 MemoryAgent 完成

事件：完成规则驱动的结构化 MemoryAgent，并建立与 ReactAgent 的可复现单局对照。

原因：在 benchmark 前先固定唯一实验变量，避免完整历史、隐藏状态或第二次模型调用影响结果。

改动：增加公开记忆 reducer、脱敏、失败动作与问题映射、Agent 生命周期、结构化 provider 请求与响应、token 用量、trace 实验来源和 CLI `--agent` 选择。

验证：Ruff、mypy 和 33 项 pytest 全部通过。ReactAgent 与 MemoryAgent 的 Fake CLI 均在 20 步成功逃生，Memory trace 包含版本化来源字段。

下一步：实现 benchmark 命令，使用持久化 trace 输出 ReactAgent 和 MemoryAgent 的 JSON、CSV 指标对照。

关联提交：待提交。

## 2026-08-17 Release 2 Benchmark 与指标完成

事件：完成多局 benchmark 命令，以及基于持久化 trace 的 JSON、CSV 指标输出。

原因：MemoryAgent 需要与 ReactAgent 在相同世界、seed 和预算下进行可复现对照，才能解释后续实验结果。

改动：新增 benchmark 行和聚合计算、原子 JSON/CSV 写入、trace 重读校验；CLI 支持单 Agent 或默认双 Agent 对照。

验证：Ruff、mypy 和 36 项 pytest 通过。`agent-arena benchmark --episodes 1` 使用 Fake provider 生成两份 trace，CSV 按 React、Memory 顺序输出，JSON 聚合成功率为 1.0。

下一步：在 benchmark 结果稳定后设计 Streamlit 实验界面。

关联提交：待提交。

## 2026-08-17 Benchmark 反馈与文件命名改进

事件：为 episode trace 和 benchmark 结果加入可读文件名，并让 benchmark 实时显示运行进度。

原因：原始 UUID 文件名难以按实验辨认；真实百炼 benchmark 默认运行 React 与 Memory 两组，原 CLI 在所有局完成前没有任何输出，容易被误判为卡住。

改动：输出名称包含 UTC 时间、Agent、seed 或局数和短 ID；真实模型会在每次决策请求前输出当前步数，benchmark 还会输出开始、每局开始和每局结束状态。

验证：Fake provider 端到端运行确认新名称和进度输出。`uv run ruff check .`、`uv run mypy src` 和 37 项 pytest 全部通过。

下一步：以小局数真实 benchmark 观察新进度信息和实际响应时长，再在结果稳定后设计 Streamlit 实验界面。

关联提交：待提交。

## 2026-08-17 本地 Ollama 与逐步复盘支持

事件：将真实实验工作流扩展为本地 Ollama `qwen3:4b`，并在终端逐步显示简短理由、动作、环境结果和对应 trace 路径。

原因：百炼的 3 seed React、Memory 对照均达到步数上限。Trace 显示 React 重复读取无电终端，Memory 虽减少拒绝动作但在维修室和反应堆室之间循环；原 benchmark 终端未展示已记录的步骤，难以直接诊断。

改动：新增 `ollama` provider、无密钥本地验证、独立 Ollama 配置、`react_v4` 探索规则和逐步终端回显。完整步骤继续存入 `runs/`，`results/` 保持指标职责。

验证：Ollama 服务可访问但模型列表为空，因此真实本地模型验证明确失败，未伪造通过结果。Ruff、mypy 和 39 项 pytest 全部通过；Fake benchmark 验证逐步输出和 trace 路径。

下一步：在本机下载 `qwen3:4b` 后运行 `verify-model --provider ollama`，再以单局和同 seed 对照检验 `react_v4` 的真实模型表现。

关联提交：待提交。

## 2026-08-19 A6 公开阶段状态实验

事件：新增 `--phase-context`，将公开背包和公开 ToolResult 压缩为阶段与未完成条件，不提供路径或下一动作。

原因：A5 证明具体参数候选不能改变策略循环，需要测量阶段摘要是否能改善长程任务分解。

改动：新增公开 `PublicPhaseTracker`，只记录面板打开、主电源恢复、授权码读取等公开成功结果；trace provenance 记录阶段上下文开关。

验证：66 项 pytest、Ruff、mypy 通过。Ollama `qwen2.5:7b` seed 0 探针 30 步均在控制室终端循环，未发生阶段推进。

结论：阶段标签不提供从阶段到动作的桥接，不能解决自主逃生。后续停止继续堆自然语言提示变量，转向真正 PlanningAgent 或明确标记的辅助候选策略。

关联提交：待提交。

## 2026-09-05 当前问题盘点与实验契约登记

事件：完成当前研究、配置、trace 和 benchmark 契约的只读盘点，并将未完成项写回持续文档。

原因：纯模型自主通关仍未验收，需明确区分已确认的实现缺口、尚未验证的行为和辅助模式的研究边界，避免后续实验误读配置或混合结论。

改动：更新 `docs/current-issues.md`、`docs/scope/scope.md` 和 `docs/autonomous-escape-experiment-plan.md`，登记固定 world 加载、循环检测回归、缺失指标、planner feedback 可复盘、生命周期测试和远程 provider 凭据阻塞。

验证：只读确认传入任意 `world`/`world_version` 时环境仍加载 `spaceship_escape_v1 / v2-zh`；`uv run pytest` 为 68 passed，Ruff 和 mypy 通过。

下一步：先设计并实现 world 加载契约、循环检测修复及指标补齐，再验证 guarded 和 planner 生命周期；纯模型与辅助模式继续独立统计。

关联提交：`29cb000`。
