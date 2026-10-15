# 项目 Skill 索引

项目工作流见 [docs/workflow.md](../docs/workflow.md)。本目录保存 9 个 Skill 及其按需加载的模式、模板和写作指南，不是需要全部串行执行的检查清单。

| 入口 | 用途 | 主要产物 |
|---|---|---|
| [scope](scope/SKILL.md) | 里程碑、优先级和交付拆分 | `docs/scope/` |
| [architect](architect/SKILL.md) | 技术决策、更新或替代设计 | `docs/specs/` |
| [audit](audit/SKILL.md) | 核查工程上下文和区域约定 | 根目录与局部 `AGENTS.md` |
| [develop](develop/SKILL.md) | 实现已确认设计 | 代码与构建进度 |
| [debug](debug/SKILL.md) | 复现、定位和修复异常 | 最小修复与验证证据 |
| [test](test/SKILL.md) | 为行为变化补回归与边界测试 | 测试、`test-preferences.json` |
| [check verify](check/SKILL.md) | 验证 spec 的行为验收 | 验收证据 |
| [check review](check/SKILL.md) | 独立审查重要改动 | 按优先级排列的发现 |
| [document](document/SKILL.md) | 根据真实 commit/diff 写交付文档 | PR、changelog、复盘 |
| [sync](sync/SKILL.md) | 协调当前改动与持久状态 | 上下文、Scope、spec 状态 |

`check` 有两种模式，合计仍为 9 个 Skill。先读对应 `SKILL.md`，再读其要求的单个模式与模板，不预载整个目录。不支持 slash command 的客户端直接读取文件并执行相同流程，不要求额外安装。

## 本项目适配

- 面向用户的产物和沟通使用中文。模板中的 English 字段、代码、路径和标准术语可以保留。
- 根目录 AGENTS、已确认 spec、用户当前授权与实验门禁优先于通用模板。已授权的维护不重复询问；需要新的实验授权时仍须等待。
- Python 3.13、uv、pytest、Ruff、mypy 是既定工具。测试偏好保存在根目录 `test-preferences.json`，不要重新选择框架或增加无关依赖。
- 文档整理只做相称验证，不机械补代码测试。代码与 CI 改动使用项目质量门禁。
- Skill 中的 POSIX 命令是参考，Windows 下使用 PowerShell 或 Python 的等价操作。不要复制不能运行的 shell 组合。
- 子任务仅在用户或实际执行的 Skill 明确要求时委派。无可用子 Agent 时按其回退方式在当前会话完成，并说明审查独立性的限制。
- 不把 Scope 的 `done` 推广为研究成功。离线 fixture、Fake 和公开 Oracle 均不证明真实模型收益。

模板与辅助文件按各自引用保留；本次未迁移 Skill 目录，避免破坏相对路径和客户端入口。
