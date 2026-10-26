# V13 验证报告

- 生成日期：2026-10-26
- 环境：Windows 11（`Windows-11-10.0.26200-SP0`）、Python 3.13.3、uv 0.13.3
- 真实付费请求：**0**

## 1. 质量门禁（逐条实跑）

| 命令 | 结果 | 备注 |
|---|---|---|
| `uv run ruff check .` | **All checks passed!** | 全仓库 |
| `uv run mypy src` | **Success: no issues found in 323 source files** | |
| `uv run pytest -q` | **1639 passed**（132.91s） | V13 新增 114 项 |
| `uv lock --check` | 无变更 | `uv.lock` 未改 |
| `git diff --check` | 无输出 | |
| `python -m agent_arena.v10.freeze verify` | **9/9 unchanged** | 冻结区未动 |
| `python -m agent_arena.v10.recompute --check` | 1093/1093，0 不一致 | |
| `python -m agent_arena.v10.independent_check --check` | 0 违规 / 回放确定 30/30 / seed 互异 30/30 | |
| `python scripts/verify_v11.py` | 7/7 | V11 未回归 |
| `python scripts/verify_v12.py` | 15/15 | V12 未回归 |
| `python scripts/verify_v13.py` | **18/18** | 新增 |
| `python scripts/e2e_web.py --start` | 见 §2 | |
| `python scripts/e2e_lab.py --start` | 见 §2 | |
| `python scripts/a11y_v12.py --browser --start` | 见 §2 | |

### 1.1 mypy

```text
$ uv run mypy src
Success: no issues found in 323 source files
```

V13 新增模块全部有类型注解；第一轮出现 10 个 `union-attr` / 赋值类型问题，
全部在源码里修掉（不是加 `type: ignore`）。

### 1.2 pytest

```text
$ uv run pytest -q
1639 passed in 132.91s (0:02:12)
```

其中 V12 基线 1525 项全部保留通过；V13 新增 **114 项**：

| 文件 | 项数 | 覆盖 |
|---|---:|---|
| `test_v13_contracts.py` | 12 | 重复身份、采样登记、协议指纹、V12 向后兼容 |
| `test_v13_comparability.py` | 11 | 画像、单变量、跨实验配对、硬拒绝 |
| `test_v13_stability.py` | 14 | 复算 22.2%/25%，跨版本排除，seed 分块，导出 |
| `test_v13_policies.py` | 23 | memory.v2 / planning.v2 / reflection.v2 机制 |
| `test_v13_analysis.py` | 17 | 消融模板、证据包、效度、归因、画像 |
| `test_v13_report_ledger.py` | 19 | 报告快照/分级/脱敏、账本审计、账单对账 |
| `test_v13_runtime.py` | 13 | 分页索引（含懒加载与全量逐行一致）、SDK 自检、压测隔离、一键验收 |
| `test_v13_ui.py` | 5 | 两个新页面 stub 冒烟 |

> 114 项 = 上述 8 个文件的用例数之和；`pytest -k v13` 实测 **114 passed**。

## 2. 浏览器端到端与可访问性

### 2.1 本地实测（Windows，2026-10-26）

| 脚本 | 结果 | 证据 |
|---|---|---|
| `scripts/e2e_lab.py --start` | **通过** | `{"ok": true, "monitor_state": "COMPLETED", "report_bytes": 8963, "report_lines": 139, "v13_stability_page": true, "v13_audit_page": true, "v13_sdk_selfcheck": true}` |
| `scripts/e2e_web.py --start` | **通过** | `{"ok": true, "state": "SUCCEEDED", "steps": 15, "download_bytes": 24801}` |
| `scripts/a11y_v12.py --browser --start` | **通过** | `ok: true`；浅/深两套主题 0 critical / 0 serious / 0 moderate；主题 token 与焦点样式均通过 |

V13 对 E2E 的增量：

- `e2e_lab` 现在覆盖 **5 页**（原 3 页 + 稳定性与效度 + 报告与审计），并在报告与审计页
  真的点「运行 SDK 自检」并断言 `SDK 自检全部通过`；
- `a11y_v12` 的页面清单加入两个新页面，浅/深主题各审一遍；
- `scripts/capture_v13_screenshots.py` 生成 7 张截图（含 430px 窄屏与深色），
  写入 `docs/v13/screenshots/`。

**过程中修掉的两个真实缺陷**：

1. 新增页面最初没有加进 `ui/app.py` 的 `VIEWS`，侧边栏不显示、`?view=` 深链也无效
   → E2E 首次运行超时（`waiting for get_by_text("六图效度")`），补 `VIEW_LAB_STABILITY` / `VIEW_LAB_AUDIT`。
2. 报告与审计页最初只有「生成 V13 报告」按钮，点完只出现下载链接（截图里是一片空白）
   → 改为在按钮下方直接展开「结论摘要（分级 + 锚点）」；账本页在 0 条目时补明确提示
   （演示目录不写付费账本，真实 159 局审计要跑脚本）。

