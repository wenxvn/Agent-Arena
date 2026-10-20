"""V11 存储层：原子写、JSONL、损坏容错与路径限制。"""

from __future__ import annotations

import json

import pytest

from agent_arena.web.store import (
    CorruptRunError,
    RunNotFoundError,
    RunStore,
    atomic_write_json,
)


def test_atomic_manifest_roundtrip(tmp_path) -> None:
    store = RunStore(tmp_path / "web")
    manifest = {"run_id": "web-20260101T000000Z-abcdef12", "state": "QUEUED"}
    store.save_manifest(manifest)
    loaded = store.load_manifest(manifest["run_id"])
    assert loaded["state"] == "QUEUED"
    assert loaded["updated_at"]


def test_events_are_append_only_and_corrupt_lines_are_skipped(tmp_path) -> None:
    store = RunStore(tmp_path)
    run_id = "web-20260101T000000Z-abcdef12"
    store.run_dir(run_id, create=True)
    store.append_event(run_id, {"event": "run_created"})
    with (store.base / run_id / "events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write("{not json}\n")
    store.append_event(run_id, {"event": "decision", "decision_index": 1})
    events, skipped = store.read_events_with_diagnostics(run_id)
    assert [event["event"] for event in events] == ["run_created", "decision"]
    assert skipped == 1


def test_corrupt_manifest_is_reported(tmp_path) -> None:
    store = RunStore(tmp_path)
    run_id = "web-20260101T000000Z-abcdef12"
    directory = store.run_dir(run_id, create=True)
    (directory / "manifest.json").write_text("{broken", encoding="utf-8")
    with pytest.raises(CorruptRunError):
        store.load_manifest(run_id)
    manifests, broken = store.discover()
    assert manifests == []
    assert broken == [run_id]


def test_run_directory_traversal_is_rejected(tmp_path) -> None:
    store = RunStore(tmp_path)
    for bad in ("../escape", "..", "WEB-20260101T000000Z-abcdef12", "x/y"):
        with pytest.raises((RunNotFoundError, ValueError)):
            store.run_dir(bad)


def test_idempotency_lookup(tmp_path) -> None:
    store = RunStore(tmp_path)
    run_id = "web-20260101T000000Z-abcdef12"
    store.save_manifest({"run_id": run_id, "state": "QUEUED", "idempotency_key": "k1"})
    assert store.find_by_idempotency("k1") == run_id
    assert store.find_by_idempotency("k2") is None


def test_atomic_write_leaves_no_temporary_files(tmp_path) -> None:
    target = tmp_path / "x.json"
    atomic_write_json(target, {"a": 1})
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 1}
    assert [path.name for path in tmp_path.iterdir()] == ["x.json"]


def test_atomic_write_handles_decimal(tmp_path) -> None:
    from decimal import Decimal

    target = tmp_path / "decimal.json"
    atomic_write_json(target, {"cost": Decimal("0.10")})
    assert json.loads(target.read_text(encoding="utf-8")) == {"cost": "0.10"}


def test_global_ledger_roundtrip(tmp_path) -> None:
    store = RunStore(tmp_path)
    store.append_global_ledger({"event": "run_started", "run_id": "r1"})
    store.append_global_ledger({"event": "run_settled", "run_id": "r1"})
    assert [row["event"] for row in store.read_global_ledger()] == [
        "run_started",
        "run_settled",
    ]
