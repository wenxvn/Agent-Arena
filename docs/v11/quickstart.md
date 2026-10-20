# V11 快速开始（Windows / macOS / Linux）

## 0. 前置条件

- Python **3.13**（`pyproject.toml` 要求 `>=3.13,<3.14`）
- [uv](https://docs.astral.sh/uv/)
- Git
- 现代浏览器（Chrome / Edge / Firefox / Safari）

不需要 Docker、数据库或 Node.js。默认只监听 `127.0.0.1`。

## 1. 安装

### Windows PowerShell

```powershell
git clone https://github.com/wenxvn/Agent-Arena.git
cd Agent-Arena
uv sync --extra web
```

### macOS / Linux

```bash
git clone https://github.com/wenxvn/Agent-Arena.git
cd Agent-Arena
uv sync --extra web
```

## 2. 启动网页（推荐命令）

```bash
uv run agent-arena web
```

打开 <http://127.0.0.1:8501>。

- `streamlit` 通过可选依赖组 `web` 锁定在 `uv.lock` 中；不写入核心依赖；
- 未安装可选依赖时可用 `uv run --with streamlit agent-arena web` 临时启动；
- 默认地址 `127.0.0.1`，端口 `8501`；
- 不想自动打开浏览器可加 `--headless`；
- 换端口：`--port 8600`。

### 辅助脚本

Windows：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/launch_web.ps1
```

macOS / Linux：

```bash
chmod +x scripts/launch_web.sh
./scripts/launch_web.sh
```

## 3. 零密钥离线演示

1. 首页点击“离线演示：MAP-01 · 破损的曙光号（seed 0）”；
2. 自动跳到“运行监控”，看到动作时间线；
3. 结束后到“结果与回放”，查看指标五态、逐步回放和导出按钮。

离线演示使用**公开规则策略**，不是模型挑战，不发送任何网络请求。页面与结果元数据都会标注 `public_heuristic_policy`。

## 4. 一键自检

```bash
uv run python scripts/verify_v11.py
```

或：

```bash
uv run agent-arena web --check
```

自检覆盖：30 图 catalog、30 图离线运行/回放/导出、预算门禁、脱敏、路径限制、崩溃恢复、导出字段一致性。全量测试是独立门禁：

```bash
uv run ruff check .
uv run mypy src
uv run pytest -q
uv run uv lock --check
git diff --check
```

## 5. 接入真实模型（可选）

1. 复制配置模板：

   ```bash
   cp .env.example .env        # macOS / Linux
   Copy-Item .env.example .env # Windows PowerShell
   ```

2. 在 `.env` 填写：

   ```dotenv
   AGENT_ARENA_PROVIDER=openai
   OPENAI_API_KEY=你的密钥
   OPENAI_BASE_URL=https://api.xiaomimimo.com/v1
   OPENAI_MODEL=mimo-v2.6-flash
   ```

   `.env` 已在 `.gitignore` 中，不要提交。

3. 重启网页，在“设置与帮助”看到密钥状态为“已配置”；
4. 到“挑战配置”，切换到“真实模型挑战”，确认费用提示后开始。

真实模式默认单局请求 60、决策 30–80（按地图）、费用上限 ¥1.00；只有 MiMo 有登记价时可执行金额硬门禁。

## 6. 常见问题

| 现象 | 处理 |
|---|---|
| `uv: command not found` | 安装 uv 后重开终端 |
| `未安装 streamlit` | 运行 `uv sync --extra web`；临时可用 `uv run --with streamlit agent-arena web` |
| 网页打不开 | 确认命令窗口未退出；访问 `http://127.0.0.1:8501` |
| 端口占用 | `agent-arena web --port 8600` |
| 密钥未配置 | 编辑本机 `.env`，不要写入源码或网页 |
| 连接失败/限流 | 检查 Base URL/模型/额度；V11 不自动重试 |
| 未知消费 | 运行会 fail-closed 停止；检查 `runs/web/_ledger/` |
| Windows 文件占用 | 服务层已重试；关闭杀毒软件对 `runs/web` 的实时扫描 |
| 想重置历史 | 删除 `runs/web/`；不要删除 `runs/v8`、`runs/v9`、`runs/v10` |

## 7. 数据位置

- 网页运行：`runs/web/<run_id>/`（manifest.json、events.jsonl、result.json）
- 全局账本：`runs/web/_ledger/web_ledger.jsonl`
- 自检报告：`runs/v11/selfcheck.json`
- 历史研究：`runs/v8/`、`runs/v9/`、`runs/v10/`（只读，不清理）
