from __future__ import annotations
import json
import subprocess
import tempfile
from pathlib import Path
from .schemas import ValidationIssue


def _run(cmd: list[str], cwd: str) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=30)
    return proc.returncode, proc.stdout, proc.stderr


def run_ruff(code: str, filename: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / filename
        path.write_text(code)
        rc, out, err = _run(["ruff", "check", "--output-format=json", str(path)], tmp)
        if not out.strip():
            return issues
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            return [ValidationIssue(tool="ruff", severity="error", message=err or out)]
        for item in data:
            loc = item.get("location") or {}
            issues.append(ValidationIssue(
                tool="ruff",
                severity="warning",
                line=loc.get("row"),
                column=loc.get("column"),
                code=item.get("code"),
                message=item.get("message", ""),
            ))
    return issues


def run_mypy(code: str, filename: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / filename
        path.write_text(code)
        rc, out, err = _run(
            ["mypy", "--ignore-missing-imports", "--no-color-output",
             "--show-column-numbers", "--no-error-summary", str(path)],
            tmp,
        )
        for line in out.splitlines():
            # path:line:col: severity: message  [code]
            parts = line.split(":", 4)
            if len(parts) < 5:
                continue
            try:
                ln = int(parts[1]); col = int(parts[2])
            except ValueError:
                continue
            sev = parts[3].strip()
            msg = parts[4].strip()
            issues.append(ValidationIssue(
                tool="mypy",
                severity="error" if sev == "error" else "warning",
                line=ln, column=col, message=msg,
            ))
    return issues
