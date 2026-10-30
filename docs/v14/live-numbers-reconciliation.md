# V14 LIVE 数字对账（V14.1）

- 目的：把 V14 期间在不同轮次写下的同一指标的不同数字**逐项定性**，并给出最终值。
- 权威来源（只读，可复算）：
  1. `runs/v14/live/` 的 43 个父实验 + 308 个 `result.json`（本机，约 29 MB，`.gitignore`）；
  2. 独立账本 `runs/v14/live/web/_ledger/web_ledger.jsonl`（616 条 started/settled）；
  3. 提交的聚合：`docs/v14/live-results.json`、`docs/v14/live-manifest.json`（逐局 run_id + sha256）。
- 复算命令：

```bash
uv run python scripts/summarize_v14_live.py --write --manifest docs/v14/live-manifest.json
uv run python scripts/summarize_v14_live.py --check-manifest docs/v14/live-manifest.json
uv run python scripts/analyze_v14_map22.py --write
```

> 本轮**没有修改**任何原始 `result.json`、`events.jsonl`、账本或历史 trace；
> 只重新聚合、重新表述，并把口径写清楚。

## 1. 三个计数口径（先定义，再对账）

| 名称 | 定义 | 谁用 |
|---|---|---|
| 局数 / runs | 账本里已 `run_settled` 的局（含 Provider 中断） | 总量、成本 |
| 有效 / valid | 局数 − 中断（`PROVIDER_ERROR` / `CANCELLED`） | 成功率分母 |
| 截尾 / censored | `state = BUDGET_REACHED`（请求/决策上限），**留在有效分母里** | 单独列出，不当机制失败 |

> **V14.1 修复（DCR-V14-11）**：修复前 `summarize_v14_live.py` 把 `PROVIDER_ERROR`
> 归成 `mechanism_failure` 并计入有效分母，等于把"模型没答完"写成"场景机制失败"，
> 还污染了成功率分母。修复后中断单独计数、不进分母。受影响的是 4 局，见 §3。

## 2. 逐项对账

| # | 旧数字 | 出处（首次出现） | 真实含义 | 判定 | 最终值 |
|---|---|---|---|---|---|
| 1 | E1-a **65 局** | `6563bea` final-report（227 局快照） | 该快照下 E1-a = 90 档 20 + 150 档（off 26 + on 19）= 65 | **历史子集**（快照），后续 +18 局未回写 | **83 局** |
| 2 | E1-a **83 局** | 本轮 | 90 档 20 + 150 档 off 26 / on 28 / on-we1 9 | **正确** | **83 局** |
| 3 | Memory 150 档 **on 19 局** | `6563bea` | 写入频率单因子补充之前：seed 0/1/2/3 = 3/3/8/5 | **历史子集** | **28 局**（seed 0/1/2/3 = 6/6/8/8） |
| 4 | Memory 150 档 on 成功率 **0.4211**（8/19） | `6563bea` | 8/19 | **历史子集**口径 | **8/28 = 0.2857** |
| 5 | E2-a **121 局** | `6563bea` final-report | 无法由任何子集复现；同一提交的 `live-results.json` 已是 125（10+7+15+15+27+27+12+12） | **算术错误**（手工求和） | **125 局** |
| 6 | E2-a **125 局** | 本轮 | MAP-16 flash 47 + pro 24 + MAP-18 18 + MAP-26 18 + MAP-14 18 | **正确** | **125 局** |
| 7 | E3 **33–36 局/臂** | `d11bd97` | **seed 2 子集**：on 33、trigger_only 36（各排除 seed 0 的 3 局） | **口径差异**（seed 限定），不是错误 | 臂总量 **36 / 39**；seed 2 为 **33 / 36** |
| 8 | E3 **69 局** | `d11bd97` | 33 + 36，即 seed 2 子集 | **口径差异**（seed 限定） | E3 总量 **100 局** |
| 9 | E3 **95 局** | `d11bd97` final-report | MAP-22 + MAP-19 子集（排除 MAP-16 的 5 局暴露探针） | **口径差异**（图限定） | E3 总量 **100 局** |
| 10 | MAP-16 flash on **有效 15 / 14/15 = 0.9333** | `7b24f31` | 两个父实验的行被合并时列错位：supplement 15 局 / ablation 7 局，却写成「有效 15、截尾 7」；实际 22 局 = 14 成功 + 4 机制失败 + 3 截尾 + 1 中断 | **错误**（列错位） | **14/21 = 0.6667**（有效分母，含 3 截尾）；排除截尾为 14/18 = 0.7778 |
| 11 | MAP-16 flash off "25 局**全部** `NODE_CAPACITY_CONFLICT`" | `7b24f31` | 实际 24 局 `NODE_CAPACITY_CONFLICT` + 1 局 `SIDING_CAPACITY_CONFLICT` | **表述错误**（同一机制族） | 24 + 1（同为会车/侧线容量冲突） |
| 12 | Memory 每成功局 **¥0.283 → ¥0.059** | `6563bea` | `0.059 = 0.47238868 / 8`，用的是 on 19 局的快照成本 | **历史子集** | **¥0.2825 → ¥0.0952**（on 28 局）；seed 2 单独看为 ¥0.0130 |
| 13 | `unknown_spend` **×3** | `66e1bb0` §5 | 实际 4 局（逐局见 `live-manifest.json`） | **错误**（表未随后续一轮更新） | **4 局** |
| 14 | 执行总量 **227 局** | `6563bea` | 第 6 轮补充后的快照 | **历史子集** | **308 局** |
| 15 | 执行总量 **265 局** | `675a5b0` | 第 8 轮补充后的快照 | **历史子集** | **308 局** |

