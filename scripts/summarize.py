#!/usr/bin/env python3
"""Summarize a Slither JSON report for the pactlint GitHub Action (stdlib only).

Counts findings by impact, writes step outputs ($GITHUB_OUTPUT), a Markdown
table ($GITHUB_STEP_SUMMARY), and exits 1 if the --fail-on threshold is hit,
2 if the Slither report is missing or unsuccessful.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

IMPACT_RANK = {"optimization": 0, "informational": 1, "low": 2, "medium": 3, "high": 4}
THRESHOLDS = {"none": None, "low": 2, "medium": 3, "high": 4}
FOOTER = (
    "For a triaged report of a deployed contract or a single file, "
    "see https://tanod.dev (paid per call via x402)."
)


class ReportError(Exception):
    pass


def load_report(path):
    if not os.path.isfile(path):
        raise ReportError(f"Slither produced no JSON output at {path}; it likely crashed before analysis.")
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise ReportError(f"Could not read Slither JSON output {path}: {exc}")
    if not isinstance(data, dict) or data.get("success") is not True:
        err = data.get("error") if isinstance(data, dict) else None
        raise ReportError(f"Slither failed: {err or 'unknown error (success is not true)'}")
    return data


def rank(impact):
    return IMPACT_RANK.get(str(impact).strip().lower(), -1)


def location(finding, cwd=None):
    cwd = cwd or os.getcwd()
    elements = finding.get("elements") or []
    chosen = None
    for el in elements:
        sm = el.get("source_mapping") or {}
        if sm and not sm.get("is_dependency"):
            chosen = sm
            break
    if chosen is None:
        return ""
    absolute = chosen.get("filename_absolute") or ""
    name = chosen.get("filename_relative") or chosen.get("filename_short") or absolute
    if absolute:
        rel = os.path.relpath(absolute, cwd)
        if not rel.startswith(".."):
            name = rel
    lines = chosen.get("lines") or []
    return f"{name}:{min(lines)}" if lines else name


_SRC_REF = re.compile(r"\s*\([^()\s]*\.sol#[\d-]+\)")


def first_line(text, limit=200):
    text = _SRC_REF.sub("", text or "")
    line = (text or "").strip().splitlines()[0].strip() if text.strip() else ""
    return line if len(line) <= limit else line[: limit - 3] + "..."


def cell(text):
    return str(text).replace("|", "\\|").replace("`", "'").replace("\r", " ").replace("\n", " ")


def summarize(data, cwd=None):
    detectors = (data.get("results") or {}).get("detectors") or []
    counts = {"findings": len(detectors), "high": 0, "medium": 0, "low": 0}
    for d in detectors:
        r = rank(d.get("impact"))
        if r == 4:
            counts["high"] += 1
        elif r == 3:
            counts["medium"] += 1
        elif r == 2:
            counts["low"] += 1
    return counts, detectors


def render_markdown(counts, detectors, fail_on, cwd=None):
    out = ["## pactlint by Tanod", ""]
    out.append(
        f"**{counts['findings']}** finding(s): {counts['high']} high, "
        f"{counts['medium']} medium, {counts['low']} low (fail-on: `{fail_on}`)."
    )
    out.append("")
    if detectors:
        out.append("| Detector | Impact | Confidence | Description | Location |")
        out.append("| --- | --- | --- | --- | --- |")
        ordered = sorted(detectors, key=lambda d: -rank(d.get("impact")))
        for d in ordered:
            out.append(
                "| {} | {} | {} | {} | {} |".format(
                    cell(d.get("check", "")),
                    cell(d.get("impact", "")),
                    cell(d.get("confidence", "")),
                    cell(first_line(d.get("description", ""))),
                    cell(location(d, cwd)),
                )
            )
        out.append("")
    else:
        out.append("No findings.")
        out.append("")
    out.append(FOOTER)
    out.append("")
    return "\n".join(out)


def append(path_env, text):
    path = os.environ.get(path_env)
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(text)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", required=True, help="Slither JSON output file")
    ap.add_argument("--fail-on", default="high", choices=sorted(THRESHOLDS))
    ap.add_argument("--sarif", default="", help="SARIF path to expose as an output")
    args = ap.parse_args(argv)

    try:
        data = load_report(args.json)
    except ReportError as exc:
        msg = str(exc)
        print(f"::error title=pactlint::{msg.splitlines()[0]}")
        append("GITHUB_STEP_SUMMARY", f"## pactlint by Tanod\n\n**Analysis failed.** {msg}\n\n{FOOTER}\n")
        return 2

    counts, detectors = summarize(data)
    append(
        "GITHUB_OUTPUT",
        f"findings={counts['findings']}\nhigh={counts['high']}\nmedium={counts['medium']}\nsarif={args.sarif}\n",
    )
    append("GITHUB_STEP_SUMMARY", render_markdown(counts, detectors, args.fail_on))

    print(f"pactlint: {counts['findings']} finding(s): {counts['high']} high, {counts['medium']} medium, {counts['low']} low")
    threshold = THRESHOLDS[args.fail_on]
    if threshold is not None:
        hits = sum(1 for d in detectors if rank(d.get("impact")) >= threshold)
        if hits:
            print(f"::error title=pactlint::{hits} finding(s) at or above impact '{args.fail_on}'")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
