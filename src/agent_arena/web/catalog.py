"""30 图公开目录与展示层元数据。

- 稳定 ID、世界、设计难度、规则/指标 hash 全部来自 V10 catalog；
- ``display_difficulty`` 与 ``difficulty_note`` 是纯展示层数据，不修改运行时；
- 地图详情只读取 ``public_rules`` / ``SHAPES`` / ``scenario_descriptor`` / 初始
  Observation，绝不读取 ``sealed_truth``。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Any

from agent_arena.v10.baselines.suite import decision_budget
from agent_arena.v10.contract import action_contract
from agent_arena.v10.contract_hints import CONTRACT_HINTS
from agent_arena.v10.runtime.catalog import (
    LEVEL_OF,
    MAP_IDS,
    V10_MAPS,
    WORLD_OF,
    create_environment,
    metric_hash,
    rule_hash,
    seed_space,
    v10_class,
)

WORLD_ORDER: tuple[str, ...] = (
    "spaceship",
    "lighthouse",
    "abyss",
    "polar",
    "pyramid",
    "subway",
    "volcano",
    "jungle",
    "lunar",
    "castle",
)

WORLD_LABELS: dict[str, str] = {
    "spaceship": "飞船",
    "lighthouse": "灯塔",
    "abyss": "深海站",
    "polar": "极地",
    "pyramid": "金字塔",
    "subway": "地铁",
    "volcano": "火山",
    "jungle": "丛林",
    "lunar": "月球",
    "castle": "古堡",
}

WORLD_EMOJI: dict[str, str] = {
    "spaceship": "🚀",
    "lighthouse": "🗼",
    "abyss": "🌊",
    "polar": "🧊",
    "pyramid": "🏛️",
    "subway": "🚇",
    "volcano": "🌋",
    "jungle": "🌿",
    "lunar": "🌕",
    "castle": "🏰",
}

WORLD_INTRO: dict[str, str] = {
    "spaceship": "在失压与断电之间分配氧气和电力。",
    "lighthouse": "与潮汐、风暴和信号窗口抢时间。",
    "abyss": "在进水、缺氧与连锁故障中做诊断。",
    "polar": "极寒补给、搜救与长期生存。",
    "pyramid": "从碑文与谎言中推出唯一答案。",
    "subway": "单线会让、时刻表与故障恢复。",
    "volcano": "温度预测、冷却调度与有损调水。",
    "jungle": "无图导航、线索经济与断路改线。",
    "lunar": "出舱流程、故障诊断与多目标任务。",
    "castle": "证据链、不可靠证人与法庭指控。",
}

#: 展示标题：修正 V8 catalog 中 6 张缺失标题的图，不修改运行时。
DISPLAY_TITLES: dict[str, str] = {
    "MAP-01": "破损的曙光号",
    "MAP-02": "双重警报",
    "MAP-03": "最后的百步",
    "MAP-04": "潮汐密道",
    "MAP-05": "三束信号",
    "MAP-06": "暴风眼",
    "MAP-07": "阀门方向",
    "MAP-08": "漏点诊断",
    "MAP-09": "深海连锁故障",
    "MAP-10": "最后一桶燃料",
    "MAP-11": "失联的小队",
    "MAP-12": "极夜三十天",
    "MAP-13": "四神之门",
    "MAP-14": "说谎的祭司",
    "MAP-15": "会变化的迷宫",
    "MAP-16": "单线预约与节点容量",
    "MAP-17": "早高峰",
    "MAP-18": "故障传播",
    "MAP-19": "温度临界点",
    "MAP-20": "冷却网络",
    "MAP-21": "喷发倒计时",
    "MAP-22": "无地图的丛林",
    "MAP-23": "迷雾中的遗迹",
    "MAP-24": "消失的道路",
    "MAP-25": "第一次出舱",
    "MAP-26": "失败的维修计划",
    "MAP-27": "月球车",
    "MAP-28": "消失的王冠",
    "MAP-29": "不可靠的证人",
    "MAP-30": "午夜审判",
}

#: 展示难度（简单/中等/困难/待校准），基于动作链、规则复杂度与人工体验解释。
DISPLAY_DIFFICULTY: dict[str, str] = {
    "MAP-01": "简单",
    "MAP-02": "中等",
    "MAP-03": "困难",
    "MAP-04": "简单",
    "MAP-05": "中等",
    "MAP-06": "困难",
    "MAP-07": "简单",
    "MAP-08": "中等",
    "MAP-09": "困难",
    "MAP-10": "简单",
    "MAP-11": "中等",
    "MAP-12": "中等",
    "MAP-13": "简单",
    "MAP-14": "困难",
    "MAP-15": "困难",
    "MAP-16": "中等",
    "MAP-17": "困难",
    "MAP-18": "困难",
    "MAP-19": "困难",
    "MAP-20": "困难",
    "MAP-21": "困难",
    "MAP-22": "中等",
    "MAP-23": "中等",
    "MAP-24": "困难",
    "MAP-25": "中等",
    "MAP-26": "中等",
    "MAP-27": "困难",
    "MAP-28": "中等",
    "MAP-29": "困难",
    "MAP-30": "困难",
}

DIFFICULTY_NOTES: dict[str, str] = {
    "MAP-01": "五步维修链，但每步都有公开检查点；规则少、失败可立即定位。",
    "MAP-02": "泄漏时点不公开，需同时照看导航核心与乘员两个倒计时。",
    "MAP-03": "五阶段顺序 + 只出现一次的航线码 + EVA 氧气预算，任一环节断链即失败。",
    "MAP-04": "路线短，核心只是等待安全潮汐相位；评分奖励更早完成。",
    "MAP-05": "三座塔各自校准并卡窗口，跨塔移动耗时随实例变化。",
    "MAP-06": "天气隐藏且预报有误差，要在读预报、加固与直接维修间权衡风险。",
    "MAP-07": "只需判断阀门方向并开阀，动作空间小、阈值明确。",
    "MAP-08": "测试分区需要读题，但候选集逐步收缩；封存诊断后维修路径唯一。",
    "MAP-09": "水位、电力、供氧三条资源线同时递减，修复窗口很窄。",
    "MAP-10": "本质是一道载重与油耗计算题，失败后原因直接可读。",
    "MAP-11": "搜索有漏检概率，风暴窗口改变耗时；同一策略结果会波动。",
    "MAP-12": "回合多（30 天）但每天只有三种劳动，认知负担低，主要是配平。",
    "MAP-13": "读碑、记录、排列三段式，空间小且提示完整。",
    "MAP-14": "说谎者逻辑题；最多 4 问、只能错交 1 次，推理强度高于设计标签。",
    "MAP-15": "要从样例归纳周期与颜色偏移，并在测试区一次通过。",
    "MAP-16": "只有两列车，但 set_route 与 move_train 分帧提交，容易漏掉整帧语义。",
    "MAP-17": "四车时刻表 + 咽喉站容量，操作项多且冲突会整帧拒绝。",
    "MAP-18": "18 名乘客、区段临时封闭、容量与对穿冲突，恢复策略复杂。",
    "MAP-19": "规则不多，但每 tick 必须申报温度且冷却延迟两 tick，操作链明显长于设计标签。",
    "MAP-20": "十条公开规则、有损旁路与区阀上限叠加，是本轮热控最难的一张。",
    "MAP-21": "喷发时刻隐藏，采样耗时与安全撤离直接冲突。",
    "MAP-22": "没有地图，需要自己记录路标并原路返回，空间记忆负担高。",
    "MAP-23": "先买线索再调查，补给与线索费用需要规划。",
    "MAP-24": "桥断时点未知、潮道相位隐藏，晚一步就只能走慢速山路。",
    "MAP-25": "九种工具、完整 EVA 流程；步骤多但每步都有明确前提。",
    "MAP-26": "测试、换件、回滚三种手段，盲换也可行但更耗备件。",
    "MAP-27": "电量、货舱、氧气、中继与伤员多目标同时约束。",
    "MAP-28": "四字段指控且每个字段要两类来源，结构严格但房间图很小。",
    "MAP-29": "12 次提问内识别不可靠证人，还要给出可引用的物证链。",
    "MAP-30": "案卷链 + 五条近期窗口 + 法庭一次性提交，任何证据缺失都会拒绝。",
}

MECHANISM: dict[str, str] = {
    "MAP-01": "供氧 / 配电时序",
    "MAP-02": "事件顺序 · 双倒计时",
    "MAP-03": "五阶段 · 航线码记忆",
    "MAP-04": "潮汐相位",
    "MAP-05": "三窗口排程",
    "MAP-06": "隐藏天气 · 风险预算",
    "MAP-07": "阀门方向推断",
    "MAP-08": "分组测试 · 唯一诊断",
    "MAP-09": "三资源连锁",
    "MAP-10": "载重与油耗",
    "MAP-11": "概率搜索",
    "MAP-12": "30 天资源配平",
    "MAP-13": "碑文约束排列",
    "MAP-14": "说谎者推理",
    "MAP-15": "周期规律归纳",
    "MAP-16": "单线会让",
    "MAP-17": "时刻表排程",
    "MAP-18": "区段封闭恢复",
    "MAP-19": "温度预测 · 冷却延迟",
    "MAP-20": "有损旁路调水",
    "MAP-21": "隐藏喷发 · 采样风险",
    "MAP-22": "无图空间记忆",
    "MAP-23": "线索经济",
    "MAP-24": "桥断与潮道",
    "MAP-25": "EVA 出舱流程",
    "MAP-26": "故障诊断 · 备件",
    "MAP-27": "多目标月球车",
    "MAP-28": "四字段取证指控",
    "MAP-29": "不可靠证人",
    "MAP-30": "案卷链 · 法庭指控",
}

#: 首页/详情页给普通用户的关键提醒（不是规则本身）。
WATCH_OUT: dict[str, str] = {
    "MAP-19": "记住：读取温度、设置冷却、调负荷都不会推进时间，每个 tick 必须 wait 一次。",
    "MAP-20": "记住：set_flow、旁路与负荷只改本 tick 设置，必须 wait 才结算；旁路只送到 4/5。",
    "MAP-28": "提交前检查：四个字段都要有至少两种不同来源类别的已记录证据。",
    "MAP-29": "提问预算只有 12 次；先取物证再比对证词，能少走弯路。",
    "MAP-30": "案卷条目需要“现场记录 + 证人确认”；近期动作窗口只保留最近 5 条。",
}


@dataclass(frozen=True)
class MapCard:
    map_id: str
    world: str
    world_label: str
    world_emoji: str
    title: str
    design_difficulty: str
    display_difficulty: str
    difficulty_note: str
    mechanism: str
    goal: str
    decision_budget: int
    seeds: tuple[int, ...]
    tool_count: int
    rule_count: int
    runtime: str
    rule_hash: str
    metric_hash: str
    primary_metric: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["seeds"] = list(self.seeds)
        return payload


def _environment(map_id: str, seed: int = 0) -> Any:
    return create_environment(map_id, environment_seed=seed)


@lru_cache(maxsize=1)
def cards() -> tuple[MapCard, ...]:
    items: list[MapCard] = []
    for map_id in MAP_IDS:
        environment = _environment(map_id)
        observation = environment.observe()
        goal = str(observation.get("goal") or "")
        factory = v10_class(map_id)
        items.append(
            MapCard(
                map_id=map_id,
                world=WORLD_OF[map_id],
                world_label=WORLD_LABELS[WORLD_OF[map_id]],
                world_emoji=WORLD_EMOJI[WORLD_OF[map_id]],
                title=DISPLAY_TITLES[map_id],
                design_difficulty=LEVEL_OF[map_id],
                display_difficulty=DISPLAY_DIFFICULTY[map_id],
                difficulty_note=DIFFICULTY_NOTES[map_id],
                mechanism=MECHANISM[map_id],
                goal=goal,
                decision_budget=decision_budget(map_id),
                seeds=seed_space(map_id),
                tool_count=len(environment.SHAPES),
                rule_count=len(environment.public_rules()),
                runtime="v10" if map_id in V10_MAPS else "v8-fallback",
                rule_hash=rule_hash(map_id),
                metric_hash=metric_hash(map_id),
                primary_metric=str(factory.PRIMARY_METRIC),
            )
        )
    return tuple(items)


def card(map_id: str) -> MapCard:
    for item in cards():
        if item.map_id == map_id:
            return item
    raise KeyError(map_id)


def world_groups() -> dict[str, list[MapCard]]:
    groups: dict[str, list[MapCard]] = {world: [] for world in WORLD_ORDER}
    for item in cards():
        groups[item.world].append(item)
    return groups


def map_detail(map_id: str, seed: int = 0) -> dict[str, Any]:
    """地图详情：只含公开规则、动作形状、实例描述与初始观察。"""

    item = card(map_id)
    environment = _environment(map_id, seed)
    observation = environment.observe()
    descriptor: dict[str, Any] = {}
    if hasattr(environment, "scenario_descriptor"):
        descriptor = dict(environment.scenario_descriptor())
    hints = list(CONTRACT_HINTS.get(map_id, ()))
    contract = action_contract(environment.SHAPES)
    fields = sorted(environment.PUBLIC_FIELDS) or sorted(observation)
    return {
        "card": item.to_dict(),
        "seed": seed,
        "goal": str(observation.get("goal") or item.goal),
        "rules": list(environment.public_rules()),
        "contract": contract.splitlines(),
        "contract_hints": hints,
        "public_fields": fields,
        "scenario_descriptor": descriptor,
        "starting_observation": observation,
        "watch_out": WATCH_OUT.get(map_id, ""),
        "success_text": "完成公开目标后，环境返回 scenario_success。",
        "failure_text": (
            "触犯公开规则、超过时限或资源归零时返回 scenario_failure；"
            "动作/决策预算耗尽另记为 CENSORED / BUDGET_REACHED，不伪装成失败。"
        ),
    }


def display_difficulty_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in cards():
        rows.append(
            {
                "map_id": item.map_id,
                "world": item.world_label,
                "title": item.title,
                "design_difficulty": item.design_difficulty,
                "display_difficulty": item.display_difficulty,
                "note": item.difficulty_note,
                "mechanism": item.mechanism,
            }
        )
    return rows


def filter_cards(
    *,
    world: str = "",
    difficulty: str = "",
    query: str = "",
) -> list[MapCard]:
    text = query.strip().lower()
    selected: list[MapCard] = []
    for item in cards():
        if world and item.world != world:
            continue
        if difficulty and item.display_difficulty != difficulty:
            continue
        if text:
            haystack = " ".join(
                (item.map_id, item.title, item.mechanism, item.goal, item.world_label)
            ).lower()
            if text not in haystack:
                continue
        selected.append(item)
    return selected


__all__ = [
    "DIFFICULTY_NOTES",
    "DISPLAY_DIFFICULTY",
    "DISPLAY_TITLES",
    "MECHANISM",
    "WATCH_OUT",
    "WORLD_EMOJI",
    "WORLD_INTRO",
    "WORLD_LABELS",
    "WORLD_ORDER",
    "MapCard",
    "card",
    "cards",
    "display_difficulty_rows",
    "filter_cards",
    "map_detail",
    "world_groups",
]
