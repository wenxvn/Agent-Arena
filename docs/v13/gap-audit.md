# V13 差距审计（P0 / P1 / P2 逐项）

对照对象：`研究提纲/V13Agent-Arena_V13_第二阶段深化执行提纲.md`
状态定义：`DONE` / `PARTIAL` / `WAITING_USER_APPROVAL` / `BLOCKED_EXTERNAL` / `NOT_DONE`

- 生成日期：2026-10-26
- 起始 HEAD：`32e27826eab33093d2d5d640d08f47bbd4974df3`
- 真实付费请求：**0**

## 0. 一句话结论

P0 6/6 工程完成、P1 6/6 工程完成（1 项等待授权）、P2 7/7 工程完成
（2 项外部条件不具备）。**没有任何一项被静默跳过**。

## 1. P0（6/6）

| ID | 任务 | 状态 | 证据 | 说明 |
|---|---|---|---|---|
| P0-1 | 实验稳定性验证 | **DONE** | `lab/v13/stability.py`、`docs/v13/repeat_variability.*` | 复算 V12 的 22.22%/25.00%；重复放进同一实验（`create_replicates`） |
| P0-2 | Memory 策略优化 | **DONE** | `policies/memory_v2.py`、`docs/v13/memory-study.md` | 路线只累积被接受 move；`env_write`/`context_only` 显式区分；三类瓶颈 |
| P0-3 | Planning 策略优化 | **DONE** | `policies/planning_v2.py`、`docs/v13/planning-study.md` | 三模式 + TTL + 预算感知 + 逐请求成本 |
| P0-4 | Agent 消融实验 | **DONE** | `lab/v13/ablation.py`、`run_v12_matrix.py --ablation` | 7 模板全单开关；两独立父实验；版本比较被拒绝 |
| P0-5 | 实验公平性审计 | **DONE** | `lab/v13/comparability.py`、`contracts.SamplingProvenance` | 画像/单变量/硬拒绝/采样登记/协议指纹 |
| P0-6 | 核心结果重新验证 | **DONE** | `docs/v13/core-evidence.md` | MAP-16/18/22 三份证据包（含反例与截尾） |

## 2. P1（6/6）

| ID | 任务 | 状态 | 证据 | 说明 |
|---|---|---|---|---|
| P1-1 | Reflection 策略优化 | **DONE（机制）/ `WAITING_USER_APPROVAL`（真实收益）** | `policies/reflection_v2.py`、`docs/v13/reflection-study.md` | SIMULATED 真触发 `triggered=2`；零触发报 `NO_TREATMENT_EXPOSURE` |
| P1-2 | MAP-30 深度探索 | **DONE** | `lab/v13/validity.py::map30_ladder`、`docs/v13/map30-budget-ladder.md` | 3 档阶梯 + 5 类失败分型 + 候选档（需批准） |
| P1-3 | 失败诊断增强 | **DONE** | `lab/v13/taxonomy.py`、`docs/v13/diagnosis-taxonomy.md` | 7 层 + 8 个 fixture + 证据锚 |
| P1-4 | 能力画像完善 | **DONE** | `lab/v13/capability.py`、`docs/v13/capability-profile.md` | 6 维机制画像；缺失不补 0；`agent_reviewed` |
| P1-5 | 可视化优化 | **PARTIAL** | `ui/lab.py`（5 页） | 轨迹 Diff/六图视图沿用 V12；新增稳定性/效度页与逐 seed 分块；**未做新的图形化组件** |
| P1-6 | 六图有效性审计 | **DONE** | `docs/v13/map-validity.md` | 08/26 `CEILING`、16/18/22 `SUITABLE`、30 `CENSORED` |

## 3. P2（7/7）

| ID | 任务 | 状态 | 证据 | 说明 |
|---|---|---|---|---|
| P2-1 | CI 自动化强化 | **PARTIAL** | `.github/workflows/ci.yml` | 已加 `verify_v13` 步骤；E2E 仍 `continue-on-error`（无 CI 实跑证据） |
| P2-2 | 性能压力测试 | **DONE** | `lab/v13/perf.py`、`docs/v13/performance-report.md` | 1k/5k 实测；懒加载 + 增量索引 |
| P2-3 | Web UI 优化 | **DONE** | `ui/lab.py`、`web/index.py` | 预检/授权状态/重复提示/服务端分页 |
| P2-4 | 自动实验报告 | **DONE** | `lab/v13/report.py` | 零 LLM；四级结论 + 锚点；负面结果保留 |
| P2-5 | 第三方 SDK 完善 | **DONE** | `lab/v13/sdkcheck.py`、`docs/v13/sdk-guide.md` | 8 项自检；异常隔离；旧签名兼容 |
| P2-6 | 数据与费用审计 | **DONE（本地）/ `BLOCKED_EXTERNAL`（后台账单）** | `lab/v13/ledger.py`、`docs/v13/data-and-cost-audit.md` | 159/159 配对、0 孤儿、0 重复；账单接口就绪 |
| P2-7 | 文档与交付整理 | **DONE** | `docs/v13/` 全套 | 见 `release-checklist.md` |

