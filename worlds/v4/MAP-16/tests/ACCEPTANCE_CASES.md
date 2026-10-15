# MAP-16 运行时实现后验收用例

这些是未来环境用例；当前未实现运行时，不是pytest结果。

1. Reset seed0：a在A、目标B；b在B、目标A；列出A-X-M-Y-B与M-D全部公开容量。
2. `set_route`仅接受相邻节点；每列车每tick最多一个未决预约；`release_section`只能撤销本车当前tick未执行预约。预约与取消均不推进tick。
3. `move_train`前先检查预约冲突；任何不安全移动轮次都不改变列车位置或tick；合法原子结算才整体更新占位并推进tick一次。
4. F01两列车从X/Y预约到M，两个预约分别合法，提交时以 `NODE_CAPACITY_CONFLICT` 失败且双方仍在X/Y、tick仍为1。
5. F02处于a=X、b=M时反向申请XM，以 `HEAD_ON_SWAP` 失败，tick和位置保持不变。
6. F03处于a=D、b=M时b预约入D并提交，以 `SIDING_CAPACITY_CONFLICT` 失败，位置不变。
7. B01处于a=D、b=M时分别预约D→M、M→X；两段不同且末态唯一占M，应成功推进一tick。
8. F04依次让b走B→Y→M→X、让a留在A；最后一步没有物理碰撞，但应更新至(a=A,b=X)后报 `DEADLOCK`。
9. 重放两套成功Oracle各六轮：a先入D与b先入D均到达B/A，冲突计数和deadlock计数均为0。
10. 对所有安全可达位置做完成路径可达性核对； `(a=A,b=X)` 与 `(a=Y,b=B)` 两态不可完成，提交后进入这类状态时报 `DEADLOCK`，不与物理冲突码混淆。
11. 同动作序列固定seed0执行两次：每tick列车位置、预约、冲突码、终止码和最终状态hash一致。
12. Oracle路径和失败案例不得进入Observation、Agent prompt或episode Trace；所有线路与容量为公开信息。
