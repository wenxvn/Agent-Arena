# MAP-04 Phase 1 测试用例草案

这些是待环境实现后执行的规则用例，不是已运行的测试。

1. reset 为 phase 2；一次 `wait` 后为 3，phase 5 后再推进回 0。
2. `S-G` 和 `G-S` 在出发相位 0、1 接受；相位 2、3、4、5 拒绝。
3. 关闭边拒绝仍推进 tick 与 tide_phase，位置和背包保持不变，原因码为 `TIDE_WINDOW_CLOSED`。
4. 路径 `T-S-G-D` 中仅 S-G 受潮相影响；G-D 与五条绕行边在任一 phase 都开放。
5. 在 G 等 4 个 tick 不损失灯芯或生命状态，只推进相位。
6. 两条 oracle 分别在 tick14、tick15 点灯成功；逐步 phase 与 JSONL expected 相同。
7. 连续 wait 到 tick18 而灯未点亮，以 `RESCUE_SIGNAL_WINDOW_EXPIRED` 失败。
8. 重复读取 gauge 只返回当下 phase，不返回未来表；当前相位对所有 Agent 一致。
