# V5 六图能力测量 pilot

此目录记录隔离 `scenario_v4` 运行时、离线验收、MiMo pilot、能力效度边界和其余 24 张地图的接入条件。目标是检验测量是否可重复、可归因，不把一次通关或 Oracle 回放当成能力结论。2026-10-16 第二次登记 pilot 完成 39/39 局（15/39 成功，报告费用 ¥0.24287288，0 unknown spend）；逐图 3-seed 结果见 [pilot-report](pilot-report.md)。

## 范围与数据

- 地图：MAP-08、MAP-16、MAP-18、MAP-22、MAP-26、MAP-30。
- 预登记矩阵：39 局，每张图最多三个 seed 标签；MAP-30 含完整历史/最近 5 步/最近 5 步加案卷三条件；六局 seed 0 smoke 是矩阵内 episode，不另增局数。
- Provider/model：本机 `openai` Responses API 配置中的 `mimo-v2.6-flash`，temperature 0，reasoning `none`，JSON object transport；每个 Action 仍由本地严格 V4 schema 校验。
- 原始运行、公开 trace、私有裁判指标与追加账本只写入被忽略的 `runs/v5/`；不要把这些生成物加入 Git。
- MiMo 费用以 [官方模型页](https://mimo.mi.com/models/zh-CN/mimo-v2.6-flash) 的当前缓存/未缓存输入与输出费率计算。提纲命令中的 2 美元是示例值，不是本 pilot 的预算。

## 可复制命令

默认命令先打印上限并执行六局 Fake provider 协议 dry-run；不读取 `.env`、不发 API 请求，临时文件自动清除：

```powershell
.\.venv\Scripts\python.exe scripts\run_v5_pilot.py --dry-run
```

离线 gate 必须先在提交后的冻结代码上完整通过：

```powershell
.\.venv\Scripts\python.exe scripts\freeze_v5_offline_gate.py
```

真实 pilot 需要显式选择账单币种。当前按本机 China 账单口径使用 CNY：

```powershell
.\.venv\Scripts\python.exe scripts\run_v5_pilot.py --execute-paid --billing-currency CNY
```

该命令自动完成 Stage B 六局 smoke；只有所有 usage、trace、judge metrics、manifest、来源 hash 与 V5 账本通过核对后，才进入其余 33 局。中断后只能使用同一 `run_manifest.json` 中记录的 `run_dir` 和 `ledger_path`，显式续跑：

```powershell
.\.venv\Scripts\python.exe scripts\run_v5_pilot.py `
  --execute-paid --billing-currency CNY --resume `
  --run-dir runs\v5\experiments\<原 run 目录> `
  --ledger runs\v5\ledgers\<原 ledger 文件>
```

每次调用都先校验 offline gate 与 Git HEAD；源文件、prompt、condition、map 设计材料、测试或 provider 适配发生变化时，必须重新完成冻结验证。`runs/v5/pilot_registry.json` 只允许一个活跃 run/ledger；关闭、完成或 unknown spend 后不能续跑或新建 successor。若要再次运行，须经用户授权、归档旧 registry、在提交 HEAD 重新冻结 gate 并登记新的 pilot（2026-10-16 第二次登记即此流程）。用户授权的封账后诊断请求不计入登记的 39 局。

## 文件

- [运行契约](runtime-contract.md)：环境、Action、Agent 可见 trace、checkpoint、预算与恢复约定。
- [离线验收记录](validation-report.md)：实际执行的回归、Oracle、独立求解与 gate 结果。
- [Pilot 结果](pilot-report.md)：Stage B/C episode、usage、费用和停止原因。
- [效度边界](capability-validity.md)：哪些观察可以解释成能力证据及样本限制。
- [其余 24 图](next-24-maps.md)：后续接入 gate 和禁止的推断。
- [设计差异](design-discrepancies.md)：MAP-22 原 Oracle 预载图记忆的问题及 V5 合法前缀。
