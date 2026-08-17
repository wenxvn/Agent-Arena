"""Command line entry points for local Agent Arena experiments."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from agent_arena.agents import ReactAgent
from agent_arena.config import RuntimeSettings
from agent_arena.evaluation import EpisodeOutcome, EpisodeRunner, write_episode_trace
from agent_arena.llm import BailianDecisionProvider, DecisionProvider, FakeDecisionProvider
from agent_arena.llm.bailian import BailianModelVerifier, ModelVerificationError
from agent_arena.worlds import SpaceshipEscapeEnvironment

app = typer.Typer(help="运行本地 Agent Arena 实验。", no_args_is_help=True)


def _load_settings(
    provider: str | None = None,
    seed: int | None = None,
    runs_dir: Path | None = None,
) -> RuntimeSettings:
    return RuntimeSettings.load(
        {
            "provider": provider,
            "seed": seed,
            "runs_dir": runs_dir,
        }
    )


@app.command()
def run(
    provider: Annotated[str | None, typer.Option("--provider")] = None,
    seed: Annotated[int | None, typer.Option("--seed")] = None,
    output_dir: Annotated[Path | None, typer.Option("--output-dir")] = None,
) -> None:
    """运行并保存一局受步数限制的飞船逃生实验。"""

    settings = _load_settings(provider=provider, seed=seed, runs_dir=output_dir)
    try:
        decision_provider = _create_decision_provider(settings)
    except ValueError:
        typer.echo("实验启动失败，请检查模型服务配置。", err=True)
        raise typer.Exit(code=2) from None

    episode = EpisodeRunner(
        SpaceshipEscapeEnvironment(seed=settings.seed),
        ReactAgent(decision_provider),
        settings,
    ).run()
    episode_path = write_episode_trace(episode, settings.runs_dir)
    typer.echo(f"本局结果：{_OUTCOME_LABELS[episode.outcome]}")
    typer.echo(f"已执行动作：{episode.executed_action_count}")
    typer.echo(f"无效模型输出：{episode.invalid_output_count}")
    typer.echo(f"运行记录：{episode_path}")


@app.command()
def benchmark(
    episodes: Annotated[int, typer.Option("--episodes", min=1)] = 1,
) -> None:
    """基准测试将在 Release 2 提供。"""

    del episodes
    typer.echo("基准测试计划在 Release 2 开发。", err=True)
    raise typer.Exit(code=2)


@app.command(name="verify-model")
def verify_model() -> None:
    """显式调用百炼，并只显示模型名和最终回复。"""

    try:
        settings = RuntimeSettings.load({"provider": "bailian"})
        verification = BailianModelVerifier(settings).verify()
    except (ModelVerificationError, ValueError):
        typer.echo("模型验证失败，请检查端点、密钥和网络。", err=True)
        raise typer.Exit(code=1) from None

    typer.echo(f"模型：{verification.model}")
    typer.echo(f"回复：{verification.text}")


def _create_decision_provider(settings: RuntimeSettings) -> DecisionProvider:
    if settings.provider == "bailian":
        return BailianDecisionProvider(settings)
    return FakeDecisionProvider(_default_fake_responses())


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
