#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Finding:
    path: Path
    line: int
    kind: str
    message: str


def _iter_files(patterns: list[str]) -> list[Path]:
    out: list[Path] = []
    for pattern in patterns:
        out.extend(ROOT.glob(pattern))
    return [p for p in out if p.is_file()]


def _scan_python_flash_strings(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    for idx, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
        if "flash(" not in line:
            continue
        stripped = line.strip()
        if "flash(tr(" in stripped or "flash(_(" in stripped:
            continue
        if re.search(r"\bflash\(\s*[furbFURB]*[\"']", stripped):
            findings.append(
                Finding(
                    path=path,
                    line=idx,
                    kind="python-flash",
                    message="flash() string literal not wrapped in tr()/_.",
                )
            )
    return findings


def _is_probably_translatable_text(text: str) -> bool:
    candidate = re.sub(r"\s+", " ", text).strip()
    if not candidate:
        return False
    if "{{" in candidate or "{%" in candidate or "{#" in candidate:
        return False
    if candidate.startswith("<!--"):
        return False
    if re.fullmatch(r"[\W\d_]+", candidate):
        return False
    if len(candidate) < 3:
        return False

    safe_tokens = {
        "N/A",
        "API",
        "IBAN",
        "BIC",
        "SQL",
        "JSON",
        "URL",
        "PDF",
        "XML",
        "CSV",
        "ETL",
        "BI",
        "UI",
        "OK",
        "FR",
        "IT",
    }
    if candidate in safe_tokens:
        return False

    if re.search(r"[A-Za-zÀ-ÿ]", candidate) is None:
        return False
    return True


def _scan_html_raw_text(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    in_script = False
    in_style = False

    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    for idx, line in enumerate(lines, start=1):
        lower = line.lower()
        if "<script" in lower:
            in_script = True
        if "</script" in lower:
            in_script = False
            continue
        if "<style" in lower:
            in_style = True
        if "</style" in lower:
            in_style = False
            continue
        if in_script or in_style:
            continue

        for m in re.finditer(r">([^<>]+)<", line):
            text = m.group(1)
            if not _is_probably_translatable_text(text):
                continue
            findings.append(
                Finding(
                    path=path,
                    line=idx,
                    kind="template-text",
                    message=f"Raw template text detected: {text.strip()[:90]}",
                )
            )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Light i18n lint for Python flash messages and HTML raw text.")
    parser.add_argument("--strict", action="store_true", help="Exit with code 1 if findings are detected.")
    parser.add_argument("--max", type=int, default=300, help="Maximum findings to display.")
    args = parser.parse_args()

    findings: list[Finding] = []

    py_files = _iter_files(["audela/**/*.py", "blueprints/**/*.py", "services/**/*.py"])
    for file_path in py_files:
        findings.extend(_scan_python_flash_strings(file_path))

    html_files = _iter_files(["templates/**/*.html", "audela/templates/**/*.html", "templates_portal/**/*.html"])
    for file_path in html_files:
        findings.extend(_scan_html_raw_text(file_path))

    findings.sort(key=lambda f: (str(f.path), f.line, f.kind))

    total = len(findings)
    shown = findings[: max(args.max, 0)]

    for f in shown:
        rel = f.path.relative_to(ROOT)
        print(f"[{f.kind}] {rel}:{f.line} :: {f.message}")

    if total > len(shown):
        print(f"... and {total - len(shown)} more findings (increase --max to see all).")

    print(f"i18n-lint findings: {total}")
    if args.strict and total > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
