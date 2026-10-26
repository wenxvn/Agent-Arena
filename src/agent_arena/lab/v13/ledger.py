"""本地账本一致性审计与后台账单离线对账（P2-6 / V13-10-04 … 10-06）。

**只读**：不追加、不修改、不重算账本条目。

检查项：

1. 父子一致：每个父实验的子局链接数 vs ``runs/web/<run_id>`` 实际目录数；
2. 起止配对：``run_started`` 与 ``run_settled`` 是否一一对应；
3. 请求/token/费用：``run_settled`` 内的 usage 是否自洽（非负、可加总）；
4. 未知消费：``cost_unknown`` 的条目单独列出，**不并进已结算金额**；
5. 重复账单：同一 ``run_id`` 出现多条 ``run_settled``；
6. 孤儿任务：只有 ``run_started`` 没有收尾（进程被杀/崩溃）。

后台账单：只有用户提供**脱敏 CSV** 时才做对账；否则明确输出
``NOT_RECONCILED_EXTERNAL``，不得声称"后台已核对"。
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

NOT_RECONCILED = "NOT_RECONCILED_EXTERNAL"
RECONCILED = "RECONCILED_WITH_EXTERNAL_BILL"
NO_BILL = "NO_EXTERNAL_BILL_PROVIDED"

#: 账单列名（容忍常见中英文写法，但只接受脱敏列）。
BILL_COLUMNS: dict[str, tuple[str, ...]] = {
    "run_id": ("run_id", "run", "请求id", "任务id"),
    "amount": ("amount", "cost", "cost_cny", "金额", "费用"),
    "currency": ("currency", "币种"),
    "settled_at": ("settled_at", "time", "timestamp", "时间"),
}

#: 金额容差：绝对 ¥0.0001 或相对 0.5%，取较大者。
ABS_TOLERANCE = Decimal("0.0001")
REL_TOLERANCE = Decimal("0.005")


@dataclass
class LedgerAudit:
    ledger_path: str
    entries: int = 0
    started: int = 0
    settled: int = 0
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_settled_cny: str = "0"
    unknown_spend_runs: list[str] = field(default_factory=list)
    orphan_runs: list[str] = field(default_factory=list)
    duplicate_settlements: list[str] = field(default_factory=list)
    negative_usage: list[str] = field(default_factory=list)
    parents: int = 0
    child_links: int = 0
    parents_live: int = 0
    parents_simulated: int = 0
    child_links_live: int = 0
    child_missing_runs: list[str] = field(default_factory=list)
    orphan_run_dirs: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": "v13-ledger-audit-1",
            "ledger_path": self.ledger_path,
            "entries": self.entries,
            "started": self.started,
            "settled": self.settled,
            "requests": self.requests,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_settled_cny": self.cost_settled_cny,
            "unknown_spend_runs": list(self.unknown_spend_runs),
            "orphan_runs": list(self.orphan_runs),
            "duplicate_settlements": list(self.duplicate_settlements),
            "negative_usage": list(self.negative_usage),
            "parents": self.parents,
            "parents_live": self.parents_live,
            "parents_simulated": self.parents_simulated,
            "child_links": self.child_links,
            "child_links_live": self.child_links_live,
            "child_missing_runs": list(self.child_missing_runs),
            "orphan_run_dirs": list(self.orphan_run_dirs),
            "issues": list(self.issues),
            "external_reconciliation": NOT_RECONCILED,
            "read_only": True,
        }


def _decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def read_ledger(path: Path) -> list[dict[str, Any]]:
    """逐行读 JSONL；坏行跳过并计入 issues（不修改文件）。"""

    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except ValueError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def audit_ledger(
    *,
    ledger_path: Path,
    lab_dir: Path | None = None,
    web_dir: Path | None = None,
) -> LedgerAudit:
    """本地账本只读一致性审计。"""

    audit = LedgerAudit(ledger_path=str(ledger_path))
    rows = read_ledger(ledger_path)
    audit.entries = len(rows)
    settled_by_run: dict[str, dict[str, Any]] = {}
    started_runs: set[str] = set()
    total = Decimal(0)
    for row in rows:
        event = str(row.get("event") or "")
        run_id = str(row.get("run_id") or "")
        if event == "run_started":
            audit.started += 1
            started_runs.add(run_id)
        elif event == "run_settled":
            audit.settled += 1
            if run_id in settled_by_run:
                audit.duplicate_settlements.append(run_id)
            settled_by_run[run_id] = row
            requests = int(row.get("requests") or 0)
            input_tokens = int(row.get("input_tokens") or 0)
            output_tokens = int(row.get("output_tokens") or 0)
            if requests < 0 or input_tokens < 0 or output_tokens < 0:
                audit.negative_usage.append(run_id)
            audit.requests += max(0, requests)
            audit.input_tokens += max(0, input_tokens)
            audit.output_tokens += max(0, output_tokens)
            if row.get("cost_unknown"):
                audit.unknown_spend_runs.append(run_id)
            else:
                cost = _decimal(row.get("cost_settled_cny"))
                if cost is not None:
                    total += cost
        elif event in {"run_aborted", "run_cancelled", "run_unknown_spend"}:
            # 这些也是收尾事件；不计入 settled，但不再算孤儿。
            started_runs.discard(run_id)
    audit.cost_settled_cny = str(total)
    audit.orphan_runs = sorted(started_runs - set(settled_by_run))

    if lab_dir is not None:
        detail = _audit_parents(lab_dir, web_dir)
        audit.parents = detail["parents"]
        audit.parents_live = detail["parents_live"]
        audit.parents_simulated = detail["parents_simulated"]
        audit.child_links = detail["child_links"]
        audit.child_links_live = detail["child_links_live"]
        audit.child_missing_runs = detail["missing"]

    if audit.duplicate_settlements:
        audit.issues.append(
            f"{len(audit.duplicate_settlements)} 个 run 有多条 run_settled（可能重复计费）。"
        )
    if audit.orphan_runs:
        audit.issues.append(
            f"{len(audit.orphan_runs)} 个 run 只有 started 没有收尾（孤儿任务）。"
        )
    if audit.unknown_spend_runs:
        audit.issues.append(
            f"{len(audit.unknown_spend_runs)} 个 run 费用未知；已结算金额不含这些局。"
        )
    if audit.negative_usage:
        audit.issues.append(f"{len(audit.negative_usage)} 个 run 的 usage 出现负值。")
    if audit.child_missing_runs:
        audit.issues.append(
            f"{len(audit.child_missing_runs)} 个子局链接指向不存在的 run 目录。"
        )
    return audit


def _audit_parents(
    lab_dir: Path, web_dir: Path | None
) -> dict[str, Any]:
    """父子一致：manifest.children 的 run_id 是否真的存在。

    同时按父实验的 ``mode`` 区分 ``live`` 与 ``simulated``：V13 的离线演示也会
    产生父实验，混在一起会让人误以为真实实验变多了。
    """

    parents = 0
    parents_live = 0
    parents_simulated = 0
    links = 0
    links_live = 0
    missing: list[str] = []
    if not lab_dir.is_dir():
        return {
            "parents": 0,
            "parents_live": 0,
            "parents_simulated": 0,
            "child_links": 0,
            "child_links_live": 0,
            "missing": [],
        }
    for directory in sorted(lab_dir.iterdir()):
        if not directory.is_dir():
            continue
        manifest_path = directory / "manifest.json"
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        parents += 1
        mode = str(manifest.get("mode") or "")
        if mode == "live":
            parents_live += 1
        else:
            parents_simulated += 1
        for child in manifest.get("children") or []:
            run_id = str(child.get("run_id") or "")
            if not run_id:
                continue
            links += 1
            if mode == "live":
                links_live += 1
            if web_dir is not None and not (web_dir / run_id).is_dir():
                missing.append(run_id)
    return {
        "parents": parents,
        "parents_live": parents_live,
        "parents_simulated": parents_simulated,
        "child_links": links,
        "child_links_live": links_live,
        "missing": missing,
    }


# ------------------------------------------------------------------ bill import
def write_bill_template(
    path: Path, rows: list[tuple[str, str, str]] | None = None
) -> Path:
    """写出脱敏账单 CSV 模板（列：run_id, amount, currency, settled_at）。

    只写模板与用户显式给出的行；**不读取**任何本地账本、不联网。
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(["run_id", "amount", "currency", "settled_at"])
    for run_id, amount, currency in rows or []:
        writer.writerow([run_id, amount, currency, ""])
    path.write_text(buffer.getvalue(), encoding="utf-8-sig", newline="")
    return path


