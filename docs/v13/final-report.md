# V13 最终报告：Agent Arena Lab 1.1

- **结论**：`LAB_1_1_ENGINEERING_READY`（P0 6/6、P1 6/6、P2 7/7 工程交付；
  真实模型部分 `WAITING_USER_APPROVAL`）
- **真实付费实验**：**本轮 0 局、CNY 0**（未获 V13 授权；V12 的 ¥6 已结束，余额不挪用）
- **执行日期**：2026-10-26
- **起始 HEAD**：`32e27826eab33093d2d5d640d08f47bbd4974df3`
- **平台**：Windows 11 实测；Ubuntu 由 CI 覆盖（本轮未触发远端）；macOS / Ollama 暂缓
- **未改动**：V8/V9/V10 冻结规则、账本、历史 trace；V11 单局语义；V12 历史实验

---

## WHAT：交付了什么（相对 V12 的**真实增量**）

V12 回答了"同一配置换架构，行为/成功率/成本/失败原因有什么差异"。
V13 回答的是下一个问题：**这些差异到底可不可信、机制有没有被激活、能不能在预算内复现。**

| 增量 | 一句话 | 位置 |
|---|---|---|
| 重复身份 | 同一条件可在一个实验内做 N 次独立重复，且不被幂等去重 | `MatrixCell.replicate_index`、`create_replicates` |
| 可比性协议 | 14 维画像 + 单变量检查 + 硬拒绝；版本比较与消融被显式区分 | `lab/v13/comparability.py` |
| 采样登记 | temperature/top_p/seed 的支持状态三态，永不宣称 deterministic | `SamplingProvenance` |
| 稳定性分析 | 翻转率 + Wilson 描述区间 + 按 seed 分块 + 跨版本排除 | `lab/v13/stability.py` |
| 三个 v2 策略 | `memory.v2`（路线记忆）、`planning.v2`（节流+预算感知）、`reflection.v2`（可验证激活） | `lab/policies/*_v2.py` |
| 单因子消融 | 7 个模板，全部"只差一个开关"，on/off 两个独立父实验 | `lab/v13/ablation.py`、`--ablation` |
| 七层归因 | 接口/测量/预算/机制/策略/Provider/未知，接口问题不算能力 | `lab/v13/taxonomy.py` |
| 六维画像 | 按机制维度组织，不对 326 个异质指标平均；缺失不补 0 | `lab/v13/capability.py` |
| 构念效度 | 六图 `SUITABLE`/`CEILING`/`CENSORED` 复合标签 + 选图建议 | `lab/v13/validity.py` |
| 模板报告 | 零 LLM；四级结论 + 逐数字锚点；负面结果保留 | `lab/v13/report.py` |
| 账本审计 | 只读一致性检查 + 可选脱敏账单对账（无账单明确标注） | `lab/v13/ledger.py` |
| 服务端分页 | 懒加载首页 + 增量刷新，5 000 条历史不再全量解析 | `web/index.py` |
| SDK 自检 | 8 项接入自检 + 异常隔离 + 旧签名兼容 | `lab/v13/sdkcheck.py` |
| 两个新页面 | 稳定性与效度、报告与审计 | `ui/lab.py`（共 5 页） |

### 一条运行链路（V13 增量标粗）

```text
Lab 页面 / CLI / Python SDK
      ▼
ExperimentSpec（**replicates / sampling / protocol**）+ preflight（零请求）
      ▼
ExperimentService（矩阵含 **replicate_index** / 单 worker / 父子状态 / 预算）
      ▼
AgentRunnerV12 → AgentPolicy（basic / memory.v1 / planning.v1 / reflection.v1
                              **/ memory.v2 / planning.v2 / reflection.v2**）
      ▼
DecisionGateway（唯一模型出口 + 单一预算汇）
      ▼
V10 Environment（**未改一行**）
      ▼
result + provenance + agent_events
      ├──> **可比性判定** → 配对比较 / 五态指标
      ├──> **重复稳定性**（翻转率 / seed 分块）
      ├──> **分层归因** + 轨迹 Diff
      ├──> **六图构念效度** / **机制画像**
      └──> **V13 模板报告** + 账本审计
```

## WHY：为什么这样做

1. **先冻结口径，再改策略。** 如果先优化再补口径，就永远说不清"提升"是策略还是口径。
2. **重复不等于新 seed。** V12 已经量化翻转率 22–25%；V13 把这条写进统计单位，
   并让 UI/报告在数字旁边就提示，避免读者自行放大样本量。
3. **接口问题不能算能力。** MAP-22 的旧 0/3 就是接口假象；V13 用分层归因把这类
   失败永久隔离在能力分母之外。
4. **只改一个开关才叫消融。** 多开关同时改只能叫"组合方案"；`single_switch_check`
   直接拒绝把多开关说成单因子。
5. **零触发 ≠ 无效。** DCR-V12-05 的教训：`NO_TREATMENT_EXPOSURE` 必须是独立状态。
6. **不重造 V12。** 子局仍走 V11 `RunService`；策略、网关、比较、诊断、可视化全部复用。

