from __future__ import annotations

import csv
import json
from pathlib import Path

from typer.testing import CliRunner

from agent_arena.cli import app
from agent_arena.config import RuntimeSettings

runner = CliRunner()


def _configure_defaults(monkeypatch, tmp_path: Path) -> Path:
    defaults_file = tmp_path / "runtime.defaults.json"
    defaults_file.write_text(
        json.dumps(
            {
                "provider": "fake",
                "world": "spaceship-escape",
                "world_version": "spaceship-escape-v2-zh",
                "agent": "react",
                "seed": 10,
                "runs_dir": str(tmp_path / "runs"),
                "results_dir": str(tmp_path / "results"),
                "step_limit": 30,
                "request_timeout_seconds": 30,
                "retry_count": 2,
                "retry_backoff_seconds": [1, 2],
                "enable_thinking": False,
                "model_name": "qwen3.7-plus",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(RuntimeSettings, "defaults_file", defaults_file)
    return defaults_file


def _benchmark_files(output_dir: Path) -> tuple[dict[str, object], list[dict[str, str]]]:
    json_paths = list(output_dir.glob("*.json"))
    csv_paths = list(output_dir.glob("*.csv"))
    assert len(json_paths) == 1
    assert len(csv_paths) == 1
    manifest = json.loads(json_paths[0].read_text(encoding="utf-8"))
    with csv_paths[0].open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return manifest, rows


def test_benchmark_writes_two_memory_episodes_in_stable_order(monkeypatch, tmp_path: Path) -> None:
    _configure_defaults(monkeypatch, tmp_path)
    output_dir = tmp_path / "benchmark"

    result = runner.invoke(
        app,
        ["benchmark", "--episodes", "2", "--agent", "memory", "--output-dir", str(output_dir)],
    )

    assert result.exit_code == 0
    manifest, csv_rows = _benchmark_files(output_dir)
    output_names = {path.name for path in output_dir.iterdir()}
    assert any(name.startswith("benchmark_") and name.endswith(".json") for name in output_names)
    assert any(name.startswith("benchmark_") and name.endswith(".csv") for name in output_names)
    assert [row["agent"] for row in csv_rows] == ["memory", "memory"]
    assert [row["episode_index"] for row in csv_rows] == ["0", "1"]
    assert [row["seed"] for row in csv_rows] == ["10", "11"]
    assert [row["outcome"] for row in csv_rows] == ["success", "success"]
    assert [row["agent"] for row in manifest["rows"]] == ["memory", "memory"]
    assert [row["episode_index"] for row in manifest["rows"]] == [0, 1]
    assert manifest["aggregates"] == {
        "attempted": 2,
        "succeeded": 2,
        "success_rate": 1.0,
        "mean_steps": 20.0,
        "mean_latency_ms": sum(int(row["latency_ms"]) for row in csv_rows) / 2,
        "mean_invalid_output_count": 0.0,
    }


def test_benchmark_defaults_to_react_and_memory_comparison(monkeypatch, tmp_path: Path) -> None:
    _configure_defaults(monkeypatch, tmp_path)
    output_dir = tmp_path / "benchmark"

    result = runner.invoke(app, ["benchmark", "--output-dir", str(output_dir)])

    assert result.exit_code == 0
    manifest, csv_rows = _benchmark_files(output_dir)
    assert [row["agent"] for row in csv_rows] == ["react", "memory"]
    assert [row["episode_index"] for row in csv_rows] == ["0", "1"]
    assert [row["seed"] for row in csv_rows] == ["10", "10"]
    assert manifest["aggregates"]["attempted"] == 2
    assert manifest["aggregates"]["success_rate"] == 1.0
    assert "基准测试开始：共 2 局" in result.output
    assert "[2/2] 完成：成功逃离飞船" in result.output
    assert "[2/2] 运行记录：" in result.output


def test_benchmark_rejects_unknown_agent(tmp_path: Path) -> None:
    result = runner.invoke(app, ["benchmark", "--agent", "unknown", "--output-dir", str(tmp_path)])

    assert result.exit_code == 2
    assert "Agent 必须是 react、memory、planner_assisted 或 both。" in result.output
