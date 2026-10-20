"""V10 公开接口的逐图补充说明（不含真值或答案）。

这些文本原先只存在于 ``scripts/run_v10_mimo.py`` 的 prompt 组装中。V11 网页需要
在同一处展示“地图详情”和真实挑战的 system prompt，因此提取为只读常量；内容与
V10 冻结 prompt 逐字一致（有测试防止漂移）。
"""

from __future__ import annotations

CONTRACT_HINTS: dict[str, tuple[str, ...]] = {
    "MAP-18": (
        "operations 是对象（不是数组）：键为列车 id，值为对象；"
        '值的 op 只能是 "release"/"detour"/"temporary_stop"/"cancel_service"，'
        'release/detour 用 "to" 给目标站，cancel_service 用 "task_id" 给任务。',
    ),
    "MAP-28": (
        "claims 是对象数组（不是对象映射）：每个元素形如 "
        '{"claim_id": <四个字段之一>, "value": <该字段的取值>}；'
        "citations_by_claim 是对象：键为四个字段名，值为已记录证据 ID 的数组。",
    ),
    "MAP-19": (
        "forecast_next 与 set_cooling 都是长度为 3 的整数数组，顺序固定为区 A、B、C"
        "（不是以区名为键的对象）。",
    ),
    "MAP-16": (
        "set_route/occupy_siding 只登记下一跳（train_id + next_node），不会移动列车；"
        "必须再调用 move_train 才会把当前所有已登记路由作为一整帧提交并推进 1 tick。",
        "section_id 接受 XY、YX 或 X_Y 三种写法（对应列车当前节点与已登记目标节点）。",
    ),
}

__all__ = ["CONTRACT_HINTS"]
