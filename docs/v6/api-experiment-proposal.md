# V6 可选真实 API 复测方案（已执行一次）

> **状态：已执行（2026-10-16，一次）。** 用户授权使用 MiMo API 后，在冻结离线门禁下完成 24 局矩阵，费用 CNY ¥0.17891580，结果见 [`pilot-report.md`](pilot-report.md)。本文件保留为协议与预算记录；**再次执行仍需新的离线门禁与预算登记**。

## 1. 目标

用真实模型验证 V6 的测量效度：先确认各层实例能产生**非退化的合法动作与指标**（不是 0% 或 100% 天花板/地板），再比较预登记的能力机制。**不以提高通过率为目标。**

## 2. 前置条件（全部满足才可申请）

1. V6 离线门禁通过（本仓库当前已通过，见 `validation-report.md`）。
2. 所有实例完成人工审阅，`review_status` 由审阅者填写。
3. 新建**独立 V6 ledger/registry 命名空间**（如 `runs/v6/ledger/`），不改动 V5 账本与 `runs/v5/pilot_registry.json`。
4. 冻结 V6 prompt 哈希、`scenario_hash`、求解器输出、runtime commit。

## 3. 模型与计费

| 项 | 值 |
|---|---|
| Provider / endpoint | Xiaomi MiMo OpenAI-compatible（本机 `.env` 配置，不写密钥） |
| Model | `mimo-v2.6-flash` |
| 计费来源 | [MiMo-V2.6-Flash 官方价格页](https://mimo.mi.com/models/zh-CN/mimo-v2.6-flash)；核验时间 2026-10-16 |
| 币种 | 必须显式选择 CNY 或 USD，不换算不叠加 |
| 价格 | CNY 缓存 ¥0.02/M、未缓存 ¥1/M、输出 ¥2/M；USD 缓存 $0.0028/M、未缓存 $0.14/M、输出 $0.28/M |
| 硬预算 | **待用户批准**（建议先申请小规模 smoke 预算，批准后再申请矩阵预算） |

## 4. 固定协议

- temperature 0；reasoning 关闭；输出严格校验；每次最多 8,192 输入 token、1,024 输出 token。
- 每局最多 100 决策、1 次恢复重试、101 次请求尝试；单局 12 分钟；全局 provider 墙钟 240 分钟。
- unknown spend、连续两次 provider 错误、全局预算/请求/token 上限耗尽 → fail closed 并停止。
- prompt 与规则 hash、runner commit、离线 gate hash、新 V6 ledger 路径全部记入 manifest。

## 5. 建议 episode 清单（先 smoke 后矩阵）

1. **Smoke（≤6 局）**：每图 L1 一个实例 × 主条件 × seed 0，验证接口非退化（能产生合法动作与专属指标，且不同条件的公开观察按设计一致）。
2. **矩阵 A（P0 三图）**：MAP-16/18/22 的 L1 与 L2、每实例两条件、每条件 N 次运行，先小 N。
3. **矩阵 B（P1 三图）**：MAP-08 四实例、MAP-26 四故障+一恢复、MAP-30 三案情，按实例配对。
4. L3 只在 L1/L2 显示非退化后追加。

停止规则：若某图所有条件都 0% 或都 100%，暂停该图并报告天花板/地板效应，不扩大矩阵。截尾（步数/动作/墙钟）单独计数，不当作能力失败。

## 6. 预注册指标与删失

逐图主指标见 `measurement-matrix.md`；报告逐实例、逐条件、逐运行的原始计数与配对差。实例不足时不做显著性断言。

## 7. 需要新增的工程件（本提案未实现）

- V6 付费 runner（可复用 V5 runner 的生命周期与账本机制，但需独立命名空间与 V6 prompt/scene 适配）。
- V6 离线门禁（复用 `offline_gate` 思路，绑定 V6 源哈希）。
- V6 预算账本与 registry。

## 8. 授权请求

请用户明确回复：是否批准启动、批准币种、smoke 预算上界、矩阵预算上界。在此之前不执行任何付费调用。
