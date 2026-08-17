"""Command line entry points for local Agent Arena experiments."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from agent_arena.agents import ReactAgent
from agent_arena.config import RuntimeSettings
from agent_arena.evaluation import EpisodeRunner, write_episode_trace
from agent_arena.llm import BailianDecisionProvider, DecisionProvider, FakeDecisionProvider
from agent_arena.llm.bailian import BailianModelVerifier, ModelVerificationError
from agent_arena.worlds import SpaceshipEscapeEnvironment

app = typer.Typer(help="Run local Agent Arena experiments.", no_args_is_help=True)


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
    """Run and persist one bounded Spaceship Escape episode."""

    settings = _load_settings(provider=provider, seed=seed, runs_dir=output_dir)
    try:
        decision_provider = _create_decision_provider(settings)
    except ValueError:
        typer.echo("Episode startup failed. Check provider configuration.", err=True)
        raise typer.Exit(code=2) from None

    episode = EpisodeRunner(
        SpaceshipEscapeEnvironment(seed=settings.seed),
        ReactAgent(decision_provider),
        settings,
    ).run()
    episode_path = write_episode_trace(episode, settings.runs_dir)
    typer.echo(f"Episode trace: {episode_path}")


@app.command()
def benchmark(
    episodes: Annotated[int, typer.Option("--episodes", min=1)] = 1,
) -> None:
    """Reserve the benchmark command until Release 2 metrics are available."""

    del episodes
    typer.echo("Benchmark is scheduled for Release 2.", err=True)
    raise typer.Exit(code=2)


@app.command(name="verify-model")
def verify_model() -> None:
    """Call Bailian explicitly and print only the model name and final text."""

    try:
        settings = RuntimeSettings.load({"provider": "bailian"})
        verification = BailianModelVerifier(settings).verify()
    except (ModelVerificationError, ValueError):
        typer.echo("Model verification failed. Check endpoint, credentials, and network.", err=True)
        raise typer.Exit(code=1) from None

    typer.echo(f"Model: {verification.model}")
    typer.echo(f"Response: {verification.text}")


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
            "decision_reason": "Use the public observation to advance the escape route.",
            "action": action,
        }
        for action in actions
    ]
