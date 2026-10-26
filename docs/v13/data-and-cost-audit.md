# 本地账本与费用审计

- 账本文件：`D:\wenxvn(2)\Agent-Arena\runs\web\_ledger\web_ledger.jsonl`（只读）
- 条目：318（started 159 / settled 159）
- 请求：5641；输入 token：7553387；输出 token：177416
- 已结算：CNY 5.43680012
- 未知消费局：0
- 父实验：22（live 20 / simulated 2）；子局链接：163（live 159）

## 发现的问题

- 未发现结构性问题（不等于后台账单已核对）。

## 外部账单对账

- 状态：`NO_EXTERNAL_BILL_PROVIDED`
- 说明：未提供 Provider 后台账单：本地账本只与登记的价目表对账，不代表后台金额已核对。

## 口径

- 未知消费的局不并入已结算金额；
- 历史账本条目一条都不修改，发现差异只生成记录；
- 没有后台账单时必须保留 `NOT_RECONCILED_EXTERNAL`。
