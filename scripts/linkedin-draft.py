#!/usr/bin/env python3
"""Generate weekly LinkedIn post drafts for ASI Builders.

Reads the current framework rankings from src/data/ and produces
a concise, engaging LinkedIn post highlighting key movements and insights.

Usage:
    python3 scripts/linkedin-draft.py                # Generate this week's draft
    python3 scripts/linkedin-draft.py --week 12      # Specific week number
    python3 scripts/linkedin-draft.py --output FILE  # Write to file instead of stdout
    python3 scripts/linkedin-draft.py --help          # Show this help
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRAMEWORKS_TS = PROJECT_ROOT / "src" / "data" / "frameworks.ts"
RANKINGS_TS = PROJECT_ROOT / "src" / "data" / "rankings.ts"
DRAFTS_DIR = PROJECT_ROOT / "drafts"


def parse_ts_array(filepath: Path, var_pattern: str) -> list[dict]:
    """Quick-and-dirty extraction of a TS array-of-objects into Python dicts.
    Works for simple literals (strings, numbers, booleans). Not a full parser."""
    if not filepath.exists():
        return []
    text = filepath.read_text()
    # Find the variable assignment
    match = re.search(rf'{var_pattern}\s*[:=]\s*\[', text)
    if not match:
        return []
    # Extract from the opening [ to its matching ]
    start = match.end() - 1
    depth = 0
    end = start
    for i, ch in enumerate(text[start:], start):
        if ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    raw = text[start:end]
    # Convert TS object literals to JSON-ish
    # Remove trailing commas, convert single quotes, handle unquoted keys
    raw = re.sub(r'/\*.*?\*/', '', raw, flags=re.S)  # block comments
    raw = re.sub(r'//[^\n]*', '', raw)  # line comments
    raw = re.sub(r"(\w+)\s*:", r'"\1":', raw)  # unquoted keys
    raw = raw.replace("'", '"')  # single → double quotes
    raw = re.sub(r',\s*([}\]])', r'\1', raw)  # trailing commas
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []


def get_frameworks() -> list[dict]:
    """Load frameworks from the TS source."""
    return parse_ts_array(FRAMEWORKS_TS, r'(?:export\s+)?(?:const|let)\s+frameworks')


def current_iso_week() -> int:
    return datetime.now().isocalendar()[1]


def generate_post(frameworks: list[dict], week: int) -> str:
    """Generate a LinkedIn post draft from framework data."""
    year = datetime.now().year
    # Sort by score descending (if score field exists)
    scored = [f for f in frameworks if f.get('score') or f.get('totalScore') or f.get('rank')]
    if not scored:
        scored = frameworks[:10]  # fallback: just use order

    # Try to extract a ranking order
    def rank_key(fw):
        return -(fw.get('score', 0) or fw.get('totalScore', 0) or (100 - fw.get('rank', 50)))
    scored.sort(key=rank_key)
    top5 = scored[:5]

    lines = []
    lines.append(f"🏗️ AI Agent Framework Rankings — Week {week}, {year}")
    lines.append("")
    lines.append("Which frameworks are builders actually choosing to create autonomous AI agents?")
    lines.append("")
    lines.append("Here's this week's top 5 from ASI Builders:")
    lines.append("")

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    for i, fw in enumerate(top5):
        name = fw.get('name', fw.get('id', f'Framework {i+1}'))
        desc = fw.get('description', fw.get('tagline', ''))
        score = fw.get('score') or fw.get('totalScore') or ''
        score_str = f" ({score}/100)" if score else ""
        line = f"{medals[i]} {name}{score_str}"
        if desc:
            line += f" — {desc[:80]}"
        lines.append(line)

    lines.append("")
    lines.append("The AI agent space moves fast. New frameworks ship weekly.")
    lines.append("We track what matters: real adoption, GitHub activity, docs quality, and community size.")
    lines.append("")
    lines.append("👉 Full ranking + methodology: https://asi-builders.com")
    lines.append("")
    lines.append("#AIAgents #Frameworks #OpenSource #BuildWithAI #ASIBuilders")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Generate weekly LinkedIn post drafts for ASI Builders",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example: python3 scripts/linkedin-draft.py --week 12 --output drafts/linkedin-w12.md"
    )
    parser.add_argument("--week", type=int, default=current_iso_week(),
                        help="ISO week number (default: current week)")
    parser.add_argument("--output", "-o", type=str, default=None,
                        help="Output file path (default: stdout)")
    parser.add_argument("--json", action="store_true",
                        help="Output as JSON with metadata")
    args = parser.parse_args()

    frameworks = get_frameworks()
    if not frameworks:
        print("⚠️  Could not parse frameworks from src/data/frameworks.ts", file=sys.stderr)
        print("   Generating template post without ranking data.", file=sys.stderr)

    post = generate_post(frameworks, args.week)

    if args.json:
        output = json.dumps({
            "week": args.week,
            "year": datetime.now().year,
            "generated_at": datetime.now().isoformat(),
            "frameworks_count": len(frameworks),
            "post": post,
            "char_count": len(post),
        }, indent=2)
    else:
        output = post

    if args.output:
        outpath = Path(args.output)
        outpath.parent.mkdir(parents=True, exist_ok=True)
        outpath.write_text(output)
        print(f"✅ Draft written to {outpath}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
