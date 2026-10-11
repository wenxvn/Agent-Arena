# V1 研究总表（SUMMARY）

> 代码：`main@4b3261b` 起，至本轮在线收官。模型实验：C011 6 尝试、React-C111 7 尝试、
> C010 5 局、E1 6 局、Pctx 6 尝试、SeedSmoke 3 局，合计 33 次尝试。
> 状态：`done`=已验证交付，`partial`=审计/设计完成、在线部分有明确决策（deferred 属合法终态）。

| Task | 状态 | 实际完成内容 | 关键证据/统计 | 测试与 CI | commit | 遗留问题 |
|---|---|---|---|---|---|---|
| T1 | done | F401 修复；51→45 去重台账；provenance 审计；4 离线测试+台账脚本 | 原始 46/51=90.2%，去重 45/45；本地 249 passed（含并行会话 56 项） | 新测试全过；CI 全绿待 push 后确认 | `f1e441a` | 本机无 uv/ruff/mypy，CI 链接缺 |
| T2 | done | 9 配置统计复核；Success@K 离线裁剪；TOP3 瓶颈 + step 引用 | K=60:60%、K=100:80%；B1 重读53次/B2 误用68 hits/B3 look簇 | `test_success_at_k` 通过；可重算 | `24f3851` | 阶段精确分解待全量 analyze-traces |
| T3 | done | 八格 8/8（C010/C011 新跑 0/5）；React-C111 0/4；Phase 定级测试锁定 | H 必要、M 增益（FORGOTTEN_FACT 双分离）、R 仅放大器 | 3 审计测试 +33 次在线尝试 | `050a31a` `abafbe6` `a0166b3` | n=5，只报效应 |
| T4 | done | E1 单变量 5/5 有效保留；E2/E3 隔离 deferred | E1 5/5 均值 30.6 零误用 vs C111 3/5 均值 47.2，配对全优 | 诚实性契约通过；在线 6 局 | `15834c2` `5cb869e` | E1 只在飞船 v1 验证 |
| T5 | done | P-v1-context 0/4；不提议 Planning v2 | planning 更差（0/4，2 倍 token）；子目标完成≠逃生 | 在线 6 尝试；0/5 合法交付 | `c733c45` | planning 系 prompt 无 E1 规则（已披露） |
| T6 | partial | seeded-v5 生成器 + oracle 测试 + 真实 3/3；新任务族仍设计 | 2 新布局一次通过；按 hash 分面（aggregates=null 验证警告） | `test_seeded_world` 9 项通过 | `ac9da24` | 跨任务泛化未实施；码值未随机（已披露） |
| T7 | partial | Reflection deferred（决策句）；UI 只读 MVP 实现+冒烟 | 高频第二调用零完成；E1-vs-C111 回放 1.0 vs 0.6 | UI 7 项测试通过；部署走 --with | `7286a69` | streamlit 未进 lock（设计如此）；Reflection 无收益证据 |

## CI 是否全绿

本地 pytest 全绿（249 passed，含并行会话新增 7 世界 56 项）；Ruff/mypy 本机缺装，CI 全绿待 push 后 GitHub Actions `quality` 链接确认。红灯根因（单行 F401）早已修复。

## 45/45 口径

- 去重后 45 组合全 success（每组合至少一次成功）。
- 原始尝试 46 success + 5 provider_error = 51 文件，端到端 90.2%。
- “6 次网关异常”缺 1 件源文件（abyss-easy 双 success 非网关错误），已修正记述，不补数字。
- 本轮新增 33 次尝试全部单列记账（见 `00` §6），未并入 45/45 分母。

## 离线 Success@K 与瓶颈

- 总体 K=30/60/100/150/200：15.6%/60.0%/80.0%/88.9%/93.3%；飞船最敏感（K=60 仅 26.7%）。
- TOP3：B1 重复读码+读码后空转（强）> B2 终点工具误用（强，灯塔）> B3 look 簇空转（中）。
- E1 已把 B1/B2 在飞船 v1 上消除（5 局零误用、读码 ≤2 次）。

## 消融最终结论（可信度）

- H 必要（无 H 四格全 0/5）——高；M 增益（FORGOTTEN_FACT 双分离，0/4 vs 3/5）——中高；
  R 仅放大器（R-only 与 R+P 全 0/5，C101 1/5→C111 3/5）——中高；P = world-declared guidance——高。
- E1（通用 tool 语义）5/5 vs 3/5，配对 5 格全优，token −35%/−50%——中高（n=5，同模型，跨日对照已声明）。
- Planning + 同上下文更差（0/4，2 倍成本），不做 v2——中高。

## Planning/Reflection/泛化

- Planning：更差，不是更好，也不是证据不足（公平对照完成）。
- Reflection：deferred（E1 成功后必要性更弱；第二调用零完成率已证无效）。
- 随机化：同任务结构实例迁移 3/3（2 新布局）；跨任务结构未做。

## 并行会话说明（2026-10-11 晚）

- 另一并行会话新增 7 世界 21 图（spec 0011，commit `e8da39d`），与本轮工作兼容：
  全套 249 passed，我的 seeded 注册、E1 prompt、UI 文件均完好。本轮 V1 提纲执行范围
  仍为原三世界（提纲冻结时的范围）， conclusions 不自动外推到 7 新世界；
  E1/C111 等结论在新世界的复验为明确下一步（未做，不假装已做）。

## 未做/失败/证据不足明示

- 未做：E2/E3（deferred，有证据的决策）、跨任务泛化、新世界复验、Planning v2（证据为负）。
- 失败：Pctx seed 4 两次基础设施中断（并行争用）+ 一次首步 provider_error→censored；
  React-C111 seed 4 两次 provider_error→censored；C011 seed 1 一次 provider_error→重跑失败。
- 证据不足：一切 n=5 结论均只报效应不报显著性；C111 为跨日历史对照（已声明）。
- 未重跑已有完整实验；未伪造表格；未假定正向结果。