def read_bill_csv(path: Path) -> dict[str, Any]:
    """读脱敏账单 CSV：只取 run_id / amount / currency / settled_at。"""
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return {"rows": [], "currency": "", "problems": ["空账单文件"]}
    mapping: dict[str, str] = {}
    for name, candidates in BILL_COLUMNS.items():
        for candidate in candidates:
            if candidate in reader.fieldnames:
                mapping[name] = candidate
                break
    problems: list[str] = []
    for required in ("run_id", "amount"):
        if required not in mapping:
            problems.append(f"账单缺少必需列：{required}（可用列：{reader.fieldnames}）")
    rows: list[dict[str, Any]] = []
    if not problems:
        for raw in reader:
            amount = _decimal(raw.get(mapping["amount"]))
            run_id = str(raw.get(mapping["run_id"]) or "").strip()
            if not run_id or amount is None:
                continue
            rows.append(
                {
                    "run_id": run_id,
                    "amount": amount,
                    "currency": str(raw.get(mapping.get("currency", ""), "") or "").strip(),
                    "settled_at": str(raw.get(mapping.get("settled_at", ""), "") or "").strip(),
                }
            )
    return {
        "rows": rows,
        "currency": next((row["currency"] for row in rows if row["currency"]), ""),
        "problems": problems,
    }


