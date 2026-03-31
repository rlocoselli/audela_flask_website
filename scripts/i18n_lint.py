#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import re
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


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
    candidate = re.sub(r"\s+", " ", html.unescape(text)).strip()
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
        "DSCR",
        "Leverage",
        "Liquidity",
        "left",
        "center",
        "right",
        "True",
        "False",
        "if_required",
        "if_not_required",
    }
    if candidate in safe_tokens:
        return False

    lower = candidate.lower()

    # Decision-rule snippets and technical tokens are documentation examples,
    # not user-facing natural language.
    if lower.startswith("fn:"):
        return False
    if "?true=" in lower or "?false=" in lower:
        return False

    # Ignore formula-like fragments and comparator chunks.
    if re.fullmatch(r"[<>=0-9xX.\-\s]+", candidate):
        return False
    if re.fullmatch(r"[<>=0-9xX.\-\s]+(?:and|or)?", lower):
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


def _extract_msgids_from_text(content: str) -> set[str]:
    msgids: set[str] = set()
    for m in re.finditer(r"_\('([^'\\]*(?:\\.[^'\\]*)*)'\)", content):
        raw = m.group(1)
        msgids.add(raw.replace("\\'", "'"))
    for m in re.finditer(r"\bt\('([^'\\]*(?:\\.[^'\\]*)*)'\)", content):
        raw = m.group(1)
        msgids.add(raw.replace("\\'", "'"))
    return msgids


def _scan_missing_en_translations(template_files: list[Path], js_files: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    try:
        from audela.i18n import TRANSLATIONS  # type: ignore
    except Exception as exc:
        return [
            Finding(
                path=ROOT / "audela/i18n.py",
                line=1,
                kind="i18n-load",
                message=f"Could not import TRANSLATIONS for missing-en check: {exc}",
            )
        ]

    en_map = TRANSLATIONS.get("en", {}) if isinstance(TRANSLATIONS, dict) else {}
    if not isinstance(en_map, dict):
        en_map = {}

    files = template_files + js_files
    for path in files:
        content = path.read_text(encoding="utf-8", errors="ignore")
        msgids = _extract_msgids_from_text(content)
        for msgid in sorted(msgids):
            if msgid in en_map:
                continue
            # Skip obviously technical placeholders
            if msgid.startswith("footer."):
                continue
            findings.append(
                Finding(
                    path=path,
                    line=1,
                    kind="missing-en",
                    message=f"Missing EN translation for msgid: {msgid}",
                )
            )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Light i18n lint for Python flash messages and HTML raw text.")
    parser.add_argument("--strict", action="store_true", help="Exit with code 1 if findings are detected.")
    parser.add_argument("--max", type=int, default=300, help="Maximum findings to display.")
    parser.add_argument("--missing-en-only", action="store_true", help="Only report keys used in templates/JS that are missing EN translations.")
    parser.add_argument("--scope", choices=["all", "bi"], default="all", help="Limit scan scope. 'bi' checks BI portal templates and BI JS only.")
    args = parser.parse_args()

    findings: list[Finding] = []

    if args.scope == "bi":
        html_files = _iter_files(["templates/portal/**/*.html"])
        bi_js_files = _iter_files(["static/bi/**/*.js", "static/portal/**/*.js"])
    else:
        html_files = _iter_files(["templates/**/*.html", "audela/templates/**/*.html", "templates_portal/**/*.html"])
        bi_js_files = _iter_files(["static/bi/**/*.js", "static/portal/**/*.js"])

    if args.missing_en_only:
        findings.extend(_scan_missing_en_translations(html_files, bi_js_files))
    else:
        py_files = _iter_files(["audela/**/*.py", "blueprints/**/*.py", "services/**/*.py"])
        for file_path in py_files:
            findings.extend(_scan_python_flash_strings(file_path))
        for file_path in html_files:
            findings.extend(_scan_html_raw_text(file_path))
        findings.extend(_scan_missing_en_translations(html_files, bi_js_files))

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