结论：**15 项里 1 项是真错误导致的计数（#5）、2 项是表述/口径错误（#10/#11）、
1 项是未回写（#13）、其余是历史快照或明确的子集口径**。所有最终值现在都由
`live-results.json` / `live-manifest.json` 唯一决定。

## 3. 4 局 Provider 中断（DCR-V14-11 的受影响范围）

| run_id | 组 | 地图 / seed | 错误 | 修复前被算成 | 修复后 |
|---|---|---|---|---|---|
| `web-20261027T121544Z-c91eeed2` | E2-a on | MAP-16 / 1 | `InternalServerError` | 机制失败 + 计入分母 | 中断（不进分母） |
| `web-20261027T140448Z-4bbae2af` | E1-a off | MAP-22 / 2 | `APITimeoutError` | 机制失败 + 计入分母 | 中断 |
| `web-20261028T010040Z-1a8d134d` | E3 trigger_only | MAP-16 / 1 | `APIConnectionError` | 机制失败 + 计入分母 | 中断 |
| `web-20261028T071123Z-f0adc103` | E3 trigger_only | MAP-22 / 2 | `InternalServerError` | 机制失败 + 计入分母 | 中断 |

受影响的数字（修复前 → 修复后，均为"成功/有效"）：

| 组 | 修复前 | 修复后 |
|---|---|---|
| E1-a off @150 | 2/26 = 0.0769 | **2/25 = 0.0800** |
| E2-a on（全组） | 39/61 = 0.6393 | **39/60 = 0.6500** |
| E2-a MAP-16 flash on | 14/22 = 0.6364 | **14/21 = 0.6667** |
| E3 trigger_only @150 | 16/39 = 0.4103 | **16/38 = 0.4211** |
| E3 trigger_only seed 2 | 16/36 = 0.4444 | **16/35 = 0.4571** |

方向与结论**没有变化**：E3 仍是 Fisher p = 1.0（16/35 vs 15/33），
planning 仍是 p < 1e-6 量级的描述性收益。

## 4. 统计范围（写结论时必须一起写）

1. 308 局 = E1-a 83 + E2-a 125 + E3 100；43 个父实验；10 034 请求；¥5.55809328。
2. 每个条件最多 3 个环境 seed（E3 正式对照只有 1 个 seed），重复只是**模型采样波动**。
3. 采样参数未登记（`SamplingProvenance.support = UNKNOWN`）→ 全部配对 `DESCRIPTIVE_ONLY`，
   本文所有数字都是**描述性**，不作显著性/因果断言。
4. `on-we1`（写入频率）与 E3 的 MAP-16 探针是**独立单因子**，不并入 on/off 配对。
5. 外部账单未提供 → 金额只按登记价目表，`BLOCKED_EXTERNAL`。