def reconcile_bill(
    audit: LedgerAudit,
    bill_path: Path | None,
    *,
    ledger_rows: list[dict[str, Any]] | None = None,
    currency: str = "CNY",
) -> dict[str, Any]:
    """把本地账本与（可选的）后台账单逐局对账。

    没有账单时返回 ``NO_EXTERNAL_BILL_PROVIDED`` —— 绝不写"已核对"。
    """

    if bill_path is None or not Path(bill_path).is_file():
        return {
            "status": NO_BILL,
            "note": (
                "未提供 Provider 后台账单：本地账本只与登记的价目表对账，"
                "不代表后台金额已核对。"
            ),
            "local_settled_cny": audit.cost_settled_cny,
        }
    bill = read_bill_csv(Path(bill_path))
    if bill["problems"]:
        return {
            "status": NOT_RECONCILED,
            "problems": bill["problems"],
            "local_settled_cny": audit.cost_settled_cny,
        }
    if bill["currency"] and bill["currency"].upper() != currency.upper():
        return {
            "status": NOT_RECONCILED,
            "problems": [f"币种不一致：账单 {bill['currency']} vs 账本 {currency}"],
            "local_settled_cny": audit.cost_settled_cny,
        }
    local: dict[str, Decimal] = {}
    for row in ledger_rows or []:
        if row.get("event") != "run_settled":
            continue
        cost = _decimal(row.get("cost_settled_cny"))
        if cost is not None and not row.get("cost_unknown"):
            local[str(row.get("run_id"))] = cost
    matched = 0
    mismatches: list[dict[str, Any]] = []
    bill_total = Decimal(0)
    local_total = Decimal(0)
    for row in bill["rows"]:
        run_id = row["run_id"]
        bill_total += row["amount"]
        local_amount = local.get(run_id)
        if local_amount is None:
            mismatches.append(
                {"run_id": run_id, "reason": "账单有此 run，本地账本没有对应结算"}
            )
            continue
        local_total += local_amount
        tolerance = max(ABS_TOLERANCE, abs(local_amount) * REL_TOLERANCE)
        if abs(local_amount - row["amount"]) > tolerance:
            mismatches.append(
                {
                    "run_id": run_id,
                    "reason": "金额差异超出容差",
                    "local": str(local_amount),
                    "bill": str(row["amount"]),
                    "tolerance": str(tolerance),
                }
            )
        else:
            matched += 1
    only_local = sorted(set(local) - {row["run_id"] for row in bill["rows"]})
    return {
        "status": RECONCILED if not mismatches and not only_local else NOT_RECONCILED,
        "bill_rows": len(bill["rows"]),
        "matched": matched,
        "mismatches": mismatches,
        "local_only_runs": only_local,
        "bill_total": str(bill_total),
        "local_total": str(local_total),
        "tolerance": {"absolute_cny": str(ABS_TOLERANCE), "relative": str(REL_TOLERANCE)},
        "currency": currency,
        "rules": (
            "按 run_id 逐局对账；容差取 max(¥0.0001, 0.5%)；"
            "账单多出的 run 与本地多出的 run 都必须列出，不静默丢弃。"
        ),
        "note": "账单必须是脱敏 CSV；本工具不联网、不登录 Provider 控制台。",
    }


