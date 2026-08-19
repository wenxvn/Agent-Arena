"""Command line entry points for local Agent Arena experiments."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import typer

from agent_arena.agents import MemoryAgent, PlannerAssistedAgent, ReactAgent
from agent_arena.config import RuntimeSettings
from agent_arena.evaluation import (
    BenchmarkRow,
    EpisodeOutcome,
    EpisodeRunner,
    StepTrace,
    TraceEvent,
    read_episode_trace,
    row_from_trace,
    write_benchmark,
    write_episode_trace,
)
from agent_arena.llm import (
    BailianDecisionProvider,
    DecisionProvider,
    FakeDecisionProvider,
    OllamaDecisionProvider,
    OllamaModelVerifier,
)
from agent_arena.llm.bailian import BailianModelVerifier, ModelVerificationError
from agent_arena.llm.openai import OpenAIDecisionProvider, OpenAIModelVerifier
from agent_arena.worlds import SpaceshipEscapeEnvironment

app = typer.Typer(help="运行本地 Agent Arena 实验。", no_args_is_help=True)


def _load_settings(
    provider: str | None = None,
    agent: str | None = None,
    seed: int | None = None,
    runs_dir: Path | None = None,
    reasoning_effort: str | None = None,
) -> RuntimeSettings:
    return RuntimeSettings.load(
        {
            "provider": provider,
            "agent": agent,
            "seed": seed,
            "runs_dir": runs_dir,
            "reasoning_effort": reasoning_effort,
        }
    )


@app.command()
def run(
    provider: Annotated[str | None, typer.Option("--provider")] = None,
    agent: Annotated[str | None, typer.Option("--agent")] = None,
    seed: Annotated[int | None, typer.Option("--seed")] = None,
    output_dir: Annotated[Path | None, typer.Option("--output-dir")] = None,
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
) -> None:
    """运行并保存一局受步数限制的飞船逃生实验。"""

    if autonomous and guarded:
        typer.echo("--autonomous 不能与 --guarded 同时使用。", err=True)
        raise typer.Exit(code=2)
    settings = _load_settings(
        provider=provider,
        agent=agent,
        seed=seed,
        runs_dir=output_dir,
        reasoning_effort=reasoning_effort,
    )
    if autonomous and settings.agent == "planner_assisted":
        typer.echo(
            "--autonomous 只适用于 react 或 memory，不能与 planner_assisted 同时使用。",
            err=True,
        )
        raise typer.Exit(code=2)
    try:
        decision_provider = _create_decision_provider(settings)
    except ValueError:
        typer.echo("实验启动失败，请检查模型服务配置。", err=True)
        raise typer.Exit(code=2) from None

    if settings.provider in {"bailian", "openai", "ollama"}:
        typer.echo(
            f"真实模型实验开始：Agent={settings.agent}，seed={settings.seed}，"
            f"每局最多 {settings.step_limit} 步。"
        )
    episode = EpisodeRunner(
        SpaceshipEscapeEnvironment(seed=settings.seed),
        _create_agent(settings.agent, decision_provider),
        settings,
        on_decision_start=_real_model_step_report(settings),
        on_step_complete=_step_report(),
        enable_runtime_feedback=not autonomous,
        enable_public_action_hints=guarded,
    ).run()
    episode_path = write_episode_trace(episode, settings.runs_dir)
    typer.echo(f"本局结果：{_OUTCOME_LABELS[episode.outcome]}")
    typer.echo(f"已执行动作：{episode.executed_action_count}")
    typer.echo(f"无效模型输出：{episode.invalid_output_count}")
    typer.echo(f"运行记录：{episode_path}")


@app.command()
def benchmark(
    episodes: Annotated[int, typer.Option("--episodes", min=1)] = 1,
    provider: Annotated[str | None, typer.Option("--provider")] = None,
    agent: Annotated[str | None, typer.Option("--agent")] = None,
    output_dir: Annotated[Path | None, typer.Option("--output-dir")] = None,
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
) -> None:
    """重复运行 Agent 对照，并写入 JSON、CSV 指标。"""

    if agent is not None and agent not in {"react", "memory", "planner_assisted", "both"}:
        typer.echo("Agent 必须是 react、memory、planner_assisted 或 both。", err=True)
        raise typer.Exit(code=2)
    if autonomous and guarded:
        typer.echo("--autonomous 不能与 --guarded 同时使用。", err=True)
        raise typer.Exit(code=2)
    if autonomous and agent == "planner_assisted":
        typer.echo(
            "--autonomous 只适用于 react 或 memory，不能与 planner_assisted 同时使用。",
            err=True,
        )
        raise typer.Exit(code=2)
    settings = _load_settings(provider=provider, reasoning_effort=reasoning_effort)
    benchmark_id = str(uuid4())
    rows: list[BenchmarkRow] = []
    try:
        selected_agents: tuple[str, ...]
        if agent in {None, "both"}:
            selected_agents = ("react", "memory")
        else:
            assert agent is not None
            selected_agents = (agent,)
        total_episodes = len(selected_agents) * episodes
        typer.echo(
            f"基准测试开始：共 {total_episodes} 局，Agent={','.join(selected_agents)}，"
            f"每局最多 {settings.step_limit} 步。"
        )
        for selected_agent in selected_agents:
            for seed_offset in range(episodes):
                episode_settings = settings.model_copy(
                    update={"agent": selected_agent, "seed": settings.seed + seed_offset}
                )
                episode_number = len(rows) + 1
                typer.echo(
                    f"[{episode_number}/{total_episodes}] 开始："
                    f"Agent={selected_agent}，seed={episode_settings.seed}。"
                )
                decision_provider = _create_decision_provider(episode_settings)
                trace = EpisodeRunner(
                    SpaceshipEscapeEnvironment(seed=episode_settings.seed),
                    _create_agent(episode_settings.agent, decision_provider),
                    episode_settings,
                    on_decision_start=_real_model_step_report(
                        episode_settings,
                        prefix=f"[{episode_number}/{total_episodes}] ",
                    ),
                    on_step_complete=_step_report(prefix=f"[{episode_number}/{total_episodes}] "),
                    enable_runtime_feedback=not autonomous,
                    enable_public_action_hints=guarded,
                ).run()
                trace_path = write_episode_trace(trace, episode_settings.runs_dir)
                rows.append(row_from_trace(read_episode_trace(trace_path), benchmark_id, len(rows)))
                typer.echo(
                    f"[{episode_number}/{total_episodes}] 完成："
                    f"{_OUTCOME_LABELS[trace.outcome]}，已执行 {trace.executed_action_count} 步，"
                    f"模型请求耗时 {trace.latency_ms} ms。"
                )
                typer.echo(f"[{episode_number}/{total_episodes}] 运行记录：{trace_path}")
    except ValueError:
        typer.echo("基准测试启动失败，请检查模型服务配置。", err=True)
        raise typer.Exit(code=2) from None

    json_path, csv_path = write_benchmark(rows, output_dir or settings.results_dir)
    typer.echo(f"基准测试完成：{benchmark_id}")
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


def _create_decision_provider(settings: RuntimeSettings) -> DecisionProvider:
    if settings.provider == "bailian":
        return BailianDecisionProvider(settings)
    if settings.provider == "openai":
        return OpenAIDecisionProvider(settings)
    if settings.provider == "ollama":
        return OllamaDecisionProvider(settings)
    return FakeDecisionProvider(_default_fake_responses())


def _create_agent(agent: str, provider: DecisionProvider) -> ReactAgent:
    if agent == "memory":
        return MemoryAgent(provider)
    if agent == "planner_assisted":
        return PlannerAssistedAgent(provider)
    return ReactAgent(provider)


def _real_model_step_report(
    settings: RuntimeSettings,
    *,
    prefix: str = "",
) -> Callable[[int, bool], None] | None:
    if settings.provider not in {"bailian", "openai", "ollama"}:
        return None

    def report(step: int, correction: bool) -> None:
        phase = "格式修正" if correction else "决策"
        typer.echo(
            f"{prefix}正在请求第 {step}/{settings.step_limit} 步{phase}："
            f"Agent={settings.agent}，seed={settings.seed}。"
        )

    return report


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


def _default_fake_responses() -> list[object]:
    """Provide a deterministic baseline path for a safe local CLI demonstration."""

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


_OUTCOME_LABELS: dict[EpisodeOutcome, str] = {
    EpisodeOutcome.SUCCESS: "成功逃离飞船",
    EpisodeOutcome.STEP_LIMIT: "达到步数上限，未完成逃生",
    EpisodeOutcome.INVALID_ACTION_LIMIT: "连续输出格式错误，实验已停止",
    EpisodeOutcome.PROVIDER_ERROR: "模型服务请求失败，实验已停止",
}
