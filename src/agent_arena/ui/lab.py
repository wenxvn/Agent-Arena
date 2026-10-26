"""V12 Lab 网页页面：实验配置 → 预检 → 提交 → 监控 → 对照 → 导出。

页面只调用 ``agent_arena.lab`` 与 ``agent_arena.web`` 服务层：

- 不在 Streamlit 里创建 Environment、不调用 Provider、不写账本；
- 预检与提交分离：预检零请求；真实付费必须显式确认；
- 所有可视化都来自已落盘的公开 trace（``lab.visualization`` 的 view-model）；
- 空状态与失败路径都给出可操作提示，不静默失败。
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

from agent_arena.lab.compare import CATEGORY_LABELS
from agent_arena.lab.contracts import (
    AgentArm,
    ComparisonPolicy,
    ExperimentBudget,
    ExperimentMode,
    ExperimentSpec,
    LiveApproval,
)
from agent_arena.lab.experiment import (
    ExperimentBusy,
    ExperimentError,
    ExperimentNotFound,
    LiveApprovalRequired,
    preflight,
)
from agent_arena.lab.registry import agent_catalog
from agent_arena.lab.visualization import FOCUS_MAPS
from agent_arena.ui import theme
from agent_arena.v10.runtime.catalog import seed_space
from agent_arena.web import catalog as web_catalog
from agent_arena.web.explain import metric_state_label, state_label
from agent_arena.web.schemas import SIMULATED_MODEL, SIMULATED_PROVIDER

LAB_CONFIG = "Lab · 实验配置"
LAB_MONITOR = "Lab · 实验监控"
LAB_RESULT = "Lab · 结果与对照"
LAB_VIEWS = [LAB_CONFIG, LAB_MONITOR, LAB_RESULT]

PROVIDER_LABELS: dict[str, str] = {
    SIMULATED_PROVIDER: "模拟执行（Fake/Scripted，不联网、不花钱）",
    "openai_compatible": "真实模型（[OI]-compatible / MiMo）",
    "ollama": "本地 Ollama",
}

MODE_NOTE: dict[str, str] = {
    "simulated": "SIMULATED：确定性脚本 Provider；只验证调用链、预算与诊断，不代表模型能力。",
    "live": "LIVE：真实模型请求，会产生费用；每局与实验级门禁都会生效。",
}


def _cost(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"¥{Decimal(str(value)):.6f}"
    except Exception:  # noqa: BLE001 - 展示层不因脏数据崩溃
        return str(value)


def _lab(get_lab: Callable[[], Any]) -> Any:
    try:
        return get_lab()
    except Exception as exc:  # noqa: BLE001 - 服务不可用时给出可读提示
        return exc


def _agent_labels() -> dict[str, str]:
    labels: dict[str, str] = {}
    for row in agent_catalog():
        labels[f"{row['agent_id']} · {row['display_name']}"] = str(row["agent_id"])
    return labels


def _common_seeds(maps: list[str]) -> list[int]:
    if not maps:
        return []
    common: set[int] | None = None
    for map_id in maps:
        space = set(seed_space(map_id))
        common = space if common is None else common & space
    return sorted(common or set())


def _build_spec(st: Any, *, allow_live: bool) -> ExperimentSpec | None:
    """从页面控件构造规格；非法配置返回 None 并显示原因。"""

    cards = {f"{card.map_id} · {card.title}": card.map_id for card in web_catalog.cards()}
    focus_labels = [
        label for label, map_id in cards.items() if map_id in FOCUS_MAPS
    ]
    map_labels = st.multiselect(
        "地图（可多选）", list(cards), default=focus_labels or list(cards)[:2]
    )
    maps = [cards[label] for label in map_labels]

    agents = _agent_labels()
    agent_labels = st.multiselect(
        "Agent 架构",
        list(agents),
        default=[
            label
            for label in agents
            if label.startswith(("basic.v1", "memory.v1", "planning.v1"))
        ],
    )
    arms = [AgentArm(agent_id=agents[label]) for label in agent_labels]

    provider_labels = list(PROVIDER_LABELS.values())
    provider_label = st.selectbox("执行通道", provider_labels, index=0)
    provider_id = next(
        (key for key, value in PROVIDER_LABELS.items() if value == provider_label),
        SIMULATED_PROVIDER,
    )
    simulated = provider_id == SIMULATED_PROVIDER
    model = (
        SIMULATED_MODEL
        if simulated
        else st.text_input("模型名", value="mimo-v2.6-flash")
    )

    seeds_available = _common_seeds(maps)
    seed_options = seeds_available or [0]
    seeds = st.multiselect(
        "环境 seed（共同可用）",
        seed_options,
        default=seed_options[:3],
    )

    per_run_requests = int(st.number_input("单局请求上限", value=60, min_value=1, max_value=200))
    per_run_decisions = int(
        st.number_input("单局决策上限", value=80, min_value=1, max_value=200)
    )
    per_run_cost = st.number_input(
        "单局费用上限 CNY", value=1.0, min_value=0.01, max_value=20.0
    )
    experiment_requests = int(
        st.number_input("实验请求上限", value=2_000, min_value=1, max_value=20_000)
    )
    experiment_cost = st.number_input(
        "实验费用上限 CNY", value=5.0, min_value=0.01, max_value=200.0
    )
    notes = st.text_input("实验备注（写入报告）", value="")

    approved = False
    approval_cap: Decimal | None = None
    if not simulated:
        st.warning(
            "真实付费实验必须先获得明确的预算批准。未批准时只能做预检，不能提交。"
        )
        approved = bool(
            st.checkbox("我已获得该实验的付费预算批准（会写入 approval 记录）", value=False)
        )
        if approved:
            cap = st.number_input(
                "批准的最高费用 CNY", value=float(experiment_cost), min_value=0.01, max_value=200.0
            )
            approval_cap = Decimal(str(cap))
        if not allow_live:
            st.info("当前页面以 preflight_only 模式运行：不会发出真实请求。")

    try:
        return ExperimentSpec(
            name=notes.strip() or "lab-experiment",
            notes=notes,
            maps=maps,
            agent_arms=arms,
            environment_seeds=seeds or None,
            provider_id=provider_id,
            model=model,
            mode=ExperimentMode.SIMULATED if simulated else ExperimentMode.LIVE,
            budget=ExperimentBudget(
                per_run_request_cap=per_run_requests,
                per_run_decision_cap=per_run_decisions,
                per_run_cost_cap_cny=Decimal(str(per_run_cost)),
                experiment_request_cap=experiment_requests,
                experiment_cost_cap_cny=Decimal(str(experiment_cost)),
            ),
            comparison=ComparisonPolicy(),
            preflight_only=(not simulated) and not (approved and allow_live),
            approval=LiveApproval(
                approved=approved and approval_cap is not None,
                approved_by="local-ui" if approved else "",
                max_cost_cny=approval_cap,
                note="由本机网页显式确认" if approved else "",
            ),
        )
    except Exception as exc:  # noqa: BLE001 - pydantic 校验失败要给可读原因
        st.error(f"配置不合法：{exc}")
        return None


def _render_matrix(st: Any, spec: ExperimentSpec) -> None:
    cells = spec.matrix()
    st.caption(
        f"矩阵：{len(spec.maps)} 图 × {len(spec.resolved_seeds())} seed × "
        f"{len(spec.agent_arms)} 实验臂 = {len(cells)} 个子局。"
    )
    preview = [
        {
            "matrix_index": cell.matrix_index,
            "地图": cell.map_id,
            "seed": cell.environment_seed,
            "Agent": cell.agent_id,
            "条件键": cell.condition_key,
        }
        for cell in cells[:60]
    ]
    st.dataframe(preview)
    if len(cells) > 60:
        st.caption("仅显示前 60 行；完整矩阵见导出的 experiment.json。")


def _render_preflight(st: Any, result: Any) -> None:
    tone = "success" if result.ok else "warning"
    st.markdown(
        theme.banner(
            "预检通过（未发送任何请求）" if result.ok else "预检发现阻塞项（未发送任何请求）",
            detail="；".join(result.blockers) or "配置与版本口径一致。",
            tone_name=tone,
            code=result.mode,
        ),
        unsafe_allow_html=True,
    )
    theme.stat_tiles(
        st,
        [
            ("子局", str(result.cells), f"seed {list(result.seeds)}", "accent"),
            ("请求上界", str(result.max_requests), "按单局上限估算", "info"),
            (
                "费用上界",
                _cost(result.max_cost_cny),
                "已登记价目" if result.cost_enforced else "无价目表：不启用金额门禁",
                "warning" if not result.cost_enforced else "success",
            ),
            (
                "批准",
                (
                    "已批准"
                    if result.approved
                    else ("需要批准" if result.approval_required else "不需要")
                ),
                "真实付费实验",
                "success" if result.approved or not result.approval_required else "warning",
            ),
        ],
    )
    for warning in result.warnings:
        st.info(warning)
    for note in result.notes:
        st.caption(note)


def _quick_demo_spec() -> ExperimentSpec:
    """一键离线演示：小矩阵、零费用、覆盖三种核心架构。"""

    return ExperimentSpec(
        name="quick-demo",
        notes="一键离线演示：MAP-22 + MAP-26，三种架构，1 个 seed。",
        maps=["MAP-22", "MAP-26"],
        agent_arms=[
            AgentArm(agent_id="basic.v1"),
            AgentArm(agent_id="memory.v1"),
            AgentArm(agent_id="planning.v1"),
        ],
        environment_seeds=[0],
        provider_id=SIMULATED_PROVIDER,
        model=SIMULATED_MODEL,
        mode=ExperimentMode.SIMULATED,
        budget=ExperimentBudget(
            per_run_request_cap=40,
            per_run_decision_cap=12,
            experiment_request_cap=600,
            experiment_cost_cap_cny=Decimal("10"),
        ),
    )


def _config_view(st: Any, get_lab: Callable[[], Any]) -> None:
    theme.page_head(
        st,
        "Agent Arena Lab",
        "配置一组架构对照实验",
        "同一模型、同一地图、同一 seed、同一预算，比较 Basic / Memory / Planning 的"
        "行为、成功率、成本与失败原因。预检不发送任何请求。",
    )
    service = _lab(get_lab)
    if isinstance(service, Exception):
        st.error(f"实验服务不可用：{service}")
        return
    quick = st.columns([1, 2])
    if quick[0].button("一键离线演示（3 架构 · 零费用）", type="primary", width="stretch"):
        try:
            experiment_id = service.create_experiment(_quick_demo_spec())
            service.submit(experiment_id)
        except ExperimentBusy as exc:
            st.warning(str(exc))
        except Exception as exc:  # noqa: BLE001
            st.error(f"演示启动失败：{exc}")
        else:
            st.session_state["lab_experiment_id"] = experiment_id
            st.success(f"已入队：{experiment_id}")
    quick[1].caption(
        "演示使用 SIMULATED 通道（确定性脚本 Provider）：不联网、不花钱，"
        "结果不代表模型能力；完整矩阵请在下方配置。"
    )
    st.divider()
    allow_live = bool(st.checkbox("允许提交真实付费实验（仍需预算批准）", value=False))
    spec = _build_spec(st, allow_live=allow_live)
    if spec is None:
        return
    st.divider()
    _render_matrix(st, spec)
    st.divider()
    result = preflight(spec)
    _render_preflight(st, result)

    st.divider()
    st.header("提交")
    service = _lab(get_lab)
    if isinstance(service, Exception):
        st.error(f"实验服务不可用：{service}")
        return
    confirmed = bool(
        st.checkbox(
            "我确认按上面的矩阵与门禁执行（模拟模式零费用；真实模式会产生费用）",
            value=spec.mode is ExperimentMode.SIMULATED,
        )
    )
    columns = st.columns(2)
    if columns[0].button("创建实验（写入冻结规格）", type="primary", width="stretch"):
        if not confirmed:
            st.warning("请先确认矩阵与预算。")
        else:
            try:
                experiment_id = service.create_experiment(spec)
            except Exception as exc:  # noqa: BLE001
                st.error(f"创建失败：{exc}")
            else:
                st.session_state["lab_experiment_id"] = experiment_id
                st.success(f"实验已创建：{experiment_id}")
    if columns[1].button("创建并提交队列", width="stretch"):
        if not confirmed:
            st.warning("请先确认矩阵与预算。")
        else:
            try:
                experiment_id = service.create_experiment(spec)
                service.submit(experiment_id)
            except LiveApprovalRequired as exc:
                st.error(str(exc))
            except ExperimentBusy as exc:
                st.warning(str(exc))
            except Exception as exc:  # noqa: BLE001
                st.error(f"提交失败：{exc}")
            else:
                st.session_state["lab_experiment_id"] = experiment_id
                st.success(f"已入队：{experiment_id}（单 worker 串行执行）")


def _experiment_options(service: Any) -> dict[str, str]:
    options: dict[str, str] = {}
    for experiment_id in reversed(service.store.list_ids()):
        try:
            manifest = service.status(experiment_id)
        except ExperimentNotFound:
            continue
        options[f"{manifest.name} · {experiment_id} · {manifest.state.value}"] = experiment_id
    return options


def _monitor_view(st: Any, get_lab: Callable[[], Any]) -> None:
    theme.page_head(
        st,
        "Agent Arena Lab",
        "实验监控",
        "父实验状态、每个子局的状态与消耗；停止只影响尚未开始的子局，并协作取消当前活跃局。",
    )
    service = _lab(get_lab)
    if isinstance(service, Exception):
        st.error(f"实验服务不可用：{service}")
        return
    options = _experiment_options(service)
    if not options:
        st.markdown(
            theme.empty_state(
                "🧪", "还没有实验", "先去「Lab · 实验配置」创建一组对照实验。"
            ),
            unsafe_allow_html=True,
        )
        return
    default = str(st.session_state.get("lab_experiment_id", ""))
    labels = list(options)
    index = next((i for i, label in enumerate(labels) if options[label] == default), 0)
    choice = st.selectbox("实验", labels, index=index)
    experiment_id = options[choice]
    st.session_state["lab_experiment_id"] = experiment_id
    manifest = service.status(experiment_id)
    st.caption(f"experiment_id：`{experiment_id}` · 子局仍在 `runs/web/<run_id>/`。")
    total = max(1, int(manifest.counts.get("total") or 1))
    done = int(manifest.counts.get("done") or 0)
    theme.stat_tiles(
        st,
        [
            ("状态", manifest.state.value, manifest.mode, "accent"),
            ("进度", f"{done}/{total}", f"未执行 {manifest.counts.get('pending', 0)}", "info"),
            (
                "请求",
                str(manifest.budget.get("requests_used", 0)),
                f"上限 {manifest.budget.get('experiment_request_cap')}",
                "info",
            ),
            (
                "已结算",
                _cost(manifest.budget.get("cost_settled_cny")),
                "未知消费" if manifest.budget.get("cost_unknown") else "费用已知",
                "warning" if manifest.budget.get("cost_unknown") else "success",
            ),
        ],
    )
    st.progress(min(1.0, done / total))
    if manifest.message:
        st.info(manifest.message)
    agents_in_matrix = sorted({str(item.get("agent_id")) for item in manifest.matrix})
    st.caption("实验臂：" + "、".join(agents_in_matrix))
    if manifest.children:
        st.dataframe(
            [
                {
                    "matrix": child.get("matrix_index"),
                    "地图": child.get("map_id"),
                    "seed": child.get("environment_seed"),
                    "Agent": child.get("agent_id"),
                    "状态": state_label(str(child.get("state") or "")),
                    "结局": child.get("outcome") or "—",
                    "请求": child.get("requests"),
                    "费用": _cost(child.get("cost_settled_cny")),
                    "run_id": child.get("run_id"),
                }
                for child in manifest.children
            ]
        )
    else:
        st.caption("尚未产生子局记录。")
    columns = st.columns(3)
    if columns[0].button("刷新", width="stretch"):
        st.rerun()
    if columns[1].button("停止实验", width="stretch", disabled=manifest.terminal):
        service.stop(experiment_id)
        st.warning("已请求停止；未开始的子局不会再执行。")
    if columns[2].button("续跑未完成子局", width="stretch", disabled=not manifest.terminal):
        try:
            service.submit(experiment_id, resume=True)
        except Exception as exc:  # noqa: BLE001
            st.error(f"续跑失败：{exc}")
        else:
            st.success("已重新入队：只执行尚未开始的子局。")
    st.caption(
        "页面刷新不会重复计费：所有事实来自磁盘 manifest；同一请求使用幂等键。"
    )


def _render_arm_table(st: Any, comparison: dict[str, Any]) -> None:
    rows = []
    for arm in comparison.get("arms") or []:
        rows.append(
            {
                "Agent": arm.get("agent_id"),
                "版本": arm.get("agent_version") or "—",
                "局数": arm.get("runs"),
                "有效分母": arm.get("valid_denominator"),
                "成功": arm.get("successes"),
                "成功率": arm.get("success_rate"),
                "机制失败": arm.get("mechanism_failures"),
                "预算截尾": arm.get("budget_censored"),
                "Provider 错误": arm.get("provider_errors"),
                "平均请求": arm.get("mean_requests"),
                "平均费用": _cost(arm.get("mean_cost_cny")),
                "拒绝动作": arm.get("rejected_actions"),
                "非法动作": arm.get("invalid_actions"),
            }
        )
    if rows:
        st.dataframe(rows)
    else:
        st.caption("还没有可聚合的实验臂数据。")


def _render_metrics(st: Any, comparison: dict[str, Any]) -> None:
    for row in comparison.get("per_map") or []:
        with st.expander(f"{row.get('map_id')} · 指标五态与配对"):
            records = []
            for arm in row.get("arms") or []:
                for metric_id, payload in sorted((arm.get("metrics") or {}).items()):
                    states = ", ".join(
                        f"{key}×{value}" for key, value in (payload.get("states") or {}).items()
                    )
                    records.append(
                        {
                            "Agent": arm.get("agent_id"),
                            "指标": metric_id,
                            "角色": payload.get("role"),
                            "五态": states or "—",
                            "有效均值": payload.get("mean"),
                            "合并比值": payload.get("pooled_ratio"),
                            "说明": payload.get("not_computed_reason") or "",
                        }
                    )
            if records:
                st.dataframe(records)
            else:
                st.caption("该图没有可聚合指标。")
            projection = row.get("projection") or {}
            if projection:
                st.markdown("**V12 研究投影（不覆盖 V10 指标）**")
                st.dataframe(
                    [
                        {
                            "指标": metric_id,
                            "五态": ", ".join(
                                f"{key}×{value}"
                                for key, value in (payload.get("states") or {}).items()
                            ),
                            "有效均值": payload.get("mean"),
                            "合并比值": payload.get("pooled_ratio"),
                            "口径版本": payload.get("rule_version"),
                        }
                        for metric_id, payload in sorted(projection.items())
                    ]
                )


def _render_view_model(st: Any, model: dict[str, Any]) -> None:
    st.markdown(f"**{model.get('title')}**（`{model.get('kind')}`）")
    if not model.get("available"):
        st.info(model.get("empty_reason") or "没有可绘制的公开数据。")
        return
    for note in model.get("notes") or []:
        st.caption(note)
    kind = model.get("kind")
    if kind == "diagnosis_funnel":
        st.dataframe(
            [
                {
                    "步": row.get("step"),
                    "事件": row.get("event"),
                    "候选数": row.get("candidate_count"),
                    "候选": ", ".join(row.get("candidate_sites") or []),
                    "tick": row.get("tick"),
                }
                for row in model.get("funnel") or []
            ]
        )
        counts = [
            {"step": row.get("step"), "候选数": row.get("candidate_count")}
            for row in model.get("funnel") or []
        ]
        if len(counts) >= 2:
            st.line_chart({"候选数": [row["候选数"] for row in counts]})
        if model.get("tests"):
            st.dataframe(model["tests"])
    elif kind in {"occupancy_timeline", "recovery_gantt"}:
        st.dataframe(model.get("timeline") or [])
        if kind == "recovery_gantt":
            delivered = [
                {"step": row.get("step"), "送达": row.get("delivered")}
                for row in model.get("timeline") or []
                if row.get("delivered") is not None
            ]
            if delivered:
                st.line_chart({"送达": [row["送达"] for row in delivered]})
            if model.get("closed_ticks"):
                st.warning("本局出现过临时封闭区段（公开信息）。")
    elif kind == "exploration_graph":
        st.dataframe(model.get("nodes") or [])
        edges = [
            {
                "从": edge.get("from"),
                "方位": edge.get("bearing"),
                "到": edge.get("to"),
                "步": edge.get("step"),
                "被接受": edge.get("accepted"),
            }
            for edge in model.get("edges") or []
        ]
        st.dataframe(edges)
        st.caption(
            f"已发现路标 {model.get('discovered_node_count')} 个；"
            f"移动 {model.get('moves_used')} / {model.get('move_budget')}。"
        )
        if model.get("agent_notes"):
            st.dataframe(model["agent_notes"])
        else:
            st.info("本局没有写入任何公开记忆（agent_notes 为空）。")
        if model.get("rejected_moves"):
            st.caption(
                f"被拒绝的移动 {len(model['rejected_moves'])} 次（未改变位置，因此不计入探索边）："
                + "、".join(
                    f"步 {item['step']} {item['bearing']}→{item['result']}"
                    for item in model["rejected_moves"][:5]
                )
            )
    elif kind == "maintenance_chain":
        st.dataframe(model.get("chain") or [])
    elif kind == "evidence_chain":
        st.dataframe(model.get("evidence_cards") or [])
        st.caption(
            f"已记录条目 {model.get('recorded_count')} / {model.get('required_count')}；"
            f"链条核对：{model.get('chain_reconciled')}"
        )
        if model.get("accusations"):
            st.dataframe(model["accusations"])
    else:
        histogram = model.get("tool_histogram") or {}
        if histogram:
            st.dataframe([{"工具": key, "次数": value} for key, value in histogram.items()])
        series = model.get("series") or {}
        for key, values in list(series.items())[:4]:
            if len(values) >= 2:
                st.line_chart({key: [row["value"] for row in values]})
        st.dataframe(model.get("timeline") or [])


def _render_findings(st: Any, findings: list[Any]) -> None:
    if not findings:
        st.info("没有命中任何确定性诊断规则（NOT_ENOUGH_EVIDENCE 之外的结论不生成）。")
        return
    st.dataframe(
        [
            {
                "地图": item.map_id,
                "run_id": item.run_id,
                "类别": item.category,
                "严重度": item.severity,
                "证据步": ", ".join(str(step) for step in item.evidence_steps) or "—",
                "说明": item.summary,
                "建议核查": item.suggested_check or "—",
            }
            for item in findings
        ]
    )


def _result_view(st: Any, get_lab: Callable[[], Any]) -> None:
    theme.page_head(
        st,
        "Agent Arena Lab",
        "结果与对照",
        "配对比较、五态指标、逐局明细、失败证据与六图可视化；导出机器可读结果与可读报告。",
    )
    service = _lab(get_lab)
    if isinstance(service, Exception):
        st.error(f"实验服务不可用：{service}")
        return
    options = _experiment_options(service)
    if not options:
        st.markdown(
            theme.empty_state("📊", "还没有结果", "先创建并跑完一组实验，再回到这里对照。"),
            unsafe_allow_html=True,
        )
        return
    default = str(st.session_state.get("lab_experiment_id", ""))
    labels = list(options)
    index = next((i for i, label in enumerate(labels) if options[label] == default), 0)
    choice = st.selectbox("实验", labels, index=index)
    experiment_id = options[choice]
    st.session_state["lab_experiment_id"] = experiment_id
    summary = service.summary(experiment_id)
    comparison = service.comparison(experiment_id)
    records = service.records(experiment_id)

    st.markdown(
        theme.banner(
            f"{summary.get('state')} · {summary.get('mode')}",
            detail=MODE_NOTE.get(str(summary.get("mode")), ""),
            tone_name="success" if summary.get("state") == "COMPLETED" else "warning",
            code=str(summary.get("experiment_id")),
        ),
        unsafe_allow_html=True,
    )
    if summary.get("supplement_of"):
        st.info(
            f"这是来源 `{summary['supplement_of']}` 的衍生实验"
            f"（{summary.get('supplement_reason') or '原因未记录'}）。"
            "原始实验的记录与账本未被修改；跨版本不配对。"
        )
    if summary.get("only_conditions"):
        st.caption(
            f"本实验只包含 {len(summary['only_conditions'])} 个条件"
            "（其余条件见来源实验）。"
        )
    theme.stat_tiles(
        st,
        [
            (
                "子局",
                f"{summary.get('executed')}/{summary.get('total_cells')}",
                "已执行 / 计划",
                "accent",
            ),
            ("有效分母", str(summary.get("valid_denominator")), "排除 Provider 错误/取消", "info"),
            (
                "成功",
                str(summary.get("successes")),
                f"成功率 {summary.get('success_rate')}",
                "success" if summary.get("successes") else "neutral",
            ),
            (
                "可比性",
                str(comparison.get("verdict")),
                "；".join(comparison.get("reasons") or [])[:60] or "版本口径一致",
                "success" if comparison.get("verdict") == "COMPARABLE" else "warning",
            ),
        ],
    )
    for note in comparison.get("notes") or []:
        st.caption(note)
    for reason in comparison.get("reasons") or []:
        st.warning(reason)

    tabs = st.tabs(["概览", "逐局明细", "可视化", "证据与差异", "导出"])
    with tabs[0]:
        st.header("实验臂汇总")
        _render_arm_table(st, comparison)
        st.header("类别分布")
        st.dataframe(
            [
                {"类别": CATEGORY_LABELS.get(key, key), "局数": value}
                for key, value in (summary.get("categories") or {}).items()
            ]
            or [{"类别": "尚未执行", "局数": 0}]
        )
        _render_metrics(st, comparison)
    with tabs[1]:
        if records:
            st.dataframe(
                [
                    {
                        "matrix": record.get("matrix_index"),
                        "地图": record.get("map_id"),
                        "seed": record.get("environment_seed"),
                        "Agent": record.get("agent_id"),
                        "状态": state_label(str(record.get("state"))),
                        "类别": CATEGORY_LABELS.get(str(record.get("category")), ""),
                        "成功": record.get("success"),
                        "决策": record.get("decisions"),
                        "请求": record.get("requests"),
                        "费用": _cost(record.get("cost_cny")),
                        "主指标": record.get("primary_metric"),
                        "主指标状态": metric_state_label(str(record.get("primary_state"))),
                        "run_id": record.get("run_id"),
                    }
                    for record in records
                ]
            )
        else:
            st.info("还没有已执行的子局。")
    with tabs[2]:
        run_ids = [str(record["run_id"]) for record in records]
        if not run_ids:
            st.info("没有可回放的子局。")
        else:
            run_id = st.selectbox("选择一局查看公开轨迹", run_ids)
            model = service.view_model(run_id)
            _render_view_model(st, model)
    with tabs[3]:
        run_ids = [str(record["run_id"]) for record in records]
        findings = service.findings(experiment_id)
        st.header("失败诊断（确定性规则）")
        if run_ids:
            only = st.selectbox("只看某一局（可选）", ["全部", *run_ids])
            selected = findings if only == "全部" else [f for f in findings if f.run_id == only]
        else:
            selected = findings
        _render_findings(st, selected)
        st.header("两条轨迹对照")
        if len(run_ids) >= 2:
            left = st.selectbox("A 局", run_ids, index=0)
            right = st.selectbox("B 局", run_ids, index=1)
            if st.button("生成对照"):
                try:
                    diff = service.pairwise(experiment_id, left, right)
                except ExperimentError as exc:
                    st.error(str(exc))
                else:
                    st.session_state["lab_pair"] = diff
        pair = st.session_state.get("lab_pair")
        if isinstance(pair, dict):
            diff = pair.get("diff") or {}
            st.markdown(
                theme.banner(
                    f"首次差异：第 {diff.get('first_divergence_step')} 步",
                    detail=str(diff.get("first_divergence_summary") or ""),
                    tone_name="accent",
                    code=str(pair.get("verdict")),
                ),
                unsafe_allow_html=True,
            )
            st.dataframe(diff.get("stage_deltas") or [])
            st.dataframe(pair.get("hypotheses") or [])
        else:
            st.caption("选择两个不同架构的局，生成事件序列对照与可验证假设。")
    with tabs[4]:
        st.caption("导出只包含公开数据；不写回账本、不重建付费状态。")
        columns = st.columns(2)
        if columns[0].button("生成导出文件", width="stretch"):
            try:
                files = service.export(experiment_id)
            except Exception as exc:  # noqa: BLE001
                st.error(f"导出失败：{exc}")
            else:
                st.session_state["lab_exports"] = files
                st.success("已写出 runs.csv / metrics.csv / paired_comparison.csv / report.md")
        files = st.session_state.get("lab_exports") or {}
        if isinstance(files, dict) and files:
            report_path = files.get("report.md")
            if report_path:
                try:
                    from pathlib import Path

                    report_text = Path(report_path).read_text(encoding="utf-8")
                except OSError:
                    report_text = ""
                if report_text:
                    st.download_button(
                        "下载实验报告 report.md",
                        data=report_text.encode("utf-8"),
                        file_name=f"{experiment_id}-report.md",
                        mime="text/markdown",
                    )
                    with st.expander("报告预览"):
                        st.markdown(report_text)
            for name, path in files.items():
                if name == "report.md":
                    continue
                try:
                    from pathlib import Path

                    blob = Path(path).read_bytes()
                except OSError:
                    continue
                st.download_button(
                    f"下载 {name}",
                    data=blob,
                    file_name=f"{experiment_id}-{name}",
                    mime="text/csv" if name.endswith(".csv") else "application/json",
                )


def render(st: Any, get_lab: Callable[[], Any], view: str) -> None:
    if view == LAB_CONFIG:
        _config_view(st, get_lab)
    elif view == LAB_MONITOR:
        _monitor_view(st, get_lab)
    else:
        _result_view(st, get_lab)


__all__ = [
    "LAB_CONFIG",
    "LAB_MONITOR",
    "LAB_RESULT",
    "LAB_VIEWS",
    "MODE_NOTE",
    "PROVIDER_LABELS",
    "render",
]
