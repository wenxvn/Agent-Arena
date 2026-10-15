# MAP-24 设计验收

状态：`DESIGN_COMPLETE_PENDING_RUNTIME`。本关以会变化的邻接图为核心：桥的两条边在tick 8后永久消失，D-E潮道的周期相位按seed隐藏，F绕道较慢但始终通行。项目范围仅含手工设计和离线规则回放。

## 逐图核对

- [x] 六节点、七双向边固定；A-B-C-D-E-A与A-F-C两条不同路线，F两段各2 tick。
- [x] B在tick 8事件后移除A-B、B-C；事件发生在动作抵达该tick后，桥心B留人即孤立。
- [x] D-E每四tick开两tick；相位offset隐藏、seed0为0，关门尝试停留原地并耗1 tick。
- [x] 两件必取物资分置C/D；必须一并带回A且完成tick≤24。
- [x] `probe_bridge`仅报当下状况、测水仅报本地完成时读数、`record_route`只抄本地邻接快照且不会自动更新；Observation不含全图或未来事件表。
- [x] 四条逐拍手算策略：桥环抢运tick7、探桥后应变tick14、山路测潮tick11、一次过时路线错误后恢复tick15。
- [x] F01桥心事件孤立；F02忽视断边连续错走并跨deadline；F03重复测水越过deadline。均携带物资且未成功交付。
- [x] B01/B02覆盖tick8移动结算位置差；B03核对seed0潮窗开闭端点；B04核对tick24/25交付边界；B05核对闭潮失败移动原地耗时。
- [x] `planning/map24_audit.py` 全部手工路线、失败/边界及四种潮位相位离线复放通过；seed0 Oracle与参考账双次生成逐字节一致，Oracle SHA-256=`33C3799D4977FA374C788DDB69F4381045E1A0EDE969482F37EE1801D992CFEF`。

## 环境实现后

需验证桥事件顺序和桥心受困、局部连接更新、隐藏潮位相位、关闭边移动耗时、两拍山路的中途事件结算、路线笔记不自动同步及deadline端点。离线回放不代表环境、Agent或模型已验证。
