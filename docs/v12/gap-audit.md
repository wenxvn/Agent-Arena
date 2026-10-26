# V12 提纲逐项对照：已完成 / 部分完成 / 未完成

对照对象：`研究提纲/V12Agent-Arena_V12_第二阶段完整执行提纲.md`（未纳入 Git）。
本文件只记录**状态事实与差距原因**，不重复 `progress.md` 的完成证据。

- 生成日期：2026-10-26
- 结论：提纲中没有被静默跳过的必做项；剩余 5 项属于**用户主动暂缓**、
  **客观无法在本机完成**、或**提纲自身标注为"可选"**。

## 1. 仍未完成（5 项）

| # | 提纲位置 | 内容 | 状态 | 原因 | 能否补 |
|---|---|---|---|---|---|
| 1 | V12-11-04 | macOS 实机验证 | `NOT_VERIFIED` | 用户明确指示"macOS 以后再说" | 需 macOS 设备 |
| 2 | 技术与模型配置 | Ollama 实机验证 | `NOT_VERIFIED` | 用户明确指示"Ollama 以后再说" | 需本机 Ollama |
| 3 | V12-12-06 | Provider **后台账单**对账 | 未做 | 只有本地登记价目 + 返回 usage 的对账（已逐局对齐）；后台账单需登录 Provider 控制台 | 需用户提供账单 |
| 4 | V12-07-06 | 可选 LLM 生成报告解说 | 未实现 | 提纲标注"可选"；核心诊断已做到零 API、可离线 | 是（需额外费用与设计） |
| 5 | V12-11-02 | CI 浏览器 E2E 作为**门禁** | 已接入但 `continue-on-error` | 首次运行需 `playwright install`，冷启动不稳定；本地已实跑通过 | 是（需稳定 runner） |

## 2. 部分完成（3 项，已披露）

| # | 提纲位置 | 差距 |
|---|---|---|
| 6 | V12-11-07 压力测试 | 七项里覆盖 6 项（54 局 dry-run、损坏 JSONL、超时、未知消费、大 CSV、进程退出取消）；"**上千条历史**分页"只有边界单测（`test_page_rows_bounds` / `test_home_paginates_map_lobby`），没有大历史量压力 |
| 7 | V12-08-09 六图 fixture | MAP-22/MAP-08 用真实 SIMULATED 轨迹；MAP-16/18/26/30 部分用**合成 UI fixture**，已在文件头声明"非真实模型" |
| 8 | V12-11-03 真机可访问性 | 自动审计（对比度/焦点/DOM/键盘）0 critical/serious/moderate；**真机 + 读屏软件**未测 |

## 3. 本轮补齐的两项（原先未做）

| # | 提纲位置 | 原状态 | 现状态 | 证据 |
|---|---|---|---|---|
| 9 | V12-12-05 反思独立小矩阵 | `NOT_RUN` | **DONE**（12 局，¥0.09626428） | `docs/v12/ablations.md` §3 |
| 10 | §4.3-1 Memory 关闭/开启 | 仅离线消融测试 | **DONE**（MAP-18 × 2 seed） | `docs/v12/ablations.md` §1 |
| 11 | §4.3-2 Planning 关闭/开启 | 仅离线消融测试 | **DONE**（MAP-16 × 2 seed） | `docs/v12/ablations.md` §2 |
| 12 | §4.3-3 Reflection 触发/关闭 | `NOT_RUN` | **DONE（但触发器未激活，对照无效）** | `DCR-V12-05` |

## 4. 提纲 §10 交付清单 A–I

| 项 | 状态 | 说明 |
|---|---|---|
| A 可独立运行的 Lab 1.0 网页流程 | DONE | `uv run agent-arena web` → Lab 三页 |
| B Basic/Memory/Planning + Reflection | DONE | 四种策略都实跑过（Reflection 见 DCR-V12-05） |
| C ExperimentSpec / 队列 / 父子 run / 预算 / 幂等 / 版本化存储 | DONE | `lab/experiment.py`、`lab/contracts.py` |
| D 六图方案 + 配对分析 + 五态 + 自动导出 | DONE | `lab/compare.py`、`lab/report.py` |
| E 诊断 / 轨迹 Diff / 证据 / 六图可视化 | DONE | `lab/diagnostics.py`、`lab/visualization.py` |
| F 第三方 SDK + 只读导入 + API 文档 | DONE | `lab/sdk.py`、`examples/custom_agent/` |
| G 一键验收 / CI / E2E / 截图 / 演示包 | DONE（CI E2E 非门禁） | 见第 5 项 |
| H `docs/v12/` 全套文档 | DONE | 审计 / ADR / 协议 / 进度 / 验证 / Checklist / Final |
| I 真实 Pilot + 主矩阵 | DONE（159 局，¥5.43680012） | 见 `mimo-results.md` |

## 5. 说明：为什么"修完再跑"的四个衍生实验不在提纲里

提纲只定义了 54 局主矩阵与补充实验。本轮额外做的 **版本复跑 / 预算扩展 / 重复 /
路线日志消融** 是为了处理真实测量缺陷（DCR-V12-01…06），不是提纲要求项；
它们各自新建实验、不污染主矩阵，已在 `mimo-results.md` 单独列表。

## 6. 复现所有真实实验的花费

| 项 | 值 |
|---|---|
| 批准上限 | CNY ¥6.00 |
| 实际结算 | **¥5.43680012**（20 个实验 / 159 局 / 5 641 请求） |
| 未知消费 | ¥0.00 |
| 剩余 | ¥0.56319988（主动保留，未用于新增实验） |