## HOW：关键实现选择

| 问题 | 选择 | 代价 |
|---|---|---|
| 如何在不破坏历史的前提下加重复编号 | `replicate_index=0` 时条件键与 V12 **逐字一致**，`>0` 追加 `|rep=<n>` | 聚合层必须显式按重复分组 |
| 如何兼容 V12 文件 | `schema_version` 不变，只增字段；旧文件按默认值读 | 读取器要能处理两种字段集 |
| 如何区分"版本比较"和"消融" | `classify_pair`：不同 `agent_id` → `VERSION_COMPARISON` | UI 必须显示对照类型 |
| 如何让路线记忆可审计 | `route_mode` 显式：`env_write`（占决策）vs `context_only`（0 动作） | 两种机制不能互相冒充 |
| 如何避免规划节流掩盖触发 | TTL 延迟写 `planner_deferred_ttl` 事件 | 事件变多 |
| 如何让历史列表不随规模变慢 | 懒加载首页 + mtime 增量刷新 + 30s 签名 TTL | 新增 run 需 `invalidate_index()` |
| 如何保证报告不说谎 | 零 LLM、四级结论、逐数字锚点 | 措辞机械 |

## RESULTS：本轮真实结果

### 1. 历史只读再分析（`HISTORICAL`）

| 指标 | V12 公布 | V13 复算 | 一致 |
|---|---|---|---|
| 2 次观测翻转率 | 22.2%（4/18） | **0.2222（4/18）** | ✅ |
| 3 次观测翻转率 | 25.0%（3/12） | **0.25（3/12，排除 6 组跨版本）** | ✅ |
| 唯一 3/3 条件 | `planning.v1 @ MAP-16 seed 1` | 同 | ✅ |
| 真实局数 / 请求 / 金额 | 159 / 5 641 / ¥5.43680012 | 同（账本 159/159 配对） | ✅ |
| MAP-30 扩展 1 到法庭 | 4/9 | 4/9 | ✅ |
| MAP-30 扩展 2 截尾 | 7/9 | 7/9 | ✅ |

### 2. 六图构念效度（`HISTORICAL`）

| 地图 | 标签 | 有效分母 | 成功 | 截尾 | 读法 |
|---|---|---:|---:|---:|---|
| MAP-08 | `CEILING` | 9 | 9 | 0 | 测不出差异，保留为回归案例 |
| MAP-16 | `SUITABLE` | 35 | 9 | 1 | planning 有梯度，代价 3.6× 请求 |
| MAP-18 | `SUITABLE` | 37 | 8 | 0 | memory 有梯度，方向与 MAP-16 相反 |
| MAP-22 | `SUITABLE` | 20 | 3 | 2 | 旧 0/3 是接口假象；route_log 才有真信号 |
| MAP-26 | `CEILING` | 9 | 9 | 0 | 同 MAP-08 |
| MAP-30 | `CENSORED` | 27 | 0 | 20 | 0 成功主要是"没测完" |

### 3. 机制验证（`SIMULATED`，零费用）

| 机制 | 证据 | 结论 |
|---|---|---|
| Memory 路线只累积被接受 move | 被拒/非法不计入，`loops`/`backtracks` 单独计数 | `SUPPORTED`（机制） |
| `env_write` 占 1 次决策、`context_only` 0 动作 | `write_attempts` / `render_count` 分离 | `SUPPORTED`（机制） |
| Planning `initial_only` 只请求 1 次 | `planner_requests == 1` | `SUPPORTED`（机制） |
| Planning TTL 延迟留证据 | `planner_deferred_ttl` 事件 | `SUPPORTED`（机制） |
| Reflection 真触发 | 探针 `triggered=2`、`TREATMENT_TRIGGERED` | `SUPPORTED`（机制） |
| Reflection 零触发 | `NO_TREATMENT_EXPOSURE` | `SUPPORTED`（口径） |
| 单因子消融模板 | 7/7 `single_switch_ok` | `SUPPORTED`（机制） |
| 重复不被幂等去重 | 3 次重复 → 3 个不同 run_id | `SUPPORTED`（机制） |

### 4. 工程指标

| 项 | 值 |
|---|---|
| pytest | **1639 passed**（V13 新增 114 项） |
| ruff | All checks passed |
| mypy | 323 文件 0 issues |
| V10 冻结 | 9/9 unchanged |
| V10 复算 | 1093/1093，0 不一致 |
| V10 独立复核 | 0 违规 / 回放确定 30/30 / seed 互异 30/30 |
| `verify_v11` | 7/7 |
| `verify_v12` | 15/15 |
| `verify_v13` | **18/18** |
| 1 000 条历史 | 懒加载首页 18 ms；已建索引翻页 0.1 ms；峰值 1.4 MiB |
| 5 000 条历史 | 懒加载首页 31 ms；已建索引翻页 0.4 ms；峰值 7.3 MiB |

## LIMITATIONS：能说什么、不能说什么