## 4. 未完成 / 部分完成（逐条解释）

| # | 项 | 状态 | 原因 | 能否补 |
|---|---|---|---|---|
| 1 | CI 浏览器 E2E 作为**阻断门禁** | `PARTIAL` | 本轮未推送远端，无法取得"CI 连续可靠通过"证据；按提纲要求，未验证前不得改门禁 | 是：推送后连续 3 次成功再改 `continue-on-error: false` |
| 2 | Provider **后台账单**对账 | `BLOCKED_EXTERNAL` | 需要用户从控制台导出脱敏 CSV | 是：`audit_v13_ledger.py --bill` 已就绪 |
| 3 | 真实模型的 Memory/Planning/Reflection 效果 | `WAITING_USER_APPROVAL` | 提纲明确禁止擅自发起付费请求；V12 授权已结束 | 是：`live-budget-proposal.md` 三个方案 |
| 4 | P1-5 新增图形化组件 | `PARTIAL` | 时间用于数据正确性（分页、稳定性、效度）优先；现有表格视图已能回答研究问题 | 是：可加六图 SVG/Diff 高亮 |
| 5 | 真机读屏软件 | `NOT_VERIFIED` | 无读屏环境 | 需人工 |
| 6 | macOS / Ollama 实机 | 按用户指示暂缓 | — | 不计 V13 缺项 |

## 5. 与提纲"可量化验收总表"的对照

| 等级 | 提纲要求 | V13 实际 |
|---|---|---|
| P0 | 旧结果读取/复算；重复身份不冲突；公平性 guard；Memory/Planning 单因子离线验证；MAP-16/18/22 证据包；预注册 LIVE 方案 | **全部满足**；状态 `ENGINEERING_READY, LIVE_PENDING` |
| P1 | Reflection 模拟 trigger ≥1 可复现；MAP-30 多级截尾拆分；六图效度标签；诊断证据锚；画像无错误归一化；交互回放正常 | **全部满足**（P1-5 为 `PARTIAL`：表格视图可用，未加新图形组件） |
| P2 | E2E 有 CI 实际证据；1k/5k 压测；UI 完整流程；模板报告可复算；SDK 异常隔离；本地账本检查；完整文档 | 除 **CI 实际证据**（`NOT_VERIFIED`）与**后台账单**（`BLOCKED_EXTERNAL`）外全部满足 |

## 6. 提纲 §8「遇到不可执行的项目」逐条对照

| 阻塞 | 提纲要求 | V13 实际做法 |
|---|---|---|
| 未给 V13 费用授权 | 完成代码/预检/模拟/历史再分析，给细分费用申请 | ✅ 全部离线完成 + `live-budget-proposal.md` 三档 |
| 没有 Provider 后台账单 | 完成本地审计 + 离线导入模板 + 标待对账 | ✅ `NO_EXTERNAL_BILL_PROVIDED` + `write_bill_template` |
| 模型不支持固定采样参数 | 记 `UNSUPPORTED`，增加重复并报告波动 | ✅ `SamplingProvenance.support` 三态；永不写 deterministic |
| Seed 白名单不足 | 用登记 seed 做重复，声明缺 holdout | ✅ 未扩 seed；E5 标"无 holdout 则探索性" |
| 浏览器 E2E 的 CI 不稳定 | 修复依赖/等待；保留显式 gap | ✅ 保留 `continue-on-error` 并在本文件记录 |
| 某优化无涨点甚至更差 | 如实保存负面结果 | ✅ 报告第 4 节；MAP-18 planning 1/11 保留 |
| 冻结层与优化冲突 | 用 V13 投影/策略层修复，不改旧规则 | ✅ 冻结 9/9 unchanged；V10 未改一行 |

## 7. 不构成"完成"的项（防自欺）

- 新增代码量、通过单测数**不是**能力证据；
- SIMULATED 演示**不是**模型能力；
- 历史 22–25% 翻转率说明"1 次/条件不足以下架构结论"；
- V13 的状态是 `LAB_1_1_ENGINEERING_READY`，**不是** `LIVE_VALIDATED`。