### 2.2 CI（GitHub Actions）

| 项 | 状态 |
|---|---|
| `quality` job（lock / ruff / mypy / pytest / freeze / recompute / independent / verify_v11 / verify_v12 / verify_v13） | **本地全绿**；CI 是否执行需看 GitHub Actions 运行记录 |
| `lab-e2e` job | 仍为 `continue-on-error: true` → **`NOT_VERIFIED`**（本轮未取得 CI 连续可靠证据） |

**诚实结论**：本轮**没有**触发 GitHub Actions（无远端推送授权），
因此不能声称"CI 通过"。本地等价命令全部实跑通过。

## 3. 离线验收明细（`verify_v13.py`，18 项）

| # | 检查 | 结果 | 说明 |
|---|---|---|---|
| 1 | `contract_v13` | ✅ | 重复身份、采样口径、协议指纹、V12 旧规格可读 |
| 2 | `v10_freeze` | ✅ | 9 个冻结根全部 unchanged |
| 3 | `thirty_maps` | ✅ | 30 图 + 30 组唯一 hash |
| 4 | `history_reproduction` | ✅ | 22.22% / 25.00%，排除 6 组跨版本 |
| 5 | `ledger_reproduction` | ✅ | 159 局 / 5641 请求 / ¥5.43680012 |
| 6 | `map30_ladder` | ✅ | 3 档；法庭被拒 4/2；截尾 5/7 |
| 7 | `six_map_validity` | ✅ | 08/26 `CEILING`、16/18/22 `SUITABLE`、30 `CENSORED` |
| 8 | `policies_v13` | ✅ | 三个 v2 策略在 MAP-22/16 有机制证据，无泄漏 |
| 9 | `ablation_templates` | ✅ | 7 模板全部单开关；版本比较被识别 |
| 10 | `comparability` | ✅ | 可比/不可比/单变量三态 |
| 11 | `taxonomy_capability` | ✅ | 8 个 fixture 全绿；6 维画像无补零 |
| 12 | `report` | ✅ | 分级 + 锚点 + 负面结果 + 脱敏 |
| 13 | `ledger_tooling` | ✅ | 孤儿检测、对账成功、差额检测 |
| 14 | `sdk` | ✅ | 8 项自检全通过 |
| 15 | `pagination` | ✅ | 120 条分页、筛选、聚合 |
| 16 | `replicate_flow` | ✅ | 3 次重复同实验、幂等、3 个不同 run |
| 17 | `simulated_isolation` | ✅ | SIMULATED 不写付费账本 |
| 18 | `exports_recompute` | ✅ | CSV/JSON/MD 行数与记录数一致 |

## 4. 演示包（`scripts/demo_v13.py`）

| 项 | 值 |
|---|---|
| 通道 | `SIMULATED`（确定性脚本 Provider） |
| 矩阵 | MAP-22 + MAP-16 × 4 架构 × 1 seed × 2 重复 = 16 局 |
| 状态 | `COMPLETED` |
| 类别 | 16 局全部 `budget_censored`（脚本动作不解决问题，属预期） |
| 翻转率 | 0.0（同脚本动作，确定性） |
| Reflection 探针 | `triggered=2`、`exposure=TREATMENT_TRIGGERED` |
| 产物 | `report_v13.md/json`、`repeat_variability.*`、`map-validity.md`、`capability-profile.md`、`diagnosis-taxonomy.md`、`reflection-trigger-probe.json` |

**明确标注**：演示目录内有 `DEMO_SIMULATED.txt`，报告标题写 `SIMULATED`，
**不得**当作模型能力证据。

## 5. 压力测试（`scripts/stress_v13_history.py`）

| 规模 | 冷构建 | 增量重建 | 懒加载首页 | 已建索引翻页 | 聚合 | 峰值内存 |
|---:|---:|---:|---:|---:|---:|---:|
| 1 000 | 499 ms | 203 ms | 18.5 ms | 0.10 ms | 0.77 ms | 1 443 KiB |
| 5 000 | 3 318 ms | 1 173 ms | 30.7 ms | 0.41 ms | 3.87 ms | 7 278 KiB |

- 压力数据是**合成**的（`stress_data=true`），只写临时目录；
- 测量前预热（先读一遍全部 manifest），避免把安全软件扫描算成代码开销；
- 详见 `performance-report.md`。

## 6. 历史复算一致性

