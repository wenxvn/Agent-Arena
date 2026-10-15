# 2026-10-15 文件与工作流审核

## 范围与结论

审核基线为 `3b19573`，起始有 356 个 Git 跟踪文件，以及用户已有的两份未跟踪 V1/V2 提纲。核查目录归属、规则与阶段状态、配置格式、项目正文链接、完全相同的文件、CI 和质量门禁。代码行为由现有全量检查验证，本次没有逐行复审所有算法，也没有验证真实模型服务。

| 类别 | 审核与处理 |
|---|---|
| 源码、测试、prompt、世界定义 | 保留。Ruff、mypy 和全量测试通过，无为整理而重写规则 |
| 项目入口与研究摘要 | 精简 AGENTS 的重复流程，修正版本化 Action contract 表述；摘要区分配置覆盖与实际尝试 |
| Scope 与 spec | spec 0017 已 Accepted，Scope 第 19 项同步 done；早期清单明确历史属性，S2 研究 Gate 保持未通过 |
| 历史诊断和研究报告 | current-issues 增加当前入口；修复 3 个 spec 链接，3 个缺失结果改为注明缺失状态的历史路径 |
| WORKFLOW 与 Skill | 新增统一 workflow 和 Skill 索引。保留 9 个 Skill 的 70 份执行指南、模式与模板，避免破坏相对引用 |
| CI | 保留既有 Actions 版本，增加只读权限、同分支重复运行取消、15 分钟超时、锁文件检查和中文步骤名 |
| 测试偏好与锁文件 | `test-preferences.json` 有 Skill 消费者，保留；依赖与 lock 不改 |
| 占位文件 | 删除空的 `prompts/.gitkeep`，目录已有 6 个真实 prompt，无需占位 |
| 本机配置、环境、实验产物与缓存 | 保留 `.env`、虚拟环境、runs/results/logs 和缓存，继续忽略，不打印密钥，不删除账本或中断证据 |
| 用户未提交提纲 | V1/V2 原样保留，不纳入本次提交；V3 原始提纲也未修改 |

## 实际验证

- `.venv/Scripts/python.exe -m pytest -q`：466 passed，7.77 秒。
- `.venv/Scripts/python.exe -m ruff check .`：通过。
- `.venv/Scripts/python.exe -m mypy src`：64 个源文件通过。
- JSON 解析 51 份、CSV 列数检查 10 份、TOML/lock 解析 2 份，通过。
- 项目 Markdown 正文和新增两个入口的相对文件链接检查通过；不检查远端 URL、标题锚点或通用 Skill 模板中的占位路径。
- 跟踪文件 SHA-256 完全重复检查未发现重复文件。这个检查不判断语义近似；不同用途的摘要与完整蓝图保留。
- `git diff --check`：通过。
- 当前 shell 无 `uv` 命令，虚拟环境也无 uv 模块，未运行 `uv lock --check`；TOML 解析不能替代依赖一致性检查。新增 CI 的远端执行结果另行核实，不把本地通过记为 Actions 通过。

起初 GitHub 专用代理指向不可用的本地端口，fetch 失败。仅对当前命令清除代理环境并覆盖 GitHub 专用 proxy 后，fetch 成功，基线与 origin/main 无领先或落后；未修改全局配置。

V1 提纲 SHA-256：`ebdec2e85acc298f52e804df87deb8da171a7252a6437333be45c9813d5f4112`。

V2 提纲 SHA-256：`86e41d2f2bbac568b350903bc78d67e09993a1ad9ddb0a27764b1aabb72a4e70`。

## 同步与后续

按项目 `/sync` 核对 AGENTS、Scope、spec 0017 与本次 diff。仅同步 V3 离线交付状态，没有新架构决策、spec 内容修改或模型收益结论。删除占位文件不产生上下文孤儿。工作流整理根据本次用户授权执行。

V2 继续停在 S2，三份账本保持关闭；没有 Provider 请求、GPU 任务、预算重置或新实验。缺失的历史结果文件需要原始备份才能恢复，本次没有制造替代结果。

交付入口为 [工作流](../workflow.md) 和 [Skill 索引](../../skills/README.md)。提交身份可通过 `git log -1 -- docs/maintenance/2026-10-15-file-audit.md` 查询。