### 可以说

- V12 的公开数字**可复现**（翻转率、局数、请求、金额、MAP-30 阶梯）；
- 三个 v2 策略的**机制**在离线可复现（路线只记被接受 move、TTL 留痕、反思真触发）；
- 六图里 **MAP-16/18/22 有梯度**，MAP-08/26 是天花板，MAP-30 是截尾；
- 历史列表在 5 000 条规模下**分页与聚合都是亚毫秒级**；
- 本地账本**自洽**（159/159 配对、0 孤儿、0 重复结算）。

### 不能说

| 主张 | 为什么不能说 |
|---|---|
| "Memory 让成功率提升 X%" | 真实模型未跑；历史翻转率 22–25% |
| "Planning 是最优架构" | MAP-18 上它是 1/11 |
| "Reflection 实测有效" | 只有 SIMULATED 探针，无真实 on/off 有效对照 |
| "route_log 提升通关率" | 3 局、跨配置 |
| "MAP-30 是能力地板" | 20/27 是预算截尾 |
| "后台账单已核对" | 无账单，状态 `NO_EXTERNAL_BILL_PROVIDED` |
| "CI 已通过" | 本轮未触发远端；E2E 仍非阻断 |
| "重复 3 次就是 N=3 样本" | 统计单位是 `(map, seed, agent)`，重复不是新 seed |

### 已知失败与缺陷（本轮发现）

1. **`public_dict()` 派生字段破坏往返**：第一版把 `deterministic_claim` 塞进
   `sampling`，导致 V12 的两个 round-trip 测试失败（`1638 passed` 之前出现 2 failed）。
   已改为"派生值按需计算"，`public_dict` 保持可往返。
2. **压力数据首次读取被安全软件放大**：第一版 `index_cold_build` 测出 10–70 秒，
   实为杀毒扫描；已改为测量前预热，并在报告里写明读法。
3. **`pathlib.is_dir()` 在 Windows 上对 5 000 目录要 1.6 秒**：已改用 `os.scandir`
   （`entry.is_dir()` 来自目录枚举），冷构建从 48 s 降到 3.3 s。
4. **CI E2E 仍未阻断**：没有取得连续可靠证据，按提纲要求保留 `continue-on-error`。

## NEXT：下一轮最优先 5 项

1. **方案 A 的 LIVE 验证**（54 局，预估 ¥1.68，上界 ¥5）：确认三个机制在真实模型上
   是否有可测效果；先看翻转率是否下降，再谈提升。
2. **重复提到 3–5 次**：当前 3 次观测的翻转率仍 25%，只有 `planning@MAP-16 seed 1`
   是 3/3。要提高结论强度，先加重复而不是加地图。
3. **CI E2E 转阻断**：连续 3 次成功后再改 `continue-on-error: false`。
4. **后台账单对账**：用户导出脱敏 CSV 后跑 `audit_v13_ledger.py --bill`，
   把 `NO_EXTERNAL_BILL_PROVIDED` 变成 `RECONCILED_WITH_EXTERNAL_BILL`。
5. **六图之外的长失败前缀**：MAP-19/20/29 用 V13 运行时重采机制触发证据，
   扩展"可区分能力"的地图集合（**不新建 seed、不改规则**）。

## 费用

| 项 | 值 |
|---|---|
| 本轮新增 LIVE 局数 | **0** |
| 本轮新增 LIVE 金额 | **CNY 0.00000000** |
| V13 已批准总额 | **¥0**（未申请、未获批） |
| V12 剩余额度 | ¥0.56319988（**未挪用**） |
| 后台对账 | `NO_EXTERNAL_BILL_PROVIDED` |
| 若批准方案 A | 上界 ¥5.00，预估 ¥1.68（见 `live-budget-proposal.md`） |

## 复现

```bash
uv run python scripts/verify_v13.py     # 18 项离线验收（零请求）
uv run python scripts/demo_v13.py       # 零 Key 演示（SIMULATED）
uv run agent-arena web                  # 五页 Lab
```

完整命令与文档索引见 `release-checklist.md`；逐任务状态见 `gap-audit.md`。

## 截图

| 文件 | 内容 |
|---|---|
| `docs/v13/screenshots/01-lab-stability.png` | 稳定性与效度（V12 历史：翻转率 0.375 / 排除 22 组 / 138 观测） |
| `docs/v13/screenshots/02-lab-stability-mobile.png` | 同页 430px 窄屏 |
| `docs/v13/screenshots/03-lab-audit.png` | 报告与审计（结论摘要直接展开） |
| `docs/v13/screenshots/04-lab-ledger-audit.png` | 账本审计（演示目录 0 条目 + 明确提示） |
| `docs/v13/screenshots/05-lab-sdk-selfcheck.png` | SDK 自检 8/8 通过 |
| `docs/v13/screenshots/06-lab-audit-dark.png` | 报告与审计（深色） |
| `docs/v13/screenshots/07-lab-results-pairs.png` | 结果页配对明细（逐对判定 + 不可比原因） |
