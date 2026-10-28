# `results/` — 基准聚合结果（审计证据）

本目录从 V14 起**纳入版本库**（此前按"生成物不入库"规则被忽略）。理由：`docs/` 里引用的
历史基准数字（V1/V2 阶段的 Muse 配置扫描、`benchmark_v3` / `evaluation_v2` 聚合指标）
需要可核对的原始聚合文件，否则审计者只能相信文字。

## 1. 里面是什么

| 类型 | 数量 | 说明 |
|---|---:|---|
| `benchmark_v3` + `evaluation_v2` 的 `*.json` | 33 个文件 / 110 条 `rows` | 基准聚合：`conditions` / `rows` / `aggregates` / `totals` |
| 同名 `*.csv` | 42 个 | 同一批聚合的表格版（逐条 episode 指标） |
| `failure_analysis.csv` | 若干 | 失败类型分布 |
| `manifest.json` | 2 个（V3 Muse 大实验） | 实验设计快照：provider / model / prompt_sha256 / seed 计划 / 终止策略 |
| 其它 JSON | 61 个 | 早期 `exp-*` 单次运行与 V2 预算探测记录 |
| `run_matrix.py` / `pipeline_driver.py` / `recovery_pipeline.py` | 4 个 | **V3 Muse 实验的驱动脚本**：`scripts/` 里没有同名文件，这是唯一副本（`manifest.json` 记录了 `source_commit`），用于复现该实验 |
| `recovery_pipeline_state.json` | 1 个（256K） | 可恢复运行的状态快照：解释了"150 个 episode 为什么有 155 次尝试"（重试是独立 attempt） |

## 2. 目录命名与对应阶段

| 前缀 | 阶段 | 对应文档 |
|---|---|---|
| `exp-C010*` `exp-C011*` `exp-E1*` `exp-Pctx*` `exp-ReactC111*` `exp-SeedSmoke` | V1 研究闭环：Planning/Memory 上下文变量的单因子扫描 | `docs/research/v1/`、`研究总纲.md` |
| `muse-memory-*` `muse-planning-*` `muse-react-*` `muse-lighthouse-*` `muse-shipv3-*` | 2026-10 起切到 `muse-spark-1.3-contributor` 后的配置叠加实验（history 窗口 / recovery / phase prior） | `docs/research/v1/08-cross-task-and-e1.md` |
| `v2-s2-m1-*`（含根级 `v2-s2-m1-budget-0{1,2,3}.json`） | V2 S2 预算探测 | `docs/research/v2/00-run-registry.md` |
| `v3-muse-react-*` | V3 十世界三十图 + Muse 的自主/不限步实验（`status: incomplete` 是**真实状态**，不是错误） | `docs/world-design-v3/` |

## 3. 口径提醒（读这些数字前必须知道）

1. **不同前缀不可互相比较**。V1 的 Legacy 世界、V2、V3 的 Action/Observation contract
   完全不同；把它们放进同一张成功率表是错误的。
2. **`rows` 数是 episode 数，不是独立世界样本**。同一 selector 的多个 seed 属于同一地图。
3. **`status: incomplete` 的实验**（如 `v3-muse-react-unbounded-*`）表示计划未跑完；
   其中的数字只能描述已完成的那些 episode。
4. **`schema_version = benchmark_v3` / `evaluation_schema_version = evaluation_v2`** 是当时的口径；
   V10 之后的主指标口径见 `docs/v10/`，两套不可混算。
5. **这些是历史结果，不代表当前能力**。V12 起的所有结论都来自 `docs/v12/`–`docs/v14/`，
   且 V12 已证明同条件重复的结局翻转率 22.2%–25.0%，单次观测不足以排序。

## 4. 明确不在这里的东西

| 内容 | 位置 | 为什么 |
|---|---|---|
| 原始逐局 trace（`events.jsonl` / `result.json`） | 本机 `runs/`（不入库） | 体积 487M，且含本机绝对路径；V14 决策见 `docs/v14/stage2-closure.md` |
| 付费账本（`web_ledger.jsonl`） | 本机 `runs/*/_ledger/`（不入库） | 含结算金额，仅以聚合形式写入 `docs/v14/live-results.json` |
| 运行日志（stdout/stderr） | 本机 `logs/`（不入库） | 无结构化证据价值，`events.jsonl` 已覆盖 |
| V14 的 308 局 MiMo 明细 | `docs/v14/live-results.md/.json` | 由 `scripts/summarize_v14_live.py` 从本机 `runs/v14/live` 只读聚合生成 |

## 5. 校验方式

```bash
# 结构完整性：所有 benchmark 文件都能被解析，且 schema 一致
uv run python - <<'PY'
import json, pathlib
bad = []
for p in pathlib.Path("results").rglob("*.json"):
    try:
        json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        bad.append((str(p), str(exc)[:60]))
print("unparsable:", bad or "none")
PY

# 与 docs 的交叉核对（示例：Muse 9 配置 × 5 seeds = 45/45）
uv run python -c "
import json
p='results/muse-memory-s60-h5rp/benchmark_20261010T182036Z_memory_5-seeds_5-episodes_a055086d.json'
d=json.load(open(p,encoding='utf-8'))
print('rows', len(d['rows']), 'aggregates', len(d['aggregates']))
"
```

## 6. 卫生说明

- 已扫描：**无** API key / token / `Bearer` 串（`sk-`、`api_key=`、`OPENAI_API_KEY` 全部 0 命中）。
- 已扫描：**无**本机绝对路径或用户名。
- 已排除：`*.lock`（运行时锁文件，0 字节）、`__pycache__/`、`*.pyc`（见 `.gitignore`）。
- 含模型名与公开端点主机（`muse-spark-1.3-contributor` / `opencode.ai` 等）——这些在
  `AGENTS.md` 与 `研究总纲.md` 中已公开登记，属于实验溯源信息，不是凭据。
