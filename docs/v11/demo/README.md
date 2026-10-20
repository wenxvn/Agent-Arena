# V11 演示数据包

这里保存一局**离线公开规则策略**的完整运行记录，用于新用户在没有 API Key、也不想先跑一局时浏览历史、回放和导出。

- 地图：MAP-01 · 破损的曙光号
- 模式：离线演示（`public_heuristic_policy`，**不是模型挑战**）
- 结果：SUCCEEDED，15 步
- 内容：`manifest.json`、`events.jsonl`、`result.json`

安装到本机：

```bash
uv run python scripts/install_v11_demo.py
```

然后启动网页：

```bash
uv run agent-arena web
```

打开“历史与对照”或“结果与回放”即可看到该运行。`--force` 会覆盖同名运行；默认不覆盖。

这些记录不含 API Key、隐藏世界真值或完整内部 prompt。
