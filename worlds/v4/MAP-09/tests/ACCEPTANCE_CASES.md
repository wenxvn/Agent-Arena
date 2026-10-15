# MAP-09 Phase 1 测试用例草案

以下为环境实现后待执行的规则测试。

1. Reset：E/P/O/C 四舱、E-C 应急廊、battery5、P5/E3、oxygen12、主线断开、供氧关闭。
2. E-P 闸开时每 tick P→E 转1水；E=4安全，E=5短路。闸关闭动作提交后本 tick 不再漏水。
3. `mode=preserve` 关闭闸但 P 可达；`mode=sacrifice` 关闭闸并永久标记 P 不可达；E-C emergency 始终可用。
4. 每个 `pump_once` 从 P 最多抽2并耗1电；两次从5到1，三次从5到0且比必需量多耗一格。
5. 主线修复要求 location E、E水≤4；恢复外部发电但不回充电池。
6. 供氧关闭每 tick -1；到0失败。O 的重启需 generator online；补氧只在供氧开启时重置为12。
7. 电池正好3、氧稳定2 tick时可发送；电池2或稳定1时不能完成完整包。
8. 发报启动扣3电，必须连续2 tick维持供氧；中途支持关闭不能给 `packet_complete`。
9. 电量不足3的发报校验耗1 tick后以 `INSUFFICIENT_TRANSMIT_POWER` 终止，期间不扣电；成功传输仍连续耗2 tick。
10. 重放 `preserve_and_pump` 和 `sacrifice_P`，逐步水量/电量/氧状态和终止 tick与手写轨迹一致。
11. F01/F02/F03 首个失败原因依次为 `SHORT_CIRCUIT`、`INSUFFICIENT_TRANSMIT_POWER`、`OXYGEN_DEPLETED`。
