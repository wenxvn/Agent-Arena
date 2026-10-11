# V1 研究总表（SUMMARY）

> 代码：`main@4b3261b` + T1 单行修复 + 4 个离线契约测试 + 1 台账脚本。模型实验 0 次新增调用。
> 状态：`done`=已验证交付，`partial`=审计/设计完成、在线部分阻塞，`blocked`=暂不可做（含恢复条件）。

| Task | 状态 | 实际完成内容 | 关键证据/统计 | 测试与 CI | commit | 遗留问题 |
|---|---|---|---|---|---|---|
| T1 | partial | F401 修复；51→45 去重台账；provenance 审计；4 离线测试+台账脚本 | 原始 46/51=90.2%，去重 45/45；本地 pytest 159 passed | 新测试待跑；CI 全绿待 push 后确认 | 待提交 | 本机无 uv/ruff/mypy（Python 3.11），CI 链接缺 |
| T2 | done（离线） | 9 配置统计复核；Success@K 离线裁剪；TOP3 瓶颈 + step 引用 | K=60:60%、K=100:80%；B1 重读53次/B2 误用68 hits/B3 look簇 | `test_success_at_k` 待跑；`analyze-traces` 可重算 | 待提交 | 阶段精确分解需全量 analyze-traces CSV |
| T3 | partial | H/R/P 实现审计；Phase 先验定级；八格矩阵（6/8 格已有，缺 C010/C011）；M 消融缺口 | C101 1/5 vs C111 3/5；P 含物品名+阶段顺序（测试锁定） | `test_phase_prior_audit` 待跑；补测 0 局 blocked | 待提交 | C011 + React-C111 未跑（需预算登记） |
| T4 | partial | 三类错误分类 + step 引用；E1/E2/E3 插入点与排序；离线契约测试 | E1>E3>E2；灯塔 lamp_console 缺定义 verified | `test_terminal_contract` 待跑；在线对照 not run | 待提交 | E1 未实施；E2 需新 world version |
| T5 | partial | qwen/Muse 旧失败复核；透传等价+prompt分叉；P-v1-context 设计 + G1 | 双输基线可比；与获胜组不可比；无偷读 | 无新测试；在线对照 not run | 待提交 | 需 T3 冻结机制 + 预算 |
| T6 | partial | seed=replicate 审计；版本机制；随机化+新任务族设计 | seed 只存档（3 处行号）；旧图锁定 | `test_seed_replicate` 待跑；生成器 not run | 待提交 | 生成器/冒烟需新 spec |
| T7 | partial | Reflection deferred 决策句；UI 只读 MVP 设计 + 契约清单 | 高频第二调用零完成；三档标记要求 | 无新测试；实现 not run | 待提交 | 待 E1/E3 与 Planning 对照后重估 |

## CI 是否全绿

否。本地 pytest 159 passed（Python 3.11 + `PYTHONPATH=src`）；Ruff/mypy/uv 本机缺装，CI 全绿待 push 后 GitHub Actions `quality` 链接确认。红灯根因（单行 F401）已修。

## 45/45 口径

- 去重后 45 组合全 success（每组合至少一次成功）。
- 原始尝试 46 success + 5 provider_error = 51 文件，端到端 90.2%。
- “6 次网关异常”缺 1 件源文件（abyss-easy 双 success 非网关错误），已修正记述，不补数字。

## 离线 Success@K 与瓶颈

- 总体 K=30/60/100/150/200：15.6%/60.0%/80.0%/88.9%/93.3%；飞船最敏感（K=60 仅 26.7%）。
- TOP3：B1 重复读码+读码后空转（强）> B2 终点工具误用（强，灯塔）> B3 look 簇空转（中）。

## 消融最有价值结论（可信度）

- P 必须与 H 联动（C101 1/5 vs 单变量全 0/5），R 疑似放大器（C111−C101=2/5）——可信度中（缺 C011，不可判交互）。
- P = world-declared guidance（含物品名+阶段顺序），主成绩不得称纯自主——可信度高（代码+测试锁定）。
- 预算独立效应大（B30 0/5 → B60 3/5 → unlimited 45/45）——可信度高；跨预算差值不得当架构收益。

## Planning/Reflection/泛化

- Planning：与 Memory 双输基线可比，失败主因 grounding；P-v1-context 设计完成，未跑。更好/更差：**证据不足**。
- Reflection：deferred（见决策句），无必要性证据。
- 随机化/跨任务：审计+设计完成，seed=replicate 已测试锁定；生成器与评测未做。

## 未做/失败/证据不足明示

- 未做：一切新模型在线对照（T3 补测、T4 E1 在线、T5 上下文对照、T6 新实例评测、T7 实现）。
- 失败：CI 全绿未确认；`1a95834e` Planning 整批 provider_error 作废。
- 证据不足：M 主效应、P 内部分量、Planning 是否受益于同上下文、Reflection 收益。
- 未重跑已有完整实验；未伪造表格；未假定正向结果。
