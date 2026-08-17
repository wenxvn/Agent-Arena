# Spaceship Escape 环境验证

## 自动验证

1. 运行 `uv run ruff check .`。
2. 运行 `uv run mypy src`。
3. 运行 `uv run pytest`。
4. 运行仅覆盖 Environment 的测试，确认 **AC-1** 至 **AC-9**。

## 手动验证

1. reset 后调用 `look`，确认初始位置为 `control_room`，且 Observation 不含内部标记。
2. 移动到 Storage Room，`look` 后只看到 `storage_crate`。
3. inspect crate，pickup screwdriver 和 replacement fuse。
4. 移动到 Maintenance Room，读取 diagnostic terminal。
5. 移动到 Reactor Room，打开 reactor panel，安装 replacement fuse。
6. 返回 Control Room，读取 `ALPHA-731`。
7. 移动到 Escape Pod，使用 `ALPHA-731`，确认 `is_success()` 为真。
8. 新建两个 seed 为 `0` 的环境，确认初始 Observation 和世界状态相同。

## 失败验证

1. 无电时读取 Control Room terminal，确认拒绝且主电源状态不变。
2. 未持有 screwdriver 时打开 panel，确认拒绝且 panel 保持关闭。
3. 未打开 panel 或未持有 replacement fuse 时修复，确认拒绝且主电源保持关闭。
4. 未读取授权码时启动 Escape Pod，确认拒绝且未逃生。
5. 在错误房间 pickup 或 inspect，确认拒绝、步数增加且状态不变。
