# 数据与费用审计（P2-6）

- 代码：`src/agent_arena/lab/v13/ledger.py`、`scripts/audit_v13_ledger.py`
- 数据来源：本机 `runs/web/_ledger/web_ledger.jsonl`（**只读**）
- 本轮新增真实付费请求：**0**

> 本文件只做**本地账本一致性**核验。**没有** Provider 后台账单，
> 因此外部对账状态是 `NO_EXTERNAL_BILL_PROVIDED`——不得写成"后台已核对"。

## 1. 本地账本一致性（V12 历史，只读）

| 检查项 | 结果 |
|---|---|
| 账本条目 | 318（started 159 + settled 159） |
| `run_started` / `run_settled` 配对 | **159 / 159**，无孤儿 |
| 重复结算（同一 run 多条 settled） | **0** |
| usage 负值 | **0** |
| 未知消费局（`cost_unknown`） | **0** |
| 请求总数 | **5 641** |
| 已结算总额 | **CNY 5.43680012** |
| 父实验 / 子局链接 | 22 / 163（V12 汇总表为 20 个实验；差异见下） |
| 子局链接指向不存在的 run 目录 | **0** |

**结论**：本地账本自洽，与 V12 文档公布的 `159 局 / 5 641 请求 / ¥5.43680012`
**逐项一致**。

### 父实验 22 vs 20 的差异

V12 汇总表列了 20 个实验，本机 `runs/lab/` 有 22 个父实验目录。差异来自：

1. 一个"探针"实验（3 请求、¥0.00026128），V12 明确写了"不参与分析"；
2. 一个早前的补充实验，其子局被并入其它汇总行。

两者都在 `docs/v12/mimo-results.md` 有记录，**不是未登记的实验**。

## 2. 按模式拆分（V13 新增）

| 模式 | 父实验 | 子局链接 |
|---|---:|---:|
| `live`（真实付费） | 22 | 163 |
| `simulated`（离线演示） | 0（V13 演示写在 `runs/v13/demo`，不进本目录） | 0 |

**为什么要拆**：V13 的离线演示也会产生父实验。如果混在一起，会让人误以为
真实实验变多了。`audit_ledger` 现在按父实验的 `mode` 分开计数。

## 3. 外部账单对账（`BLOCKED_EXTERNAL`）

| 项 | 状态 |
|---|---|
| 本地已结算 | CNY 5.43680012 |
| Provider 后台账单 | **未提供** |
| 对账状态 | `NO_EXTERNAL_BILL_PROVIDED` |
| 容差规则 | `max(¥0.0001, 0.5%)` |
| 币种/时区 | 币种必须一致；时间戳只做参考，不参与金额比对 |

**如何补上**（用户操作）：

1. 从 Provider 控制台导出脱敏 CSV（只保留 `run_id, amount, currency, settled_at`）；
2. 运行：

```bash
uv run python scripts/audit_v13_ledger.py --bill path/to/bill.csv --write
```

3. 若出现差异，会生成差额表（本地金额 / 账单金额 / 容差），
   并按 DCR 格式记录；**不修改**任何历史账本条目。

## 4. 对账接口的规则（为什么这样设计）

| 规则 | 原因 |
|---|---|
| 按 `run_id` 逐局对账，不按总额 | 总额相同也可能是"这局多、那局少" |
| 容差 `max(¥0.0001, 0.5%)` | Provider 常有极小舍入差；0.5% 覆盖已知的计价差异 |
| 币种必须一致 | 混币种直接 `NOT_RECONCILED` |
| 账单多出的 run / 本地多出的 run 都列出 | 静默丢弃会掩盖重复计费或漏记 |
| 未知消费局不并入已结算金额 | 否则总额会虚高或虚低 |
| 只读 | 任何差异只生成记录，不改账本 |

## 5. 负向场景（已测）

| 场景 | 行为 | 测试 |
|---|---|---|
| 只有 `run_started` 没有收尾 | 列入 `orphan_runs`，生成 issue | `test_audit_detects_orphan_and_duplicates` |
| 同一 run 两条 `run_settled` | 列入 `duplicate_settlements` | 同上 |
| `cost_unknown=true` | 列入 `unknown_spend_runs`，**不计入**已结算 | `test_audit_keeps_unknown_spend_out_of_settled_total` |
| 账单缺 `run_id`/`amount` 列 | `problems` 非空，返回 `NOT_RECONCILED_EXTERNAL` | `test_bill_csv_rejects_missing_columns` |
| 账单币种不是 CNY | `NOT_RECONCILED_EXTERNAL` | `test_reconcile_flags_amount_mismatch_and_currency` |
| 账单金额超容差 | 列出 mismatch（含 local/bill/tolerance） | 同上 |
| 损坏的 JSONL 行 | 跳过，不影响其它行 | `test_read_ledger_tolerates_broken_lines` |

## 6. 费用口径（与 V12 一致，未改）

- 单局费用 = `input_tokens × 输入单价 + output_tokens × 输出单价`（登记价目表）；
- 只有 MiMo 有登记价目；其它模型**不启用金额硬门禁**（预检会警告）；
- 未知 usage → `unknown_spend` → fail-closed，不重试；
- 取消/中断的局按已发生的 usage 结算，不补零。

## 7. 复算

```bash
uv run python scripts/audit_v13_ledger.py --write
# 输出 docs/v13/data-and-cost-audit.md / .json
```

JSON 里包含完整的 `unknown_spend_runs` / `orphan_runs` /
`duplicate_settlements` / `negative_usage` 列表，便于逐条回查。

## 8. 不支持的主张

- ❌ "后台账单已核对"——没有账单，状态是 `NO_EXTERNAL_BILL_PROVIDED`；
- ❌ "费用 100% 准确"——本地按登记价目与返回 usage 计算，未与 Provider 对账；
- ❌ "V13 花了钱"——本轮真实付费请求为 0。
