# V2-01 CI 与基线

## 基线快照

- 核验日期：2026-10-13（Asia/Shanghai）。先执行 `git fetch origin`；本地 `main` 与 `origin/main` 均为 `587dccd43e1a3c39bb78c75e199bfc66ab1331e2`，工作区仅有本轮维护文件和用户未跟踪的 `研究提纲/`。
- 最新 Actions 为 [CI run 38353317972](https://github.com/wenxvn/Agent-Arena/actions/runs/38353317972)，提交 `587dccd43e1a3c39bb78c75e199bfc66ab1331e2`，结论 `failure`。
- run 的 `uv sync --frozen --all-groups` 通过；`ruff check .` 报 25 项，故 `mypy src` 与 `pytest` 均被跳过。

## 修复范围

- 移除 `scripts/audit_maps.py` 中未使用的循环绑定和死代码；将 `scripts/build_run_register.py` 的 lambda 改成局部函数。
- 修复 UI 的异常链与超长行；补全 zip 长度契约，并整理受 Ruff 规则影响的测试代码。
- 将所有世界工厂的公开返回类型改为共同的 `Environment` 基类；以 `WorldDefinitionLike` 描述各确定性环境读取的共享定义字段，避免逐个地图版本伪装成同一 Pydantic 类型。
- UI 汇总仅把数值型步数/token纳入聚合，并跳过缺失或非整数的成功 seed，避免缺值进入排序和运算。
- 同步校正文档中的 E1-ON 条件、首次尝试与重跑口径，并修正火山均值并非全难度单调递增的描述；实测数值不变。

## 本地验证

在仓库外的临时目录建立工具和虚拟环境，使用 Python 3.13.16 与 uv 0.13.0；项目本身的 `.venv`、依赖锁文件未被重建或改写。

| 检查 | 结果 |
|---|---|
| `uv sync --frozen --all-groups` | 通过 |
| `uv run ruff check .` | 通过 |
| `uv run mypy src` | 通过，48 个源文件 |
| `uv run pytest -q` | 通过，304 passed |
| `uv lock --check` | 通过，36 个 packages 已解析 |
| `git diff --check` | 通过 |

未启动模型调用或 GPU 任务；历史 trace 与世界定义未改写。

## 研究口径校正

- 9 配置的 45/45 指去重后每个配置至少出现一次成功；原始 51 个 trace 为 46 次成功和 5 次 `provider_error`，按所有尝试计为 46/51（90.2%）。E1-ON 的 prompt hash 为 `44229085`。新世界没有 E1-OFF 对照，因此不能把新世界的零误用描述成受控消融。
- 10×3 的 150/150 指 150 个配置最终均有成功 trace，其中存在网关失败后的补跑；不代表首次尝试 150/150 稳定成功。
- 七个新世界中，火山困难图均值为 31.4 步，低于中等图的 35.4 步；其他六图均值随难度递增。

## 远端 Gate 与下一步

远端 `origin/main` 当前仍停在基线提交。以上修复与本地质量检查已完成，尚未推送，因此还没有对应修复提交的 Actions 结果；S0 只有在推送后 `quality` 成功才算通过。修复提交 SHA 与对应 run 将在远端验证后补记。

V1 的旧审计和 SUMMARY 保留为当时的历史快照；其中“CI 待 push 确认”不能当作当前状态，应以本文件记录的 2026-10-13 run 和本节后续远端验证为准。
