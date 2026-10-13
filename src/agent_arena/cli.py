"""Command line entry points for local Agent Arena experiments."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import nullcontext
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

import typer

from agent_arena.agents import (
    CandidateSelectionAgent,
    MemoryAgent,
    PlannerAssistedAgent,
    PlanningAgent,
    ReactAgent,
)
from agent_arena.config import RuntimeSettings
from agent_arena.evaluation import (
    BenchmarkRow,
    EpisodeOutcome,
    EpisodeRunner,
    FailureAnalysis,
    StepTrace,
    TraceEvent,
    analyze_trace,
    read_episode_trace,
    row_from_trace,
    write_benchmark,
    write_episode_trace,
    write_failure_analysis,
)
from agent_arena.llm import (
    BailianDecisionProvider,
    BudgetedDecisionProvider,
    DecisionProvider,
    FakeDecisionProvider,
    OllamaDecisionProvider,
    OllamaModelVerifier,
    ProviderBudgetController,
    ProviderBudgetExceeded,
    ProviderBudgetLimits,
    ProviderBudgetSnapshot,
)
from agent_arena.llm.bailian import BailianModelVerifier, ModelVerificationError
from agent_arena.llm.openai import OpenAIDecisionProvider, OpenAIModelVerifier
from agent_arena.worlds import (
    Environment,
    create_environment,
)

app = typer.Typer(help="运行本地 Agent Arena 实验。", no_args_is_help=True)


def _load_settings(
    provider: str | None = None,
    agent: str | None = None,
    seed: int | None = None,
    world: str | None = None,
    world_version: str | None = None,
    runs_dir: Path | None = None,
    reasoning_effort: str | None = None,
    memory_version: str | None = None,
    step_limit: int | None = None,
    max_provider_requests: int | None = None,
    max_provider_tokens: int | None = None,
    max_provider_output_tokens: int | None = None,
    provider_budget_timeout_seconds: int | None = None,
    provider_budget_experiment_id: str | None = None,
    provider_budget_expected_provider: str | None = None,
    provider_budget_expected_model: str | None = None,
    provider_budget_expected_world_definition_hash: str | None = None,
    provider_budget_expected_base_prompt_hash: str | None = None,
    provider_budget_ledger: Path | None = None,
) -> RuntimeSettings:
    bounded_experiment = any(
        value is not None
        for value in (
            max_provider_requests,
            max_provider_tokens,
            max_provider_output_tokens,
            provider_budget_timeout_seconds,
            provider_budget_experiment_id,
            provider_budget_expected_provider,
            provider_budget_expected_model,
            provider_budget_expected_world_definition_hash,
            provider_budget_expected_base_prompt_hash,
            provider_budget_ledger,
        )
    )
    return RuntimeSettings.load(
        {
            "provider": provider,
            "agent": agent,
            "seed": seed,
            "world": world,
            "world_version": world_version,
            "runs_dir": runs_dir,
            "reasoning_effort": reasoning_effort,
            "memory_version": memory_version,
            "step_limit": step_limit,
            "max_provider_requests": max_provider_requests,
            "max_provider_tokens": max_provider_tokens,
            "max_provider_output_tokens": max_provider_output_tokens,
            "provider_budget_timeout_seconds": provider_budget_timeout_seconds,
            "provider_budget_experiment_id": provider_budget_experiment_id,
            "provider_budget_expected_provider": provider_budget_expected_provider,
            "provider_budget_expected_model": provider_budget_expected_model,
            "provider_budget_expected_world_definition_hash": (
                provider_budget_expected_world_definition_hash
            ),
            "provider_budget_expected_base_prompt_hash": provider_budget_expected_base_prompt_hash,
            "provider_budget_ledger": provider_budget_ledger,
            "retry_count": 0 if bounded_experiment else None,
        }
    )


@app.command()
def run(
    provider: Annotated[str | None, typer.Option("--provider")] = None,
    agent: Annotated[str | None, typer.Option("--agent")] = None,
    memory_version: Annotated[
        str | None,
        typer.Option("--memory-version", help="MemoryAgent 记忆策略：v2 或 v3_spatial_event。"),
    ] = None,
    seed: Annotated[int | None, typer.Option("--seed")] = None,
    world: Annotated[str | None, typer.Option("--world")] = None,
    world_version: Annotated[str | None, typer.Option("--world-version")] = None,
    output_dir: Annotated[Path | None, typer.Option("--output-dir")] = None,
    step_limit: Annotated[int | None, typer.Option("--step-limit", min=1)] = None,
    max_provider_requests: Annotated[
        int | None,
        typer.Option("--provider-request-budget", min=1),
    ] = None,
    max_provider_tokens: Annotated[
        int | None,
        typer.Option("--provider-token-budget", min=1),
    ] = None,
    max_provider_output_tokens: Annotated[
        int | None,
        typer.Option("--provider-output-token-cap", min=1),
    ] = None,
    provider_budget_timeout_seconds: Annotated[
        int | None,
        typer.Option("--provider-budget-timeout-seconds", min=1),
    ] = None,
    provider_budget_experiment_id: Annotated[
        str | None,
        typer.Option("--provider-budget-experiment-id"),
    ] = None,
    provider_budget_expected_provider: Annotated[
        str | None,
        typer.Option("--provider-budget-expected-provider"),
    ] = None,
    provider_budget_expected_model: Annotated[
        str | None,
        typer.Option("--provider-budget-expected-model"),
    ] = None,
    provider_budget_expected_world_definition_hash: Annotated[
        str | None,
        typer.Option("--provider-budget-expected-world-hash"),
    ] = None,
    provider_budget_expected_base_prompt_hash: Annotated[
        str | None,
        typer.Option("--provider-budget-expected-prompt-hash"),
    ] = None,
    provider_budget_ledger: Annotated[
        Path | None,
        typer.Option("--provider-budget-ledger"),
    ] = None,
    autonomous: Annotated[
        bool,
        typer.Option(
            "--autonomous",
            help="使用通用 prompt，并关闭 Runner 的循环提醒。",
        ),
    ] = False,
    guarded: Annotated[
        bool,
        typer.Option(
            "--guarded",
            help="注入仅基于公开 Observation 的动作候选提示，并单独记录该实验变量。",
        ),
    ] = False,
    reasoning_effort: Annotated[
        str | None,
        typer.Option(
            "--reasoning-effort",
            help="Responses API 推理强度：none、low、medium、high。",
        ),
    ] = None,
    recent_history: Annotated[
        int,
        typer.Option("--recent-history", min=0, help="向模型提供最近 N 步公开轨迹。"),
    ] = 0,
    structured_milestones: Annotated[
        bool,
        typer.Option("--structured-milestones", help="启用结构化公开里程碑记忆。"),
    ] = False,
    semantic_guard: Annotated[
        bool,
        typer.Option(
            "--semantic-guard",
            help="只依据公开 Observation 拒绝出口、可见目标和背包不合法的 Action。",
        ),
    ] = False,
    stuck_recovery: Annotated[
        bool,
        typer.Option("--stuck-recovery", help="启用公开轨迹循环检测和恢复提醒。"),
    ] = False,
    candidate_actions: Annotated[
        bool,
        typer.Option("--candidate-actions", help="列出当前 Observation 可构造的具体 Action。"),
    ] = False,
    phase_context: Annotated[
        bool,
        typer.Option("--phase-context", help="注入由公开里程碑生成的阶段状态。"),
    ] = False,
) -> None:
    """运行并保存一局受步数限制的飞船逃生实验。"""

    if autonomous and guarded:
        typer.echo("--autonomous 不能与 --guarded 同时使用。", err=True)
        raise typer.Exit(code=2)
    if memory_version == "v3_spatial_event" and agent not in {None, "memory"}:
        typer.echo("--memory-version v3_spatial_event 需要 --agent memory。", err=True)
        raise typer.Exit(code=2)
    settings = _load_settings(
        provider=provider,
        agent=agent,
        seed=seed,
        world=world,
        world_version=world_version,
        runs_dir=output_dir,
        reasoning_effort=reasoning_effort,
        memory_version=memory_version,
        step_limit=step_limit,
        max_provider_requests=max_provider_requests,
        max_provider_tokens=max_provider_tokens,
        max_provider_output_tokens=max_provider_output_tokens,
        provider_budget_timeout_seconds=provider_budget_timeout_seconds,
        provider_budget_experiment_id=provider_budget_experiment_id,
        provider_budget_expected_provider=provider_budget_expected_provider,
        provider_budget_expected_model=provider_budget_expected_model,
        provider_budget_expected_world_definition_hash=provider_budget_expected_world_definition_hash,
        provider_budget_expected_base_prompt_hash=provider_budget_expected_base_prompt_hash,
        provider_budget_ledger=provider_budget_ledger,
    )
    if autonomous and settings.agent in {"planner_assisted", "candidate_select"}:
        typer.echo(
            "--autonomous 只适用于 react 或 memory，不能与辅助 Agent 同时使用。",
            err=True,
        )
        raise typer.Exit(code=2)
    environment = _load_environment(settings)
    budget_controller: ProviderBudgetController | None = None
    budget_snapshot: ProviderBudgetSnapshot | None = None
    try:
        _validate_budget_world_identity(settings, environment)
        budget_controller = _create_provider_budget_controller(settings)
        decision_provider = _create_decision_provider(
            settings,
            budget_controller=budget_controller,
            budget_context=f"{settings.agent}:seed={settings.seed}:{settings.memory_version}",
        )
        agent_instance = _create_agent(
            settings.agent,
            decision_provider,
            structured_milestones=structured_milestones,
            memory_version=settings.memory_version,
        )
        _validate_budget_prompt_identity(settings, agent_instance.base_prompt_hash)
        invocation_context = (
            budget_controller.invocation_lease()
            if budget_controller is not None
            else nullcontext()
        )
        with invocation_context:
            episode = EpisodeRunner(
                environment,
                agent_instance,
                settings,
                on_decision_start=_real_model_step_report(settings),
                on_step_complete=_step_report(),
                enable_runtime_feedback=not autonomous or stuck_recovery,
                enable_public_action_hints=guarded,
                recent_history_window=recent_history,
                enable_structured_milestones=structured_milestones,
                enable_public_action_guard=semantic_guard,
                enable_stuck_recovery=not autonomous or stuck_recovery,
                enable_concrete_action_candidates=candidate_actions,
                enable_public_phase_context=phase_context,
                enable_candidate_selection=settings.agent == "candidate_select",
            ).run()
            if budget_controller is not None:
                budget_snapshot = budget_controller.snapshot()
    except ProviderBudgetExceeded as exc:
        typer.echo(f"预算门禁停止：{exc}", err=True)
        if budget_controller is not None:
            budget = budget_controller.snapshot()
            typer.echo(
                f"预算用量：{budget.requests_used}/{budget.max_requests} 个 provider 请求，"
                f"{budget.tokens_used}/{budget.max_tokens} tokens；"
                f"closed_reason={budget.closed_reason or 'none'}。",
                err=True,
            )
        raise typer.Exit(code=2) from None
    except ValueError:
        typer.echo("实验启动失败，请检查模型服务配置。", err=True)
        raise typer.Exit(code=2) from None

    if settings.provider in {"bailian", "openai", "ollama"}:
        typer.echo(
            f"真实模型实验开始：Agent={settings.agent}，seed={settings.seed}，"
            f"{_format_step_budget(settings.step_limit)}。"
        )
    episode_path = write_episode_trace(episode, settings.runs_dir)
    typer.echo(f"本局结果：{_OUTCOME_LABELS[episode.outcome]}")
    typer.echo(f"已执行动作：{episode.executed_action_count}")
    typer.echo(f"无效模型输出：{episode.invalid_output_count}")
    typer.echo(f"运行记录：{episode_path}")
    if budget_controller is not None:
        budget = budget_snapshot or budget_controller.snapshot()
        typer.echo(
            f"预算用量：{budget.requests_used}/{budget.max_requests} 个 provider 请求，"
            f"{budget.tokens_used}/{budget.max_tokens} tokens。"
        )


@app.command()
def benchmark(
    episodes: Annotated[int, typer.Option("--episodes", min=1)] = 1,
    provider: Annotated[str | None, typer.Option("--provider")] = None,
    agent: Annotated[str | None, typer.Option("--agent")] = None,
    memory_version: Annotated[
        str | None,
        typer.Option("--memory-version", help="MemoryAgent 记忆策略：v2 或 v3_spatial_event。"),
    ] = None,
    output_dir: Annotated[Path | None, typer.Option("--output-dir")] = None,
    seed: Annotated[int | None, typer.Option("--seed")] = None,
    world: Annotated[str | None, typer.Option("--world")] = None,
    world_version: Annotated[str | None, typer.Option("--world-version")] = None,
    step_limit: Annotated[int | None, typer.Option("--step-limit", min=1)] = None,
    max_provider_requests: Annotated[
        int | None,
        typer.Option("--provider-request-budget", min=1),
    ] = None,
    max_provider_tokens: Annotated[
        int | None,
        typer.Option("--provider-token-budget", min=1),
    ] = None,
    max_provider_output_tokens: Annotated[
        int | None,
        typer.Option("--provider-output-token-cap", min=1),
    ] = None,
    provider_budget_timeout_seconds: Annotated[
        int | None,
        typer.Option("--provider-budget-timeout-seconds", min=1),
    ] = None,
    provider_budget_experiment_id: Annotated[
        str | None,
        typer.Option("--provider-budget-experiment-id"),
    ] = None,
    provider_budget_expected_provider: Annotated[
        str | None,
        typer.Option("--provider-budget-expected-provider"),
    ] = None,
    provider_budget_expected_model: Annotated[
        str | None,
        typer.Option("--provider-budget-expected-model"),
    ] = None,
    provider_budget_expected_world_definition_hash: Annotated[
        str | None,
        typer.Option("--provider-budget-expected-world-hash"),
    ] = None,
    provider_budget_expected_base_prompt_hash: Annotated[
        str | None,
        typer.Option("--provider-budget-expected-prompt-hash"),
    ] = None,
    provider_budget_ledger: Annotated[
        Path | None,
        typer.Option("--provider-budget-ledger"),
    ] = None,
    autonomous: Annotated[
        bool,
        typer.Option(
            "--autonomous",
            help="使用通用 prompt，并关闭 Runner 的循环提醒。",
        ),
    ] = False,
    guarded: Annotated[
        bool,
        typer.Option(
            "--guarded",
            help="注入仅基于公开 Observation 的动作候选提示，并单独记录该实验变量。",
        ),
    ] = False,
    reasoning_effort: Annotated[
        str | None,
        typer.Option(
            "--reasoning-effort",
            help="Responses API 推理强度：none、low、medium、high。",
        ),
    ] = None,
    recent_history: Annotated[
        int,
        typer.Option("--recent-history", min=0, help="向模型提供最近 N 步公开轨迹。"),
    ] = 0,
    structured_milestones: Annotated[
        bool,
        typer.Option("--structured-milestones", help="启用结构化公开里程碑记忆。"),
    ] = False,
    semantic_guard: Annotated[
        bool,
        typer.Option(
            "--semantic-guard",
            help="只依据公开 Observation 拒绝出口、可见目标和背包不合法的 Action。",
        ),
    ] = False,
    stuck_recovery: Annotated[
        bool,
        typer.Option("--stuck-recovery", help="启用公开轨迹循环检测和恢复提醒。"),
    ] = False,
    candidate_actions: Annotated[
        bool,
        typer.Option("--candidate-actions", help="列出当前 Observation 可构造的具体 Action。"),
    ] = False,
    phase_context: Annotated[
        bool,
        typer.Option("--phase-context", help="注入由公开里程碑生成的阶段状态。"),
    ] = False,
) -> None:
    """重复运行 Agent 对照，并写入 JSON、CSV 指标。"""

    supported_agents = {
        "react",
        "memory",
        "planning",
        "planner_assisted",
        "candidate_select",
        "both",
    }
    if agent is not None and agent not in supported_agents:
        typer.echo(
            "Agent 必须是 react、memory、planner_assisted、candidate_select 或 both。\n"
            "另支持 planning。",
            err=True,
        )
        raise typer.Exit(code=2)
    if autonomous and guarded:
        typer.echo("--autonomous 不能与 --guarded 同时使用。", err=True)
        raise typer.Exit(code=2)
    if memory_version == "v3_spatial_event" and agent != "memory":
        typer.echo("--memory-version v3_spatial_event 需要 --agent memory。", err=True)
        raise typer.Exit(code=2)
    if autonomous and agent in {"planner_assisted", "candidate_select"}:
        typer.echo(
            "--autonomous 只适用于 react 或 memory，不能与辅助 Agent 同时使用。",
            err=True,
        )
        raise typer.Exit(code=2)
    settings = _load_settings(
        provider=provider,
        agent=agent if agent != "both" else None,
        seed=seed,
        world=world,
        world_version=world_version,
        reasoning_effort=reasoning_effort,
        memory_version=memory_version,
        step_limit=step_limit,
        max_provider_requests=max_provider_requests,
        max_provider_tokens=max_provider_tokens,
        max_provider_output_tokens=max_provider_output_tokens,
        provider_budget_timeout_seconds=provider_budget_timeout_seconds,
        provider_budget_experiment_id=provider_budget_experiment_id,
        provider_budget_expected_provider=provider_budget_expected_provider,
        provider_budget_expected_model=provider_budget_expected_model,
        provider_budget_expected_world_definition_hash=provider_budget_expected_world_definition_hash,
        provider_budget_expected_base_prompt_hash=provider_budget_expected_base_prompt_hash,
        provider_budget_ledger=provider_budget_ledger,
    )
    benchmark_id = str(uuid4())
    rows: list[BenchmarkRow] = []
    total_episodes = episodes * (2 if agent in {None, "both"} else 1)
    budget_controller: ProviderBudgetController | None = None
    budget_snapshot: ProviderBudgetSnapshot | None = None
    try:
        _validate_budget_world_identity(settings, _load_environment(settings))
        selected_agents: tuple[str, ...]
        if agent in {None, "both"}:
            selected_agents = ("react", "memory")
        else:
            assert agent is not None
            selected_agents = (agent,)
        total_episodes = len(selected_agents) * episodes
        budget_controller = _create_provider_budget_controller(settings)
        if budget_controller is not None and budget_controller.should_stop:
            raise ProviderBudgetExceeded(
                "The registered experiment budget is already closed or exhausted."
            )
        invocation_context = (
            budget_controller.invocation_lease()
            if budget_controller is not None
            else nullcontext()
        )
        interrupted_by_budget = False
        with invocation_context:
            typer.echo(
                f"基准测试开始：共 {total_episodes} 局，Agent={','.join(selected_agents)}，"
                f"{_format_step_budget(settings.step_limit)}。"
            )
            for selected_agent in selected_agents:
                for seed_offset in range(episodes):
                    if budget_controller is not None and budget_controller.should_stop:
                        break
                    episode_settings = settings.model_copy(
                        update={"agent": selected_agent, "seed": settings.seed + seed_offset}
                    )
                    episode_number = len(rows) + 1
                    typer.echo(
                        f"[{episode_number}/{total_episodes}] 开始："
                        f"Agent={selected_agent}，seed={episode_settings.seed}。"
                    )
                    try:
                        decision_provider = _create_decision_provider(
                            episode_settings,
                            budget_controller=budget_controller,
                            budget_context=(
                                f"{episode_settings.agent}:seed={episode_settings.seed}:"
                                f"{episode_settings.memory_version}"
                            ),
                        )
                        episode_environment = _load_environment(episode_settings)
                        episode_agent = _create_agent(
                            episode_settings.agent,
                            decision_provider,
                            structured_milestones=structured_milestones,
                            memory_version=episode_settings.memory_version,
                        )
                        _validate_budget_world_identity(episode_settings, episode_environment)
                        _validate_budget_prompt_identity(
                            episode_settings, episode_agent.base_prompt_hash
                        )
                        trace = EpisodeRunner(
                            episode_environment,
                            episode_agent,
                            episode_settings,
                            on_decision_start=_real_model_step_report(
                                episode_settings,
                                prefix=f"[{episode_number}/{total_episodes}] ",
                            ),
                            on_step_complete=_step_report(
                                prefix=f"[{episode_number}/{total_episodes}] "
                            ),
                            enable_runtime_feedback=not autonomous or stuck_recovery,
                            enable_public_action_hints=guarded,
                            recent_history_window=recent_history,
                            enable_structured_milestones=structured_milestones,
                            enable_public_action_guard=semantic_guard,
                            enable_stuck_recovery=not autonomous or stuck_recovery,
                            enable_concrete_action_candidates=candidate_actions,
                            enable_public_phase_context=phase_context,
                            enable_candidate_selection=episode_settings.agent == "candidate_select",
                        ).run()
                    except ProviderBudgetExceeded as exc:
                        typer.echo(f"预算门禁停止本局：{exc}", err=True)
                        if budget_controller is None:
                            raise
                        interrupted_by_budget = True
                        break
                    trace_path = write_episode_trace(trace, episode_settings.runs_dir)
                    rows.append(
                        row_from_trace(read_episode_trace(trace_path), benchmark_id, len(rows))
                    )
                    typer.echo(
                        f"[{episode_number}/{total_episodes}] 完成："
                        f"{_OUTCOME_LABELS[trace.outcome]}，已执行 "
                        f"{trace.executed_action_count} 步，模型请求耗时 {trace.latency_ms} ms。"
                    )
                    typer.echo(f"[{episode_number}/{total_episodes}] 运行记录：{trace_path}")
                if interrupted_by_budget or (
                    budget_controller is not None and budget_controller.should_stop
                ):
                    break
            if budget_controller is not None:
                budget_snapshot = budget_controller.snapshot()
    except (ValueError, ProviderBudgetExceeded):
        typer.echo("基准测试启动失败，请检查模型服务配置。", err=True)
        raise typer.Exit(code=2) from None

    json_path, csv_path = write_benchmark(rows, output_dir or settings.results_dir)
    is_complete = len(rows) == total_episodes
    typer.echo(
        f"基准测试{'完成' if is_complete else '提前停止'}：{benchmark_id}"
        f"（{len(rows)}/{total_episodes} 局完成）"
    )
    typer.echo(f"JSON 结果：{json_path}")
    typer.echo(f"CSV 结果：{csv_path}")
    if budget_controller is not None:
        budget = budget_snapshot or budget_controller.snapshot()
        typer.echo(
            f"预算用量：{budget.requests_used}/{budget.max_requests} 个 provider 请求，"
            f"{budget.tokens_used}/{budget.max_tokens} tokens；"
            f"closed_reason={budget.closed_reason or 'none'}。"
        )
        if not is_complete:
            raise typer.Exit(code=2)


@app.command(name="analyze-trace")
def analyze_trace_command(
    trace_path: Annotated[Path, typer.Argument(help="一个 JSON Episode Trace 路径。")],
) -> None:
    """分析一个 Episode Trace 中的自动失败信号和公开进展。"""

    try:
        analysis = analyze_trace(read_episode_trace(trace_path))
    except (OSError, ValueError):
        typer.echo("Trace 读取失败：请提供可读取的 JSON Episode Trace。", err=True)
        raise typer.Exit(code=2) from None
    _print_failure_analysis(analysis)


@app.command(name="analyze-traces")
def analyze_traces_command(
    traces_path: Annotated[Path, typer.Argument(help="Trace 文件或目录。")],
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", help="报告输出目录，默认写入输入目录。"),
    ] = None,
) -> None:
    """批量分析 Trace，并写入 failure_analysis JSON/CSV。"""

    paths = _trace_paths(traces_path)
    if not paths:
        typer.echo("未找到可分析的 Episode Trace。", err=True)
        raise typer.Exit(code=2)
    analyses: list[FailureAnalysis] = []
    for path in paths:
        try:
            analyses.append(analyze_trace(read_episode_trace(path)))
        except (OSError, ValueError):
            # Directories may contain benchmark manifests beside episode
            # traces. They are not episode inputs and are skipped safely.
            continue
    if not analyses:
        typer.echo("未找到可分析的 Episode Trace。", err=True)
        raise typer.Exit(code=2)
    destination = output_dir or (traces_path.parent if traces_path.is_file() else traces_path)
    json_path, csv_path = write_failure_analysis(analyses, destination)
    typer.echo(f"已分析 Episode：{len(analyses)}")
    typer.echo(f"JSON 结果：{json_path}")
    typer.echo(f"CSV 结果：{csv_path}")


@app.command(name="verify-model")
def verify_model(
    provider: Annotated[str, typer.Option("--provider")] = "bailian",
) -> None:
    """显式验证远程 provider 或 Ollama，并只显示模型名和最终回复。"""

    if provider not in {"bailian", "openai", "ollama"}:
        typer.echo("验证 provider 必须是 ollama、bailian 或 openai。", err=True)
        raise typer.Exit(code=2)
    try:
        settings = RuntimeSettings.load({"provider": provider})
        verification = (
            OllamaModelVerifier(settings).verify()
            if settings.provider == "ollama"
            else (
                OpenAIModelVerifier(settings).verify()
                if settings.provider == "openai"
                else BailianModelVerifier(settings).verify()
            )
        )
    except (ModelVerificationError, ValueError):
        if provider == "ollama":
            typer.echo("Ollama 模型验证失败，请检查服务、模型名称和网络。", err=True)
        else:
            typer.echo("模型验证失败，请检查端点、密钥和网络。", err=True)
        raise typer.Exit(code=1) from None

    typer.echo(f"模型：{verification.model}")
    typer.echo(f"回复：{verification.text}")


def _create_provider_budget_controller(
    settings: RuntimeSettings,
) -> ProviderBudgetController | None:
    if settings.max_provider_requests is None:
        return None
    assert settings.max_provider_tokens is not None
    assert settings.max_provider_output_tokens is not None
    assert settings.provider_budget_timeout_seconds is not None
    assert settings.provider_budget_experiment_id is not None
    assert settings.provider_budget_expected_provider is not None
    assert settings.provider_budget_expected_model is not None
    assert settings.provider_budget_expected_world_definition_hash is not None
    assert settings.provider_budget_expected_base_prompt_hash is not None
    assert settings.provider_budget_ledger is not None
    if settings.provider_budget_expected_model != settings.selected_model_name:
        raise ProviderBudgetExceeded(
            "The configured model does not match the frozen budget experiment."
        )
    if settings.provider_budget_expected_provider != settings.provider:
        raise ProviderBudgetExceeded(
            "The configured provider does not match the frozen budget experiment."
        )
    return ProviderBudgetController(
        ProviderBudgetLimits(
            experiment_id=settings.provider_budget_experiment_id,
            expected_provider=settings.provider_budget_expected_provider,
            expected_model=settings.provider_budget_expected_model,
            expected_world_definition_hash=settings.provider_budget_expected_world_definition_hash,
            expected_base_prompt_hash=settings.provider_budget_expected_base_prompt_hash,
            max_requests=settings.max_provider_requests,
            max_tokens=settings.max_provider_tokens,
            max_output_tokens_per_request=settings.max_provider_output_tokens,
            timeout_seconds=settings.provider_budget_timeout_seconds,
        ),
        settings.provider_budget_ledger,
    )


def _validate_budget_world_identity(
    settings: RuntimeSettings,
    environment: Environment,
) -> None:
    if settings.max_provider_requests is None:
        return
    expected_hash = settings.provider_budget_expected_world_definition_hash
    if expected_hash is not None and environment.identity[3] != expected_hash:
        raise ProviderBudgetExceeded(
            "The world definition hash does not match the budget registration."
        )


def _validate_budget_prompt_identity(settings: RuntimeSettings, prompt_hash: str) -> None:
    if settings.max_provider_requests is None:
        return
    expected_hash = settings.provider_budget_expected_base_prompt_hash
    if expected_hash is not None and prompt_hash != expected_hash:
        raise ProviderBudgetExceeded("The base prompt hash does not match the budget registration.")


def _create_decision_provider(
    settings: RuntimeSettings,
    *,
    budget_controller: ProviderBudgetController | None = None,
    budget_context: str = "",
) -> DecisionProvider:
    if settings.provider == "bailian":
        provider: DecisionProvider = BailianDecisionProvider(settings)
    elif settings.provider == "openai":
        provider = OpenAIDecisionProvider(settings)
    elif settings.provider == "ollama":
        provider = OllamaDecisionProvider(settings)
    else:
        provider = FakeDecisionProvider(_default_fake_responses(settings.agent))
    if budget_controller is None:
        return provider
    return BudgetedDecisionProvider(
        provider,
        budget_controller,
        context=budget_context,
        provider_name=settings.provider,
        model_name=settings.selected_model_name,
    )


def _create_agent(
    agent: str,
    provider: DecisionProvider,
    *,
    structured_milestones: bool = False,
    memory_version: Literal["v2", "v3_spatial_event"] = "v2",
) -> ReactAgent:
    if agent == "memory":
        return MemoryAgent(
            provider,
            structured_milestones=structured_milestones,
            memory_version=memory_version,
        )
    if agent == "planning":
        return PlanningAgent(provider)
    if agent == "planner_assisted":
        return PlannerAssistedAgent(provider)
    if agent == "candidate_select":
        return CandidateSelectionAgent(provider)
    return ReactAgent(provider)


def _trace_paths(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if not path.is_dir():
        return []
    return sorted(
        candidate
        for candidate in path.rglob("*.json")
        if candidate.name != "failure_analysis.json" and not candidate.name.startswith("benchmark_")
    )


def _print_failure_analysis(analysis: FailureAnalysis) -> None:
    signals = analysis.automatic_failure_signals
    typer.echo(f"Episode: {analysis.episode_id}")
    typer.echo(f"Outcome: {analysis.outcome}")
    typer.echo(f"Steps: {analysis.steps}")
    typer.echo("")
    typer.echo("Automatic failure signals:")
    typer.echo(f"Repeated inspection: {signals.repeated_inspection}")
    typer.echo(f"Repeated navigation: {signals.repeated_navigation}")
    typer.echo(f"Repeated failure: {signals.repeated_failure}")
    typer.echo(f"Invalid output: {signals.invalid_output}")
    typer.echo(f"Rejected action: {signals.rejected_action}")
    typer.echo("")
    typer.echo(f"State progress events: {analysis.state_progress_count}")
    typer.echo(f"Epistemic progress events: {analysis.epistemic_progress_count}")
    typer.echo(f"No-progress actions: {analysis.no_progress_action_count}")
    typer.echo(f"Unique public facts: {analysis.unique_public_fact_count}")
    if analysis.unavailable_metrics:
        typer.echo("Unavailable metrics (legacy trace): " + ", ".join(analysis.unavailable_metrics))
    typer.echo("")
    typer.echo(f"Planner calls: {analysis.planner_call_count}")
    typer.echo(f"Replans: {analysis.replan_count}")
    typer.echo(f"Planner call ratio: {analysis.planner_call_ratio:.3f}")
    typer.echo("")
    typer.echo("Manual annotation required:")
    if analysis.manual_annotation_required_steps:
        typer.echo(" ".join(f"step {step}" for step in analysis.manual_annotation_required_steps))
    else:
        typer.echo("none")


def _real_model_step_report(
    settings: RuntimeSettings,
    *,
    prefix: str = "",
) -> Callable[[int, bool], None] | None:
    if settings.provider not in {"bailian", "openai", "ollama"}:
        return None

    def report(step: int, correction: bool) -> None:
        phase = "格式修正" if correction else "决策"
        total = str(settings.step_limit) if settings.step_limit > 0 else "不限"
        typer.echo(
            f"{prefix}正在请求第 {step}/{total} 步{phase}："
            f"Agent={settings.agent}，seed={settings.seed}。"
        )

    return report


def _format_step_budget(step_limit: int) -> str:
    if step_limit == 0:
        return "步数不限"
    return f"每局最多 {step_limit} 步"


def _step_report(*, prefix: str = "") -> Callable[[StepTrace], None]:
    executed_actions = 0

    def report(step: StepTrace) -> None:
        nonlocal executed_actions
        if step.action is not None and step.result is not None:
            executed_actions += 1
            reason = step.decision_reason or "未提供简短理由"
            typer.echo(
                f"{prefix}第 {executed_actions} 步 | 理由：{reason} | "
                f"动作：{_format_action(step)} | "
                f"结果：{step.result.status}/{step.result.reason}，{step.result.summary}"
            )
        elif step.event in {TraceEvent.ACTION_INVALID, TraceEvent.PROVIDER_ERROR}:
            typer.echo(f"{prefix}步骤事件：{step.summary}")

    return report


def _format_action(step: StepTrace) -> str:
    assert step.action is not None
    action = step.action.model_dump(mode="json")
    tool = action.pop("tool")
    arguments = "，".join(f"{name}={value}" for name, value in action.items())
    return f"{tool}({arguments})" if arguments else f"{tool}()"


def _default_fake_responses(agent: str = "react") -> list[object]:
    """Provide a deterministic baseline path for a safe local CLI demonstration."""

    if agent == "planning":
        return _default_planning_fake_responses()

    actions = [
        {"tool": "move", "destination": "corridor"},
        {"tool": "move", "destination": "storage_room"},
        {"tool": "inspect", "target": "storage_crate"},
        {"tool": "pickup", "item": "screwdriver"},
        {"tool": "pickup", "item": "replacement_fuse"},
        {"tool": "move", "destination": "corridor"},
        {"tool": "move", "destination": "maintenance_room"},
        {"tool": "read_terminal", "target": "diagnostic_terminal"},
        {"tool": "move", "destination": "reactor_room"},
        {"tool": "use", "item": "screwdriver", "target": "reactor_panel"},
        {"tool": "use", "item": "replacement_fuse", "target": "damaged_fuse"},
        {"tool": "move", "destination": "maintenance_room"},
        {"tool": "move", "destination": "corridor"},
        {"tool": "move", "destination": "control_room"},
        {"tool": "read_terminal", "target": "control_terminal"},
        {"tool": "move", "destination": "corridor"},
        {"tool": "move", "destination": "maintenance_room"},
        {"tool": "move", "destination": "reactor_room"},
        {"tool": "move", "destination": "escape_pod"},
        {"tool": "use", "item": "ALPHA-731", "target": "escape_pod"},
    ]
    return [
        {
            "decision_reason": "根据当前可见信息推进逃生路线。",
            "action": action,
        }
        for action in actions
    ]


def _default_planning_fake_responses() -> list[object]:
    """Interleave generic Planner decisions and the public escape path."""

    plans = [
        {
            "decision_reason": "先建立可公开验证的资源子目标。",
            "current_subgoal": "获得完成后续任务所需的公开资源",
            "success_criteria": ["inventory contains screwdriver replacement_fuse"],
            "known_constraints": [],
            "relevant_resources": [],
            "unresolved_questions": ["尚未知道完成最终任务还需要哪些公开步骤"],
        },
        {
            "decision_reason": "资源已满足，转向公开结果可验证的系统恢复目标。",
            "current_subgoal": "恢复系统功能",
            "success_criteria": ["ToolResult reason is power_restored"],
            "known_constraints": [],
            "relevant_resources": ["screwdriver", "replacement_fuse"],
            "unresolved_questions": [],
        },
        {
            "decision_reason": "系统已恢复，转向获取公开授权信息。",
            "current_subgoal": "获得公开授权信息",
            "success_criteria": ["ToolResult reason is code_read"],
            "known_constraints": [],
            "relevant_resources": [],
            "unresolved_questions": [],
        },
        {
            "decision_reason": "授权信息已公开，完成最终目标。",
            "current_subgoal": "完成最终公开目标",
            "success_criteria": ["ToolResult reason is escaped"],
            "known_constraints": [],
            "relevant_resources": [],
            "unresolved_questions": [],
        },
    ]
    actions = _default_fake_responses()
    responses: list[object] = []
    action_index = 0
    for boundary, plan in zip((5, 11, 15, 20), plans, strict=True):
        responses.append(plan)
        responses.extend(actions[action_index:boundary])
        action_index = boundary
    return responses


_OUTCOME_LABELS: dict[EpisodeOutcome, str] = {
    EpisodeOutcome.SUCCESS: "成功逃离飞船",
    EpisodeOutcome.STEP_LIMIT: "达到步数上限，未完成逃生",
    EpisodeOutcome.INVALID_ACTION_LIMIT: "连续输出格式错误，实验已停止",
    EpisodeOutcome.PROVIDER_ERROR: "模型服务请求失败，实验已停止",
}


def _load_environment(
    settings: RuntimeSettings,
) -> Environment:
    try:
        return create_environment(settings.world, settings.world_version, seed=settings.seed)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from None
