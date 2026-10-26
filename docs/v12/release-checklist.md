# V12 发布检查清单

- **评估日期**：2026-10-25
- **结论**：`LAB_1_0_READY`（P0 + P1 + P2 全部交付；真实模型实验 12 个、125 局、¥4.92471204）
- **不是**：公网生产就绪（单机本地，无登录/多租户）

## P0 —— `LAB_CORE_READY`

| 项 | 状态 | 证据 |
|---|---|---|
| 统一 Agent Adapter（`AgentPolicy` + 网关） | DONE | `lab/policies/base.py`、`lab/gateway.py` |
| `basic.v1` / `memory.v1` / `planning.v1` | DONE | `lab/policies/*`、`tests/test_v12_policies.py` |
| 实验矩阵与批量队列 | DONE | `lab/experiment.py` |
| 可比较结果（配对 + 不可比声明） | DONE | `lab/compare.py` |
| 预算安全（单局 + 实验级 + 未知消费） | DONE | 真实 71 局：0 未知消费、未超 ¥6 |
| V11 回归保持通过 | DONE | `validation-report.md` §4 |

**Gate：`LAB_CORE_READY` = 通过。**

## P1 —— 从"能运行"到"能解释"

| 项 | 状态 | 证据 |
|---|---|---|
| Reflection（公开触发器 + 限额 + 消融） | DONE | `lab/policies/reflection.py` |
| 轨迹差异与失败诊断 | DONE | `lab/diagnostics.py` |
| 六图专属可视化 | DONE | `lab/visualization.py` |
| Lab 网页流程 | DONE | `ui/lab.py` + 3 个导航项 |
| 可读报告 | DONE | `lab/report.py::build_report` |

## P2 —— 可用性与交付质量

| 项 | 状态 | 证据 |
|---|---|---|
| 第三方 Python Agent SDK | DONE | `lab/sdk.py`、`examples/custom_agent/` |
| 只读导入公开轨迹 | DONE | `read_public_run_file` |
| 一键离线验收 | DONE | `scripts/verify_v12.py`（11/11） |
| CI 浏览器 E2E | DONE | `.github/workflows/ci.yml` `lab-e2e` |
| 截图（桌面/窄屏/深色） | DONE | `docs/v12/screenshots/`（8 张） |
| Demo 包（三组） | DONE | `docs/v12/demo/` |
| 压力/故障测试 | DONE | `tests/test_v12_robustness.py` |
| 跨平台 | PARTIAL | Windows 实测；Ubuntu CI；macOS 按用户指示暂缓 |
| 可访问性自动检测 | DONE | `scripts/a11y_v12.py`：对比度（22 token × 2 方案）+ 焦点样式 + 6 页 DOM/键盘（浅色/深色），0 critical / 0 serious / 0 moderate |
| 衍生实验流程 | DONE | 补充 / 版本复跑 / 预算扩展 / 重复；31 项测试 |
| 真实 API 验证 | DONE | 125 局、¥4.92471204、0 未知消费；详见 `mimo-results.md` |

## 交付物 A–I（对应提纲 §10）

| 编号 | 内容 | 状态 |
|---|---|---|
| A | 可独立运行的 Lab 本地网页流程 | DONE |
| B | Basic/Memory/Planning + Reflection（可关闭/触发事件明确） | DONE |
| C | ExperimentSpec、批量队列、父子 run、全局预算/幂等/版本化存储 | DONE |
| D | 六图方案、统一配对分析、五态指标、自动导出 | DONE |
| E | 行为诊断/两轨迹 Diff、可点开证据、六图可视化 | DONE |
| F | 第三方 Python Agent 示例、只读导入、API 文档 | DONE |
| G | 一键离线验收、CI/E2E、V11 兼容回归、截图、无 Key 演示包 | DONE |
| H | `docs/v12/` 审计/ADR/协议/进度/验证/Checklist/Final | DONE |
| I | 真实 Pilot + 54 局矩阵 | **DONE**（12 个实验、125 局、¥4.92471204；含 Pilot / 主矩阵 / MAP-22×2 / MAP-30×2 / 种子覆盖×3 / 重复×1） |

## 明确未完成（不冒充通过）

- [x] MAP-22 记忆假设 —— 接口与口径已修好，得到**可测量的负结果**（DCR-V12-03）
- [x] MAP-30 能力 —— 抬预算后 4/9 走到法庭且 `ACCUSATION_REJECTED`（DCR-V12-04）
- [ ] 反思独立小矩阵 —— 需单独预算批准，未混入主矩阵
- [x] 重复次数 —— 已做 1 次重复（18 组，翻转率 22.2%）；扩到 3 次列入 NEXT
- [ ] macOS 实机 / Ollama 实机 —— 按用户指示暂缓
- [ ] 移动端真机
- [ ] Provider 账单对账
- [ ] `<html lang>` 本地化 —— Streamlit 前端固定为 `en`，应用层无法覆盖（已披露）

## 发布动作

- [ ] 提交源码/文档/脱敏演示资产（**不提交** `runs/`、`results/`、`.env`）
- [ ] 推送后确认 CI `quality` 与 `lab-e2e` 结果
- [ ] 不打正式 tag / Release（需用户明确确认）