def ledger_markdown(audit: LedgerAudit, reconciliation: dict[str, Any]) -> str:
    lines = [
        "# 本地账本与费用审计",
        "",
        f"- 账本文件：`{audit.ledger_path}`（只读）",
        f"- 条目：{audit.entries}（started {audit.started} / settled {audit.settled}）",
        f"- 请求：{audit.requests}；输入 token：{audit.input_tokens}；"
        f"输出 token：{audit.output_tokens}",
        f"- 已结算：CNY {audit.cost_settled_cny}",
        f"- 未知消费局：{len(audit.unknown_spend_runs)}",
        f"- 父实验：{audit.parents}（live {audit.parents_live} / "
        f"simulated {audit.parents_simulated}）；子局链接：{audit.child_links}"
        f"（live {audit.child_links_live}）",
        "",
        "## 发现的问题",
        "",
    ]
    if audit.issues:
        lines.extend(f"- {issue}" for issue in audit.issues)
    else:
        lines.append("- 未发现结构性问题（不等于后台账单已核对）。")
    lines += [
        "",
        "## 外部账单对账",
        "",
        f"- 状态：`{reconciliation.get('status')}`",
        f"- 说明：{reconciliation.get('note')}",
    ]
    for key in ("bill_rows", "matched", "bill_total", "local_total"):
        if key in reconciliation:
            lines.append(f"- {key}：{reconciliation[key]}")
    if reconciliation.get("mismatches"):
        lines += ["", "| run_id | 原因 | 本地 | 账单 |", "|---|---|---|---|"]
        for item in reconciliation["mismatches"][:20]:
            lines.append(
                f"| `{item.get('run_id')}` | {item.get('reason')} | "
                f"{item.get('local', '—')} | {item.get('bill', '—')} |"
            )
    lines += [
        "",
        "## 口径",
        "",
        "- 未知消费的局不并入已结算金额；",
        "- 历史账本条目一条都不修改，发现差异只生成记录；",
        "- 没有后台账单时必须保留 `NOT_RECONCILED_EXTERNAL`。",
        "",
    ]
    return "\n".join(lines)


__all__ = [
    "ABS_TOLERANCE",
    "BILL_COLUMNS",
    "NO_BILL",
    "NOT_RECONCILED",
    "RECONCILED",
    "REL_TOLERANCE",
    "LedgerAudit",
    "audit_ledger",
    "ledger_markdown",
    "read_bill_csv",
    "read_ledger",
    "reconcile_bill",
    "write_bill_template",
]