| 数字 | V12 公布 | V13 复算 | 一致 |
|---|---|---|---|
| 2 次观测翻转率（3 份实验子集） | 22.2%（4/18） | 0.2222（4/18） | ✅ |
| 3 次观测翻转率（3 份实验子集） | 25.0%（3/12） | 0.25（3/12） | ✅ |
| 3 次观测排除组 | 6 | 6 | ✅ |
| 全部 14 份历史 CSV 的翻转率 | 未公布 | 0.375（6/16，排除 22 组跨版本/跨预算） | 口径不同，见下 |
| 真实局数 | 159 | 159（账本 settled） | ✅ |
| 请求数 | 5 641 | 5 641 | ✅ |
| 结算金额 | ¥5.43680012 | 5.43680012 | ✅ |
| MAP-30 扩展 1 到法庭 | 4/9 | 4/9 | ✅ |
| MAP-30 扩展 2 截尾 | 7/9 | 7/9 | ✅ |

**关于 0.375 与 0.25 的差异**：V12 的 25.00% 只取"主矩阵 + 两次重复实验"这 3 份 CSV；
V13 的稳定性页默认载入**全部 14 份**历史 CSV，因此 MAP-22 的两次契约版本、
MAP-30 的三档预算会各自形成独立分组。两者都不是错的，但**不能混引**——
`docs/v13/repeat_variability.md` 固定用 3 份子集（与 V12 对齐），
UI 在数字旁明确写出"按当前载入的记录集计算"。

## 7. 未验证 / 阻塞

| 项 | 状态 | 原因 | 下一步 |
|---|---|---|---|
| GitHub Actions 实跑 | `NOT_VERIFIED` | 本轮未推送远端 | 推送后看 Actions 记录 |
| CI E2E 阻断门禁 | `PARTIAL` | 无连续可靠 CI 证据 | 连续 3 次成功后改 `continue-on-error: false` |
| Provider 后台账单对账 | `BLOCKED_EXTERNAL` | 无账单文件 | 用户导出脱敏 CSV 后跑 `audit_v13_ledger.py --bill` |
| 真实模型效果（Memory/Planning/Reflection） | `WAITING_USER_APPROVAL` | 未获 V13 预算授权 | 见 `live-budget-proposal.md` |
| 真机读屏软件 | `NOT_VERIFIED` | 无读屏环境 | 人工验证 |
| macOS / Ollama | 按用户指示暂缓 | — | 不计 V13 缺项 |
| P1-5 新的图形化组件 | `PARTIAL` | 本轮优先做数据正确性（分页/稳定性/效度/归因）；现有表格 + 配对明细已能回答研究问题 | 可加六图 SVG / Diff 高亮 |

## 8. 本轮发现并修复的真实缺陷（自审）

| # | 缺陷 | 如何发现 | 修复 |
|---|---|---|---|
| 1 | `public_dict()` 把派生字段塞进 `sampling`/`protocol`，破坏 JSON 往返 | `pytest` 出现 2 个 V12 回归失败（`test_json_spec_file_round_trip`、`test_only_conditions_survives_json_round_trip`，当时 `2 failed, 1636 passed`） | 派生值改为按需计算（`report._sampling_claim`），`public_dict` 只输出可往返字段 |
| 2 | 新增两个 Lab 页面没加进 `ui/app.py` 的 `VIEWS` | `e2e_lab` 首次运行超时（找不到「六图效度」） | 补 `VIEW_LAB_STABILITY` / `VIEW_LAB_AUDIT` |
| 3 | 压测把"安全软件首次扫描"算成代码开销 | 1 000 条冷构建 10–14 s，与 5 000 条不成比例 | 测量前预热，报告写明读法 |
| 4 | `pathlib.is_dir()` 对 5 000 目录耗 1.6 s | 逐段计时定位 | 改 `os.scandir`（`entry.is_dir()` 来自枚举）；冷构建 48 s → 3.3 s |
| 5 | 证据包把同 `agent_id` 不同配置合成一臂 | 自查 `MAP-22` 的 memory 混合了契约修复前后 | 按 `agent@config_hash` 分臂 |
| 6 | 稳定性页翻转率与文档 25% 不一致 | E2E 截图/文本核对 | UI 明写"按当前载入记录集计算"，文档固定 3 份子集口径 |
| 7 | 懒加载首页与全量排序不一致（`created_at` 相同则顺序随机） | 自查 `RunIndex.page(lazy=True)` vs `lazy=False` 逐行比对 | 排序键改为 `(created_at, run_id)` 降序，并加回归测试 `test_index_lazy_page_matches_full_page` |
| 8 | `list_runs` 每次 rerun 都全量解析 manifest | 阅读 V11 代码时发现（`discover()`） | 改为走 `RunIndex`（字段与 `_summary` 对齐，新增 `_summary_from_entry`） |
| 9 | V13 开发中间版本的 `experiment.json` 读不回（`sampling.deterministic_claim` 越界） | 打开本机 22 个历史实验时 `_spec` 抛 `ValidationError` | `_spec` 读回时剥掉 `sampling.deterministic_claim` / `protocol.fingerprint`，22/22 全部可读 |
| 10 | 报告与审计页点完「生成报告」只有下载链接（截图空白） | 截图审查 | 结论摘要直接展开在按钮下方；账本 0 条目时补提示 |
