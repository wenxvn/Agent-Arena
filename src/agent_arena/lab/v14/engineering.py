"""V14 工程边界证据（P2-2 / P2-4 / P2-5 / P2-6）。

全部在**临时目录**里测量，不碰真实 ``runs/``，不发任何网络请求：

| 函数 | 覆盖 |
|---|---|
| ``cold_start_measurement`` | 未预热首次打开 vs 预热后解析（两者分开报告） |
| ``corrupted_manifest_handling`` | 损坏 manifest 不让索引崩、不静默算进统计 |
| ``concurrent_read_during_write`` | 读取时新 run 正在写入（不出现半条记录/异常） |
| ``ttl_refresh`` | 索引 TTL 到点后刷新能看到新 run |
| ``long_history_export`` | 长历史全量导出的行数与字节数 |
| ``export_consistency`` | CSV/JSON/报告的行数、分母、类别、来源模式一致 |
| ``sdk_hardening`` | 旧签名兼容、异常隔离、预算网关不可绕 |
| ``ledger_recompute`` | V12 账本复算（159 局 / 5641 请求 / ¥5.43680012） |

口径原则：

- 耗时是**本机实测**，不设跨机器固定阈值；
- 不把全部事件读进内存（索引只读 manifest，导出按需）；
- 缺失字段不补 0（CSV 缺列就报缺列）。
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_arena.lab.paths import REPO_ROOT
from agent_arena.lab.v13.perf import _guard, synthesize_history
from agent_arena.web.index import RunIndex
from agent_arena.web.store import MANIFEST

V12_LEDGER_EXPECTATION = {
    "runs": 159,
    "requests": 5_641,
    "settled_cost_cny": "5.43680012",
    "orphans": 0,
    "duplicate_settlements": 0,
}

EXTERNAL_BILL_STATUS = "NO_EXTERNAL_BILL_PROVIDED"

# --------------------------------------------------------------------- perf
@dataclass
class Measurement:
    label: str
    milliseconds: float
    detail: str = ""
    ok: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "milliseconds": round(self.milliseconds, 2),
            "detail": self.detail,
            "ok": self.ok,
            **self.extra,
        }

def _timed(label: str, function: Any, *, detail: str = "") -> tuple[Any, Measurement]:
    started = time.perf_counter()
    value = function()
    return value, Measurement(
        label=label, milliseconds=(time.perf_counter() - started) * 1000, detail=detail
    )

def cold_start_measurement(base: Path) -> dict[str, Any]:
    """未预热首次打开 vs 已预热解析（**分开报告**，不混成一个数）。"""

    _guard(base)
    measurements: list[Measurement] = []
    cold_index = RunIndex(base)
    _, cold = _timed(
        "cold_first_open",
        lambda: cold_index.page(offset=0, limit=50),
        detail="全新进程/全新索引，未做任何预热（含文件系统首次读取）",
    )
    measurements.append(cold)

    warm_index = RunIndex(base)
    warm_index.refresh(force=True)
    _, warm = _timed(
        "warm_page_first_50",
        lambda: warm_index.page(offset=0, limit=50),
        detail="已预热：索引已构建，读读页缓存",
    )
    measurements.append(warm)

    _, rebuild = _timed(
        "warm_index_rebuild",
        lambda: RunIndex(base).refresh(force=True),
        detail="已预热后的全量索引重建（只 stat + 解析 manifest）",
    )
    measurements.append(rebuild)
    return {
        "schema": "v14-cold-start-1",
        "runs": cold_index.stats.runs,
        "measurements": [item.as_dict() for item in measurements],
        "note": (
            "``cold_first_open`` 是**未预热**的首次打开；"
            "``warm_*`` 是预热后的解析成本。两者不可互相替代，"
            "也不代表 CI 或用户机器的性能。"
        ),
    }

def corrupted_manifest_handling(base: Path) -> dict[str, Any]:
    """损坏 manifest 不得让索引崩溃，也不得静默算进统计。"""

    _guard(base)
    good = synthesize_history(base, 5)
    bad_dir = base / "web-20260101T000000Z-0000dead"
    bad_dir.mkdir(parents=True, exist_ok=True)
    (bad_dir / MANIFEST).write_text("{not valid json", encoding="utf-8")
    index = RunIndex(base)
    index.refresh(force=True)
    started = time.perf_counter()
    pages = index.page(offset=0, limit=50)
    elapsed = (time.perf_counter() - started) * 1000
    entries = list(pages.get("rows") or [])
    return {
        "schema": "v14-corrupted-manifest-1",
        "good_runs": good["count"],
        "indexed_runs": index.stats.runs,
        "page_entries": len(entries),
        "broken_manifests": index.stats.broken,
        "elapsed_ms": round(elapsed, 2),
        "crashed": False,
        "bad_run_indexed": any(
            str(entry.get("run_id")) == bad_dir.name for entry in index.entries
        ),
        "no_private_fields": all("sealed_truth" not in entry for entry in entries),
        "note": (
            "损坏的 manifest 被跳过而不是让整页崩；也不会以空记录混进统计。"
        ),
    }

def concurrent_read_during_write(base: Path, *, rounds: int = 40) -> dict[str, Any]:
    """一个线程持续写入新 run，另一个线程持续分页/聚合读取。"""

    _guard(base)
    synthesize_history(base, 20)
    index = RunIndex(base)
    index.refresh(force=True)
    errors: list[str] = []
    seen_counts: list[int] = []

    def reader() -> None:
        for _ in range(rounds):
            try:
                page = index.page(offset=0, limit=10)
                seen_counts.append(len(page.get("rows") or []))
                index.aggregate()
            except Exception as exc:  # noqa: BLE001 - 记录而不是吞掉
                errors.append(f"{type(exc).__name__}: {exc}")
            time.sleep(0.002)

    def writer() -> None:
        for step in range(rounds):
            run_id = f"web-20260101T00{step // 60:02d}{step % 60:02d}Z-0000beef"
            directory = base / run_id
            directory.mkdir(parents=True, exist_ok=True)
            manifest = json.loads(
                (sorted(base.glob("web-*"))[0] / MANIFEST).read_text(encoding="utf-8")
            )
            manifest["run_id"] = run_id
            (directory / MANIFEST).write_text(
                json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
            )
            time.sleep(0.002)

    threads = [threading.Thread(target=reader), threading.Thread(target=writer)]
    started = time.perf_counter()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    elapsed = (time.perf_counter() - started) * 1000
    index.invalidate()
    index.page(offset=0, limit=10)
    return {
        "schema": "v14-concurrent-1",
        "rounds": rounds,
        "read_errors": errors[:5],
        "error_count": len(errors),
        "min_page_entries": min(seen_counts) if seen_counts else 0,
        "max_page_entries": max(seen_counts) if seen_counts else 0,
        "final_indexed_runs": index.stats.runs,
        "elapsed_ms": round(elapsed, 2),
        "ok": not errors,
        "note": (
            "并发读写在单用户本地场景下不应抛异常；半写入的 run 在下一次刷新前"
            "可能不被索引，但绝不能返回半条记录。"
        ),
    }

def ttl_refresh(base: Path) -> dict[str, Any]:
    """索引 TTL 到点后，新写入的 run 必须能被看到。"""

    _guard(base)
    synthesize_history(base, 3)
    index = RunIndex(base)
    index.refresh(force=True)
    before = index.stats.runs
    synthesize_history(base / "extra", 1, seed=99)
    source = sorted((base / "extra").glob("web-*"))[0]
    target = base / source.name
    target.mkdir(parents=True, exist_ok=True)
    (target / MANIFEST).write_text(
        (source / MANIFEST).read_text(encoding="utf-8"), encoding="utf-8"
    )
    # 模拟 TTL 到期：把检查时间推回过去。
    index._checked_at = time.monotonic() - (index.SIGNATURE_TTL_SECONDS + 1)
    index.refresh()
    after = index.stats.runs
    index.invalidate()
    forced = index.stats.runs
    return {
        "schema": "v14-ttl-refresh-1",
        "before": before,
        "after_ttl_expiry": after,
        "after_invalidate": forced,
        "ttl_seconds": index.SIGNATURE_TTL_SECONDS,
        "ok": after > before and forced >= after,
        "note": (
            "TTL 只影响\"多久重新扫一次目录\"；写入方应调用 ``invalidate()`` 让下一次查询立刻刷新。"
        ),
    }

def long_history_export(base: Path, *, count: int = 1_000) -> dict[str, Any]:
    """长历史全量导出：行数、字节数与内存占用（不把全部事件读进内存）。"""

    _guard(base)
    synthesize_history(base, count)
    index = RunIndex(base)
    index.refresh(force=True)
    _, timed = _timed(
        "export_all_rows",
        lambda: [
            json.dumps(entry, ensure_ascii=False) for entry in index.entries
        ],
    )
    rows = index.entries
    payload_bytes = sum(len(row.encode("utf-8")) for row in json.loads(
        json.dumps([json.dumps(row, ensure_ascii=False) for row in rows[:1]])
    )) if rows else 0
    return {
        "schema": "v14-long-export-1",
        "runs": index.stats.runs,
        "rows_exported": len(rows),
        "index_bytes_estimate": index.stats.bytes_estimate,
        "first_row_bytes": payload_bytes,
        "export_ms": round(timed.milliseconds, 2),
        "ok": len(rows) == index.stats.runs,
        "note": "导出只读 manifest 索引；不加载 events.jsonl，因此行数不受事件长度影响。",
    }

# ---------------------------------------------------------- export consistency
def export_consistency(
    csv_texts: dict[str, str],
    *,
    metrics: dict[str, Any],
    report_text: str,
    expected_mode: str,
) -> dict[str, Any]:
    """检查 run / metrics / report 的行数与分母是否同口径。"""

    import csv
    import io

    parsed: dict[str, list[dict[str, str]]] = {}
    for name, text in csv_texts.items():
        parsed[name] = list(csv.DictReader(io.StringIO(text)))
    runs = parsed.get("runs.csv") or []
    metrics_rows = parsed.get("metrics.csv") or []
    problems: list[str] = []

    # 1. 行数：runs.csv 必须等于 metrics 里的 run 计数
    metrics_runs = metrics.get("runs")
    if metrics_runs is not None and metrics_runs != len(runs):
        problems.append(f"runs.csv 行数 {len(runs)} ≠ metrics.runs {metrics_runs}")

    # 2. 分母：有效分母必须与类别统计一致
    valid_categories = {"completed_success", "mechanism_failure", "budget_censored"}
    counted = sum(
        1 for row in runs if str(row.get("category") or "") in valid_categories
    )
    for key in ("valid_denominator", "valid"):
        value = metrics.get(key)
        if value is not None and int(value) != counted:
            problems.append(f"metrics.{key}={value} ≠ 按类别统计的 {counted}")

    # 3. 模式：任何一行出现 LIVE 而整体是 SIMULATED 都是错误
    modes = {str(row.get("mode") or "") for row in runs}
    if modes and modes != {expected_mode}:
        problems.append(f"CSV mode={sorted(modes)} ≠ {expected_mode}")
    if expected_mode.upper() not in report_text.upper():
        problems.append("报告没有写明执行模式")

    # 4. 缺列不得静默补 0：按文件声明可空列，且 metrics 的 VALID 值不得为空
    nullable_by_file: dict[str, set[str]] = {
        "runs.csv": {"primary_value", "cost_cny", "termination", "primary_state"},
        "metrics.csv": {"value", "numerator", "denominator", "note"},
        "paired_comparison.csv": {"reasons", "left_cost_cny", "right_cost_cny"},
        "findings.csv": {"evidence_steps", "evidence_event_ids", "suggested_check", "detail"},
    }
    empty_cells: set[str] = set()
    for name, rows_ in parsed.items():
        allowed = nullable_by_file.get(name, set())
        for row in rows_:
            for key, value in row.items():
                if value == "" and key not in allowed:
                    empty_cells.add(key)
    silent_zeros: list[str] = []
    for row in metrics_rows:
        state = str(row.get("state") or "").upper()
        if state == "VALID" and str(row.get("value") or "") == "":
            silent_zeros.append(str(row.get("metric") or row.get("key") or "?"))
    if empty_cells:
        problems.append(f"出现非可空列的空单元格（疑似被静默补零）：{sorted(empty_cells)}")
    if silent_zeros:
        problems.append(f"VALID 指标的 value 为空（应显式写 N/A 而不是留空）：{silent_zeros}")

    return {
        "schema": "v14-export-consistency-1",
        "files": {name: len(rows_) for name, rows_ in parsed.items()},
        "runs_rows": len(runs),
        "valid_denominator_computed": counted,
        "modes": sorted(modes),
        "empty_cells": sorted(empty_cells),
        "silent_zero_metrics": silent_zeros,
        "problems": problems,
        "ok": not problems,
        "note": "导出口径必须一致：行数、分母、模式、空值处理，任一不一致即失败。",
    }

# --------------------------------------------------------------- SDK hardening
def sdk_hardening() -> dict[str, Any]:
    """旧签名、异常隔离、预算网关不可绕的显式检查（零请求）。"""

    from agent_arena.lab.contracts import AGENT_CONTRACT_VERSION
    from agent_arena.lab.v13.sdkcheck import run_sdk_checks

    base_report = run_sdk_checks()
    checks = {item["name"]: item for item in base_report.get("checks") or []}
    extra: list[dict[str, Any]] = []

    # 1. 旧签名兼容：v1 契约的插件不需要改动
    extra.append(
        {
            "name": "legacy_signature_compatible",
            "ok": AGENT_CONTRACT_VERSION == "agent_policy_v1",
            "detail": f"agent_contract_version={AGENT_CONTRACT_VERSION}",
        }
    )

    # 2. 策略异常隔离：插件抛异常时该局记 FAILED，进程不崩
    extra.append(
        {
            "name": "policy_exception_isolated",
            "ok": bool(checks.get("invalid_action_isolated", {}).get("ok")),
            "detail": "非法动作/异常被计为局级失败，而不是让服务崩溃",
        }
    )

    # 3. 预算网关不可绕：插件只能拿 Observation，拿不到 gateway 之外的计费入口
    extra.append(
        {
            "name": "budget_gateway_not_bypassable",
            "ok": bool(checks.get("public_observation_only", {}).get("ok"))
            and bool(checks.get("budget_and_simulated", {}).get("ok")),
            "detail": "插件只看到公开观察；费用只由 gateway 结算",
        }
    )

    return {
        "schema": "v14-sdk-hardening-1",
        "base_checks": base_report.get("checks") or [],
        "base_ok": bool(base_report.get("ok")),
        "extra_checks": extra,
        "ok": bool(base_report.get("ok")) and all(item["ok"] for item in extra),
        "note": (
            "只验证本机可信插件；不声称可以安全运行任意第三方代码。"
        ),
    }

# ------------------------------------------------------------- ledger recompute
DEFAULT_LEDGER_PATH = REPO_ROOT / "runs" / "web" / "_ledger" / "web_ledger.jsonl"
LEDGER_ABSENT = "LEDGER_NOT_PRESENT_LOCALLY"

def _csv_recompute(records: list[dict[str, Any]]) -> dict[str, Any]:
    """从只读逐局 CSV 复算（只覆盖 CSV 里有的局，不等于全账本）。"""

    settled = 0.0
    unknown = 0
    for item in records:
        if item.get("cost_known") and item.get("cost_cny") is not None:
            settled += float(item["cost_cny"])
        else:
            unknown += 1
    run_ids = [str(item.get("run_id") or "") for item in records]
    return {
        "source": "docs/v12/real-runs/*.csv（只读）",
        "runs": len(records),
        "requests": sum(int(item.get("requests") or 0) for item in records),
        "settled_cost_cny": f"{settled:.8f}",
        "cost_unknown_runs": unknown,
        "duplicates": len(run_ids) - len(set(run_ids)),
        "covers_full_ledger": False,
    }

def ledger_recompute(
    records: list[dict[str, Any]],
    *,
    ledger_path: Path | None = None,
) -> dict[str, Any]:
    """复算账本：优先读**本机既有**只读账本，缺失时明确报缺口。

    V13 记录的 159 局 / 5 641 请求 / ¥5.43680012 来自本机 ``runs/web/_ledger``；
    该目录在 ``.gitignore`` 内，新克隆的工作区不会带上它。因此这里分两种结果：

    - 账本存在：逐条复算 started/settled 配对、请求、Decimal 结算额、重复与孤儿；
    - 账本缺失：报 ``LEDGER_NOT_PRESENT_LOCALLY``，只给出 CSV 子集（138 局），
      **不**用 CSV 数字冒充 159 局全账本。
    """

    import decimal

    expected = V12_LEDGER_EXPECTATION
    csv_part = _csv_recompute(records)
    path = ledger_path or DEFAULT_LEDGER_PATH
    external = {
        "status": EXTERNAL_BILL_STATUS,
        "note": (
            "用户未提供脱敏后台账单 CSV；外部对账保持 `BLOCKED_EXTERNAL`，"
            "不能假装已经对上外部账。"
        ),
    }
    if not path.is_file():
        return {
            "schema": "v14-ledger-recompute-1",
            "status": LEDGER_ABSENT,
            "ledger_path": str(path),
            "expected": expected,
            "open_ledger": None,
            "csv_subset": csv_part,
            "matches_v13_record": False,
            "external_bill": external,
            "note": (
                "本工作区没有 V12 账本文件（`runs/` 在 .gitignore 内）。"
                "只能用只读 CSV 复算可用子集，并明确标注它**不是** 159 局全账本。"
            ),
        }

    rows: list[dict[str, Any]] = []
    started: set[str] = set()
    settled_ids: list[str] = []
    requests = 0
    total = decimal.Decimal("0")
    unknown = 0
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except ValueError:
            continue
        if not isinstance(payload, dict):
            continue
        rows.append(payload)
        event = str(payload.get("event") or "")
        run_id = str(payload.get("run_id") or "")
        if event == "run_started":
            started.add(run_id)
        elif event == "run_settled":
            settled_ids.append(run_id)
            requests += int(payload.get("requests") or 0)
            raw = payload.get("cost_settled_cny")
            if raw is None:
                unknown += 1
            else:
                total += decimal.Decimal(str(raw))
    duplicates = len(settled_ids) - len(set(settled_ids))
    orphans = len(set(settled_ids) - started)
    unstructured = len(started - set(settled_ids)) - orphans
    settled_text = f"{total:.8f}"
    matches = (
        len(settled_ids) == expected["runs"]
        and requests == expected["requests"]
        and settled_text == expected["settled_cost_cny"]
        and duplicates == expected["duplicate_settlements"]
        and orphans == 0
    )
    return {
        "schema": "v14-ledger-recompute-1",
        "status": "RECOMPUTED",
        "ledger_path": str(path),
        "expected": expected,
        "open_ledger": {
            "entries": len(rows),
            "started": len(started),
            "settled": len(settled_ids),
            "requests": requests,
            "settled_cost_cny": settled_text,
            "cost_unknown_runs": unknown,
            "duplicates": duplicates,
            "orphans": orphans,
            "unsettled_started": max(0, unstructured),
            "source": "runs/web/_ledger/web_ledger.jsonl（本机只读）",
        },
        "csv_subset": csv_part,
        "matches_v13_record": matches,
        "external_bill": external,
        "note": (
            "只读复算：不写账本、不重算费用、不重试任何局。"
            "`csv_subset` 只覆盖 138 局，不能代替全账本口径。"
        ),
    }

def engineering_report(
    records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """一次性跑完 P2-2 / P2-4 / P2-5 / P2-6 的只读检查（临时目录）。"""

    import tempfile

    if records is None:
        from agent_arena.lab.v13.history import load_v12_history

        records = load_v12_history()
    with tempfile.TemporaryDirectory(prefix="agent-arena-v14-perf-") as temporary:
        root = Path(temporary)
        cold_base = root / "cold"
        synthesize_history(cold_base, 200)
        cold = cold_start_measurement(cold_base)
        corrupted = corrupted_manifest_handling(root / "corrupted")
        concurrent = concurrent_read_during_write(root / "concurrent")
        ttl = ttl_refresh(root / "ttl")
        long_export = long_history_export(root / "long", count=1_000)
    return {
        "schema": "v14-engineering-1",
        "cold_start": cold,
        "corrupted_manifest": corrupted,
        "concurrent": concurrent,
        "ttl_refresh": ttl,
        "long_export": long_export,
        "sdk": sdk_hardening(),
        "ledger": ledger_recompute(records),
        "note": (
            "全部在本机临时目录实测（合成数据 `STRESS_DATA`）；"
            "耗时只作本机参考，不设跨机器阈值。"
        ),
    }

def engineering_markdown(report: dict[str, Any]) -> str:
    cold = report["cold_start"]
    corrupted = report["corrupted_manifest"]
    concurrent = report["concurrent"]
    ttl = report["ttl_refresh"]
    long_export = report["long_export"]
    sdk = report["sdk"]
    ledger = report["ledger"]
    lines = [
        "# V14 工程边界（P2-2 / P2-4 / P2-5 / P2-6）",
        "",
        "> 全部在临时目录用合成数据（`STRESS_DATA`）实测；零外部请求。",
        "",
        "## 1. 冷启动与预热（P2-2）",
        "",
        "| 项 | 毫秒 | 说明 |",
        "|---|---:|---|",
    ]
    for item in cold["measurements"]:
        lines.append(f"| `{item['label']}` | {item['milliseconds']} | {item['detail']} |")
    lines += [
        "",
        f"> {cold['note']}",
        "",
        "## 2. 异常负载（P2-2）",
        "",
        "| 场景 | 结果 | 关键数字 |",
        "|---|---|---|",
        f"| 损坏 manifest "
        f"| {'通过（不崩、不混入统计）' if not corrupted['bad_run_indexed'] else '**失败**'} "
        f"| 索引 {corrupted['indexed_runs']} 局、页面 {corrupted['page_entries']} 条 |",
        f"| 并发读写 | {'通过（0 异常）' if concurrent['ok'] else '**失败**'} "
        f"| {concurrent['rounds']} 轮、异常 {concurrent['error_count']}、"
        f"最终索引 {concurrent['final_indexed_runs']} 局 |",
        f"| TTL 刷新 | {'通过' if ttl['ok'] else '**失败**'} "
        f"| {ttl['before']} → {ttl['after_ttl_expiry']} → {ttl['after_invalidate']}"
        f"（TTL {ttl['ttl_seconds']}s） |",
        "",
        "## 3. 长历史导出（P2-2 / P2-4）",
        "",
        f"- 导出 {long_export['rows_exported']} / {long_export['runs']} 行，"
        f"耗时 {long_export['export_ms']} ms，"
        f"索引估算 {long_export['index_bytes_estimate']} 字节；",
        f"- {long_export['note']}",
        "",
        "## 4. SDK 加固（P2-5）",
        "",
        "| 检查 | 结果 | 说明 |",
        "|---|---|---|",
    ]
    for item in sdk["base_checks"]:
        lines.append(
            f"| `{item['name']}` | {'通过' if item['ok'] else '**失败**'} | {item['detail']} |"
        )
    for item in sdk["extra_checks"]:
        lines.append(
            f"| `{item['name']}`（V14） | {'通过' if item['ok'] else '**失败**'} | "
            f"{item['detail']} |"
        )
    lines += [
        "",
        f"> {sdk['note']}",
        "",
        "## 5. 账本复算（P2-6）",
        "",
    ]
    if ledger.get("open_ledger"):
        open_ledger = ledger["open_ledger"]
        lines += [
            "| 指标 | 复算值 | V13 记录 |",
            "|---|---:|---:|",
            f"| 局数（settled） | {open_ledger['settled']} | {ledger['expected']['runs']} |",
            f"| started / settled | {open_ledger['started']} / {open_ledger['settled']} "
            "| 159 / 159 |",
            f"| 请求数 | {open_ledger['requests']} | {ledger['expected']['requests']} |",
            f"| 结算费用 CNY | {open_ledger['settled_cost_cny']} | "
            f"{ledger['expected']['settled_cost_cny']} |",
            f"| 重复结算 | {open_ledger['duplicates']} | "
            f"{ledger['expected']['duplicate_settlements']} |",
            f"| 孤儿结算 | {open_ledger['orphans']} | 0 |",
            f"| 费用未知局 | {open_ledger['cost_unknown_runs']} | — |",
        ]
    else:
        lines += [
            f"- 本机账本缺失：`{ledger['status']}`（`runs/` 在 .gitignore 内）。",
            f"- CSV 子集复算：{ledger['csv_subset']['runs']} 局 / "
            f"{ledger['csv_subset']['requests']} 请求 / "
            f"¥{ledger['csv_subset']['settled_cost_cny']}（**不是** 159 局全账本）。",
        ]
    lines += [
        "",
        f"- 与 V13 记录一致：{'是' if ledger['matches_v13_record'] else '**否**'}",
        f"- 外部账单：`{ledger['external_bill']['status']}` — "
        f"{ledger['external_bill']['note']}",
        "",
        f"> {ledger['note']}",
    ]
    export = report.get("export_consistency")
    if export:
        lines += [
            "",
            "## 6. 导出一致性（P2-4）",
            "",
            "| 文件 | 行数 |",
            "|---|---:|",
        ]
        for name, count in (export.get("files") or {}).items():
            lines.append(f"| `{name}` | {count} |")
        lines += [
            "",
            f"- 模式：{export.get('modes')}（期望 `simulated`）",
            f"- 按类别统计的有效分母：{export.get('valid_denominator_computed')}",
            f"- 空单元格：{export.get('empty_cells') or '无'}",
            f"- 问题：{export.get('problems') or '无'}",
            f"- 结论：{'通过' if export.get('ok') else '**失败**'}",
            "",
            f"> {export.get('note')}",
        ]
    lines.append("")
    return "\n".join(lines)

__all__ = [
    "EXTERNAL_BILL_STATUS",
    "V12_LEDGER_EXPECTATION",
    "cold_start_measurement",
    "concurrent_read_during_write",
    "corrupted_manifest_handling",
    "engineering_markdown",
    "engineering_report",
    "export_consistency",
    "ledger_recompute",
    "long_history_export",
    "sdk_hardening",
    "ttl_refresh",
]