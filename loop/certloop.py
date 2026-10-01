"""Weekly Certification Loop — verify, draft, check, persist, publish.

The weekly agent run performs the DISCOVER stage (web search) and drops a findings
file in inbox/. Everything that must be reliable happens here, deterministically:

  1. Budget guard  — reject a run that overspent its search/fetch allowance
  2. Verify        — schema, https links, >= N opportunities, every provider searched
  3. Maker         — draft the week's README (Overview / Opportunities / How to Apply)
  4. Checker       — clarity + professional tone + motivational close; maker revises
  5. Spine         — append the week to progress.md, mark new vs returning finds
  6. Connector     — git commit "Weekly Certification Opportunities – DATE" and push

Usage:
    python loop/certloop.py publish inbox/findings-2026-10-01.json [--no-push]
    python loop/certloop.py check   inbox/findings-2026-10-01.json   # dry run, writes nothing
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "loop" / "config.json").read_text(encoding="utf-8"))
TONE = CONFIG["tone"]
WEEK_DIR = re.compile(r"^\d{4}-\d{2}-\d{2}$")
FIELDS = ("provider", "title", "url", "description", "cost", "audience", "region")
COST_LABEL = {
    "free": "Free",
    "free-learning-paid-exam": "Free training (exam is paid)",
    "free-limited-time": "Free for a limited time",
    "discounted": "Discounted",
}
COMMIT_TRAILER = "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"


# --- 1 + 2: budget guard and verification -------------------------------------------

def verify(findings: dict) -> list[str]:
    problems = []
    used = findings.get("budget", {})
    for key in ("searches", "fetches"):
        limit = CONFIG["budget"][f"max_{key}"]
        if key not in used:
            problems.append(f"budget: '{key}' usage not reported")
        elif used[key] > limit:
            problems.append(f"budget: {used[key]} {key} exceeds the limit of {limit}")

    searched = {p.get("provider") for p in findings.get("providers_searched", [])}
    missing = [p for p in CONFIG["providers"] if p not in searched]
    if missing:
        problems.append(f"providers not searched: {', '.join(missing)}")

    opps = findings.get("opportunities", [])
    if len(opps) < CONFIG["min_opportunities"]:
        problems.append(f"only {len(opps)} opportunities; need {CONFIG['min_opportunities']}")
    seen = set()
    for i, o in enumerate(opps, 1):
        empty = [k for k in FIELDS if not str(o.get(k, "")).strip()]
        if empty:
            problems.append(f"opportunity {i}: missing {', '.join(empty)}")
        if not str(o.get("url", "")).startswith("https://"):
            problems.append(f"opportunity {i}: link must be an https official page")
        if o.get("url") in seen:
            problems.append(f"opportunity {i}: duplicate link {o.get('url')}")
        seen.add(o.get("url"))
        if o.get("cost") not in COST_LABEL:
            problems.append(f"opportunity {i}: cost must be one of {', '.join(COST_LABEL)}")
    return problems


def first_seen(week: str) -> dict[str, str]:
    """Continuity: url -> the earliest earlier week it appeared in."""
    seen: dict[str, str] = {}
    for folder in sorted(p for p in ROOT.iterdir() if p.is_dir() and WEEK_DIR.match(p.name)):
        data_file = folder / "findings.json"
        if folder.name >= week or not data_file.exists():
            continue
        for o in json.loads(data_file.read_text(encoding="utf-8")).get("opportunities", []):
            seen.setdefault(o["url"], folder.name)
    return seen


# --- 3: maker ------------------------------------------------------------------------

def draft(findings: dict, week: str, history: dict[str, str]) -> str:
    opps = findings["opportunities"]
    new = sum(o["url"] not in history for o in opps)
    found = sum(p.get("status") == "found" for p in findings["providers_searched"])
    out = [
        f"# 🎓 Weekly Certification Opportunities — {week}",
        "",
        "> Free and low-cost ways to learn, prove and showcase AI and cloud skills, curated every week.",
        "",
        "## Overview",
        "",
        f"This week the loop reviewed **{len(findings['providers_searched'])} providers** and documented "
        f"**{len(opps)} opportunities** you can start today. **{new}** of them are new since the last edition, "
        f"and {found} providers currently offer an official program. Every link below points to the provider's own page.",
        "",
        "## Opportunities",
        "",
    ]
    for i, o in enumerate(opps, 1):
        status = "🆕 New this week" if o["url"] not in history else f"🔁 Listed since {history[o['url']]}"
        out += [
            f"### {i}. {o['title']}",
            "",
            "| | |",
            "|---|---|",
            f"| **Provider** | {o['provider']} |",
            f"| **Official page** | [{o['url']}]({o['url']}) |",
            f"| **Eligibility** | {COST_LABEL[o['cost']]} · {o['audience']} · {o['region']} |",
            f"| **Status** | {status} |",
            "",
            o["description"].strip(),
            "",
        ]
    out += [
        "## How to Apply",
        "",
        "1. **Open the official page** linked above. Always enrol through the provider's own site.",
        "2. **Create or sign in to a free account** with the provider (an email address is usually enough).",
        "3. **Complete the modules and the final quiz or lab** to unlock the certificate or badge.",
        "4. **Claim and share your credential** on LinkedIn, your CV and your GitHub profile.",
        "5. **Check the eligibility line** first: some programs are free to learn but charge for the proctored exam.",
        "",
    ]
    if findings.get("watchlist"):
        out += ["## On the Watchlist", ""]
        out += [f"- **{w['provider']} — {w['title']}**: {w['note']} ([details]({w['url']}))" for w in findings["watchlist"]]
        out += [""]
    out += ["## Providers Searched", "", "| Provider | Result | Note |", "|---|---|---|"]
    out += [f"| {p['provider']} | {p['status']} | {p.get('note', '')} |" for p in findings["providers_searched"]]
    out += ["", "---", "", TONE["motivational_close"], ""]
    return "\n".join(out)


# --- 4: checker + maker revisions ----------------------------------------------------

def _prose_lines(text: str) -> list[str]:
    return [ln for ln in text.splitlines() if ln.strip() and not ln.startswith(("|", "#", "-", ">")) and "](" not in ln]


def check(text: str, findings: dict) -> list[str]:
    problems = []
    for section in ("## Overview", "## Opportunities", "## How to Apply"):
        if section not in text:
            problems.append(f"structure:missing-section:{section[3:]}")
    for o in findings["opportunities"]:
        if o["url"] not in text:
            problems.append("structure:missing-link")
    lowered = text.lower()
    for word in TONE["hype_words"]:
        if re.search(rf"\b{re.escape(word)}\b", lowered):
            problems.append(f"tone:hype:{word}")
    if text.count("!") > TONE["max_exclamations"]:
        problems.append("tone:exclamations")
    shouting = [w for w in re.findall(r"\b[A-Z]{5,}\b", text) if w not in TONE["acronyms"]]
    if shouting:
        problems.append("tone:shouting")
    for line in _prose_lines(text):
        if any(len(s.split()) > TONE["max_sentence_words"] for s in re.split(r"(?<=[.?])\s+", line)):
            problems.append("clarity:long-sentence")
            break
    if TONE["motivational_close"] not in text:
        problems.append("tone:missing-motivation")
    return problems


def revise(text: str, problem: str) -> str:
    kind = problem.split(":")
    if kind[:2] == ["tone", "hype"]:
        return re.sub(rf"\b{re.escape(kind[2])}\b", TONE["hype_words"][kind[2]], text, flags=re.I).replace("  ", " ")
    if problem == "tone:exclamations":
        return text.replace("!", ".")
    if problem == "tone:shouting":
        return re.sub(r"\b[A-Z]{5,}\b", lambda m: m.group() if m.group() in TONE["acronyms"] else m.group().capitalize(), text)
    if problem == "clarity:long-sentence":
        prose = set(_prose_lines(text))
        return "\n".join(
            re.sub(r",\s+(and|but|which)\s+", lambda m: f". {m.group(1).capitalize()} ", ln, count=1) if ln in prose else ln
            for ln in text.splitlines()
        )
    if problem == "tone:missing-motivation":
        return text.rstrip() + "\n\n" + TONE["motivational_close"] + "\n"
    return text  # structural problems cannot be fixed by rewording — they fail the run


def maker_checker(findings: dict, week: str, history: dict[str, str]) -> tuple[str, int, list[str]]:
    text = draft(findings, week, history)
    rounds = 0
    for rounds in range(1, CONFIG["max_checker_rounds"] + 1):
        problems = check(text, findings)
        if not problems:
            return text, rounds, []
        revised = revise(text, problems[0])
        if revised == text:
            return text, rounds, problems
        text = revised
    return text, rounds, check(text, findings)


# --- 5: spine ------------------------------------------------------------------------

def update_progress(findings: dict, week: str, history: dict[str, str], rounds: int) -> None:
    path = ROOT / "progress.md"
    current = path.read_text(encoding="utf-8") if path.exists() else (
        "# 📒 Progress Log\n\nThe loop's spine: one section per weekly run. "
        "Read this before searching so each week builds on the last.\n"
    )
    current = re.sub(rf"\n## Week of {week}\n.*?(?=\n## Week of |\Z)", "", current, flags=re.S)  # idempotent re-runs
    b = findings["budget"]
    lines = [
        f"\n## Week of {week}",
        "",
        f"- **Run:** checker passed in {rounds} round(s) · budget {b['searches']}/{CONFIG['budget']['max_searches']} searches, "
        f"{b['fetches']}/{CONFIG['budget']['max_fetches']} fetches",
        "",
        "### Providers searched",
        "",
        "| Provider | Result | Note |",
        "|---|---|---|",
    ]
    lines += [f"| {p['provider']} | {p['status']} | {p.get('note', '')} |" for p in findings["providers_searched"]]
    lines += ["", "### Certifications found", "", "| # | Provider | Title | Link | Notes |", "|---|---|---|---|---|"]
    for i, o in enumerate(findings["opportunities"], 1):
        tag = "new" if o["url"] not in history else f"returning (since {history[o['url']]})"
        lines.append(f"| {i} | {o['provider']} | {o['title']} | {o['url']} | {COST_LABEL[o['cost']]}; {tag} |")
    if findings.get("watchlist"):
        lines += ["", "### Watchlist and notes", ""]
        lines += [f"- {w['provider']} — {w['title']}: {w['note']} ({w['url']})" for w in findings["watchlist"]]
    path.write_text(current.rstrip() + "\n" + "\n".join(lines) + "\n", encoding="utf-8")


def update_index() -> None:
    weeks = sorted((p for p in ROOT.iterdir() if p.is_dir() and WEEK_DIR.match(p.name)), reverse=True)
    rows = []
    for folder in weeks:
        data = json.loads((folder / "findings.json").read_text(encoding="utf-8"))
        rows.append(f"| [{folder.name}]({folder.name}/README.md) | {len(data['opportunities'])} | "
                    f"{', '.join(sorted({o['provider'] for o in data['opportunities']}))} |")
    template = (ROOT / "loop" / "INDEX_TEMPLATE.md").read_text(encoding="utf-8")
    (ROOT / "README.md").write_text(template.replace("{{ARCHIVE}}", "\n".join(rows)), encoding="utf-8")


# --- 6: connector --------------------------------------------------------------------

def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")


def publish_to_git(week: str, push: bool) -> int:
    git("add", week, "progress.md", "README.md")
    result = git("commit", "-m", f"Weekly Certification Opportunities – {week}\n\n{COMMIT_TRAILER}")
    print(result.stdout.strip() or result.stderr.strip())
    if not push or not git("remote").stdout.strip():
        print("push skipped")
        return 0
    result = git("push", "-u", "origin", "HEAD")
    print("pushed" if result.returncode == 0 else f"push failed: {result.stderr.strip()}")
    return 0 if result.returncode == 0 else 4


# --- CLI -----------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles and Task Scheduler logs default to a legacy code page
    parser = argparse.ArgumentParser(prog="certloop")
    parser.add_argument("command", choices=["check", "publish"])
    parser.add_argument("findings", type=Path)
    parser.add_argument("--no-push", action="store_true")
    args = parser.parse_args(argv)

    findings = json.loads(args.findings.read_text(encoding="utf-8"))
    week = findings.get("week") or date.today().isoformat()
    problems = verify(findings)
    if problems:
        print("VERIFY FAILED - nothing published:\n  - " + "\n  - ".join(problems))
        return 2

    history = first_seen(week)
    text, rounds, remaining = maker_checker(findings, week, history)
    if remaining:
        print(f"CHECKER FAILED after {rounds} round(s):\n  - " + "\n  - ".join(remaining))
        return 3
    new = sum(o["url"] not in history for o in findings["opportunities"])
    print(f"verify ok · checker passed in {rounds} round(s) · {new} new opportunities")
    if args.command == "check":
        return 0

    folder = ROOT / week
    folder.mkdir(exist_ok=True)
    (folder / "README.md").write_text(text, encoding="utf-8")
    (folder / "findings.json").write_text(json.dumps(findings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    update_progress(findings, week, history, rounds)
    update_index()
    print(f"wrote {folder / 'README.md'}, progress.md, README.md")
    return publish_to_git(week, push=not args.no_push)


if __name__ == "__main__":
    sys.exit(main())
