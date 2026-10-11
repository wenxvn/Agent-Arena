# V1-01 CI 与数据可追溯（T1）

## 1. 研究问题与假设

- 问题：仓库“159 passed”“45/45”是否为可追溯证据？
- 假设：一次导入修复即可恢复 CI；旧 trace 完整且可机读；`provider_error` 未被成功率统计静默吞掉。

## 2. 代码版本与环境

- 代码：`main@4b3261b` + 本轮 1 行修复（`tests/test_phase_tracker.py` 去掉 `LIGHTHOUSE_MILESTONES` 未使用导入）。
- 模型/world：不涉及（离线审计，0 次 LLM 调用）。
- 真实命令（Windows + Python 3.11.9，`uv` 未安装）：
  - `$env:PYTHONPATH="src"; python -m pytest tests/test_phase_tracker.py -q` → 3 passed
  - `$env:PYTHONPATH="src"; python -m pytest -q` → **159 passed**
  - `python -m ruff / python -m mypy / uv` → 无模块/无命令（blocked，见 §6）
  - `git diff --check` → 通过（除 CRLF 提示外无空白错误）

## 3. 引用 trace 与新增局

- 引用：`runs/muse-9maps-*` 51 文件（见 `00` §2 去重表）；`results/muse-*` 15+ benchmark JSON/CSV。
- 新增运行：0。无中断/重试/丢失（本轮未启动模型实验）。
- 历史 trace 未被清理、覆盖或重命名（`git status` 仅 `研究提纲/` 未跟踪 + 本轮新文件）。

## 4. 实验结果

### 4.1 CI 修复

| 检查 | 本地结果 | CI 状态 |
|---|---|---|
| Ruff F401（`LIGHTHOUSE_MILESTONES`） | 已删，文件 3 passed | 待 GitHub Actions 全绿（blocked：本机无 ruff，需 push 后看链接） |
| pytest 全套 | 159 passed | 待 CI |
| mypy | 本机无模块，blocked | 待 CI |
| `uv lock --check` | 本机无 uv，blocked | 待 CI |

修复 diff：`tests/test_phase_tracker.py:3`
`-from agent_arena.worlds.lighthouse import LIGHTHOUSE_MILESTONES, LighthouseEnvironment`
`+from agent_arena.worlds.lighthouse import LighthouseEnvironment`

全仓其他 F401 目检：该文件是唯一在提纲点名的失败点；无 ruff 本机无法全量担保，已在报告中标记，CI 为准。

### 4.2 provenance 结论（verified）

- 每个 9maps trace 含 `episode_id, world/version/hash, agent=memory, provider/model, prompt, 条件开关（provenance）, step_limit=0, seed, outcome, action_count, tokens, error`。抽查 `runs/muse-9maps-ship-med/…_seed-2_1ad88ffc.json` 头字段齐全。
- `provider_error` trace 尾事件 `event=provider_error, action=None, result=None`，`invalid_output_count=0`（除 light-easy s0 另有 3 次环境拒绝），与 `success` 可区分，未被静默吞掉。
- 无重复 episode 记数：去重规则见 `00` §2；`abyss-easy seed-2` 双 success 取先到，已注明歧义。
- 可靠性口径：去重后 `45/45=100%`（每组合至少一次成功）；原始尝试 `46/51=90.2%`。若原始失败数据缺失，只报下界，不称“恰好 51 次尝试之外无失败”。

### 4.3 基线契约测试（已有覆盖，verified 位置）

| 契约 | 测试位置 |
|---|---|
| `Action` 统一校验 | `tests/test_experiment_contract.py`（schema/非法分类） |
| hidden `WorldState` 不暴露 | `tests/test_experiment_contract.py:121-125`（`WorldState` 不进请求） |
| world selector 与 hash | `tests/test_experiment_contract.py:29-55`（未知组合拒跑、hash 记录） |
| 旧 trace 兼容 | `src/agent_arena/evaluation/trace.py:read_episode_trace` + `tests/test_trace_v2.py` |
| provider_error 统计 | `src/agent_arena/evaluation/trace.py:20`（`EpisodeOutcome.provider_error` 独立）+ `benchmark.py` 行级 outcome |

本轮新增契约测试（离线，0 模型调用）：

- `tests/test_terminal_contract.py`（T4）：灯塔 fixture `read_terminal` 恒 `WRONG_TARGET`、重复 `CODE_READ` 无新事实。
- `tests/test_phase_prior_audit.py`（T3）：`PublicPhaseTracker.render` 在未探索时即暴露关键物品名 + 阶段顺序（world-declared guidance 证据）。
- `tests/test_seed_replicate.py`（T6）：同 seed 可复现、异 seed 同地图、`create_environment` 拒未知组合。
- `tests/test_success_at_k.py`（T2）：`Success@K` 裁剪规则的边界/缺字段/重复/censored 单测。
- `scripts/build_run_register.py`：台账再生脚本（`--runs-dir/--results-dir/--output`）。

## 5. 证据支持/不支持什么

- 支持：CI 红灯根因为单行未使用导入；旧 trace 机读完整；45/45 在去重口径下可复算（见 `02`）。
- 不支持：本地 159 passed 不等价 CI 全绿（Python 3.11 vs CI 3.13 + 缺 ruff/mypy）；“6 次网关异常”缺 1 件源文件，不补数字。

## 6. 阻塞与最小复现

- blocked：本机无 `uv/ruff/mypy`（Python 仅 3.11，项目要求 3.13）。复现：`python -m ruff --version` → `No module named ruff`。
- 恢复条件：push 后看 GitHub Actions `quality`（ruff/mypy/pytest）全绿链接；或在本机装 uv + Python 3.13 后重跑提纲 §T1 命令。
- 外部 GitHub 障碍若导致不能确认，标记 + 保留本地结果（本报告即此口径）。

## 7. 下一步

T2 离线效率报告（`02`），尽量 0 次新 LLM 调用。
