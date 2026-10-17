"""Static leakage and read-only checks for the V7 metric layer.

The V7 layer is deliberately a consumer of public Episode Traces and offline
judge artefacts. This script fails if V7 source starts importing runner,
prompt, provider, environment, or evaluation modules, writes files, opens a
network socket, or contains credential-shaped strings in its documentation.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V7_SOURCE = ROOT / "src" / "agent_arena" / "v7"
V7_DOCS = ROOT / "docs" / "v7"

FORBIDDEN_IMPORT_PREFIXES = (
    "agent_arena.llm",
    "agent_arena.arena",
    "agent_arena.agents",
    "agent_arena.evaluation",
    "agent_arena.worlds",
    "agent_arena.v5",
    "agent_arena.v6",
    "httpx",
    "openai",
    "requests",
    "socket",
    "subprocess",
)

FORBIDDEN_NAMES = {
    "requests",
    "httpx",
    "openai",
    "socket",
    "subprocess",
}

FORBIDDEN_ATTRIBUTES = {
    ("os", "environ"),
    ("os", "getenv"),
    ("Path", "write_text"),
    ("Path", "write_bytes"),
    ("Path", "open"),
}

SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]{20,}\b"),
    re.compile(r"(?i)\b(?:api[_-]?key|secret|token)\s*[:=]\s*['\"][^'\"]{12,}['\"]"),
    re.compile(r"(?i)\b(?:OPENAI|DASHSCOPE|BAILIAN|ANTHROPIC)_API_KEY\s*="),
)


def _iter_imports(tree: ast.AST) -> list[str]:
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


def _iter_calls(tree: ast.AST) -> list[tuple[str, str]]:
    calls: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            calls.append((node.func.id, node.func.id))
        elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            calls.append((node.func.value.id, node.func.attr))
    return calls


def scan_source(root: Path | None = None) -> list[str]:
    findings: list[str] = []
    source_root = root or V7_SOURCE
    for path in sorted(source_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        try:
            relative = path.relative_to(ROOT)
        except ValueError:
            relative = path
        for module in _iter_imports(tree):
            if module in FORBIDDEN_NAMES or module.startswith(FORBIDDEN_IMPORT_PREFIXES):
                findings.append(f"{relative}: forbidden import {module}")
        for owner, attribute in _iter_calls(tree):
            if (owner, attribute) in FORBIDDEN_ATTRIBUTES:
                findings.append(f"{relative}: forbidden call {owner}.{attribute}")
            if owner == "open" or (owner == "builtins" and attribute == "open"):
                findings.append(f"{relative}: file I/O call open")
    return findings


def scan_docs(root: Path | None = None) -> list[str]:
    findings: list[str] = []
    docs_root = root or V7_DOCS
    for path in sorted(docs_root.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        try:
            relative = path.relative_to(ROOT)
        except ValueError:
            relative = path
        for pattern in SECRET_PATTERNS:
            for match in pattern.finditer(text):
                findings.append(f"{relative}: credential-shaped text {match.group(0)[:24]!r}")
    return findings


def scan() -> list[str]:
    return scan_source() + scan_docs()


def main() -> int:
    findings = scan()
    if findings:
        for finding in findings:
            print(f"LEAKAGE: {finding}")
        return 1
    print(
        "V7 leakage check passed: "
        f"{len(list(V7_SOURCE.rglob('*.py')))} source files, "
        f"{len(list(V7_DOCS.rglob('*.md')))} docs, no forbidden imports or writes."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
