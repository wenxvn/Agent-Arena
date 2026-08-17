"""Command line entry points for local Agent Arena experiments."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from agent_arena.config import RuntimeSettings
from agent_arena.evaluation import ScaffoldEpisode, write_scaffold_episode
from agent_arena.llm.bailian import BailianModelVerifier, ModelVerificationError

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
    """Persist a scaffold episode using the safe Fake provider default."""

    settings = _load_settings(provider=provider, seed=seed, runs_dir=output_dir)
    if settings.provider != "fake":
        typer.echo(
            "Bailian episodes require the ReactAgent and Episode Runner, which are not built yet.",
            err=True,
        )
        raise typer.Exit(code=2)

    episode = ScaffoldEpisode.from_settings(settings)
    episode_path = write_scaffold_episode(episode, settings.runs_dir)
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
