#!/usr/bin/env python3
"""linkedin-draft.py — Generate weekly LinkedIn post drafts for ASI Builders.

Reads content sources and produces a ready-to-review LinkedIn post draft.
Designed for Maël's AI agent workflow (Bernard orchestrates, Pax publishes).

Usage:
  python3 scripts/linkedin-draft.py [--topic TOPIC] [--style {insight,ranking,thread}] [--output PATH]
  python3 scripts/linkedin-draft.py --help
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
DRAFTS_DIR = PROJECT_ROOT / "drafts"
CONTENT_INPUT = PROJECT_ROOT / "content-news-input.json"
DEFAULT_OUTPUT = DRAFTS_DIR / "linkedin-post-weekly.md"

# LinkedIn post constraints
MAX_CHARS = 3000
IDEAL_CHARS = 1200  # Sweet spot for engagement

TEMPLATES = {
    "insight": """# LinkedIn Draft — {date}

## Topic: {topic}

---

**Hook** (première ligne visible sans "voir plus"):
{hook}

**Corps:**
{body}

**CTA:**
{cta}

---

**Hashtags:** {hashtags}
**Estimated chars:** {char_count}
**Style:** Insight post
**Status:** draft — needs Pax review
""",
    "ranking": """# LinkedIn Draft — {date}

## Topic: {topic}

---

**Hook:**
{hook}

**Ranking:**
{body}

**Takeaway:**
{cta}

---

**Hashtags:** {hashtags}
**Estimated chars:** {char_count}
**Style:** Ranking post
**Status:** draft — needs Pax review
""",
    "thread": """# LinkedIn Draft — {date}

## Topic: {topic}

---

**Post 1/3 — Hook:**
{hook}

**Post 2/3 — Deep dive:**
{body}

**Post 3/3 — CTA:**
{cta}

---

**Hashtags:** {hashtags}
**Estimated chars:** {char_count}
**Style:** Thread (carousel alternative)
**Status:** draft — needs Pax review
"""
}

DEFAULT_HASHTAGS = "#AI #AIAgents #BuildWithAI #ASIBuilders"


def load_content_sources():
    """Load available content sources for draft generation."""
    sources = []
    
    # Try content-news-input.json
    if CONTENT_INPUT.exists():
        try:
            with open(CONTENT_INPUT) as f:
                data = json.load(f)
            if isinstance(data, list):
                sources.extend(data)
            elif isinstance(data, dict) and "items" in data:
                sources.extend(data["items"])
        except (json.JSONDecodeError, KeyError):
            pass
    
    # Try existing drafts for context
    for draft in DRAFTS_DIR.glob("*.md"):
        if "linkedin" not in draft.name.lower():
            sources.append({
                "type": "draft",
                "path": str(draft),
                "name": draft.stem
            })
    
    return sources


def generate_draft(topic=None, style="insight", sources=None):
    """Generate a LinkedIn post draft scaffold."""
    date = datetime.now().strftime("%Y-%m-%d")
    week = datetime.now().strftime("W%W")
    
    if not topic:
        topic = f"AI Agents Weekly — {week}"
    
    # Build source context summary
    source_summary = ""
    if sources:
        source_lines = []
        for s in sources[:5]:  # Top 5 sources
            if isinstance(s, dict):
                name = s.get("title", s.get("name", s.get("path", "unknown")))
                source_lines.append(f"  - {name}")
        if source_lines:
            source_summary = "\n\nSources available:\n" + "\n".join(source_lines)
    
    template = TEMPLATES.get(style, TEMPLATES["insight"])
    
    draft = template.format(
        date=date,
        topic=topic,
        hook=f"[WRITE HOOK HERE — max 150 chars, stops the scroll]\n\nContext: {topic}{source_summary}",
        body=f"[WRITE BODY HERE — {IDEAL_CHARS} chars ideal]\n\nKey points to cover:\n  1. What changed this week in AI agents\n  2. One concrete insight (data or example)\n  3. Your take (opinionated > neutral)",
        cta="[WRITE CTA HERE — question or action]\n\nExamples: 'What's your stack?' / 'Link in comments' / 'Agree or disagree?'",
        hashtags=DEFAULT_HASHTAGS,
        char_count=f"~{IDEAL_CHARS} target"
    )
    
    return draft


def main():
    parser = argparse.ArgumentParser(
        description="Generate LinkedIn post drafts for ASI Builders",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python3 scripts/linkedin-draft.py
  python3 scripts/linkedin-draft.py --topic "Claude 4 changes everything"
  python3 scripts/linkedin-draft.py --style ranking --topic "Top 5 AI agent frameworks"
  python3 scripts/linkedin-draft.py --output drafts/linkedin-special.md
"""
    )
    parser.add_argument("--topic", help="Post topic (default: weekly recap)")
    parser.add_argument("--style", choices=["insight", "ranking", "thread"],
                       default="insight", help="Post style template")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT),
                       help=f"Output path (default: {DEFAULT_OUTPUT})")
    parser.add_argument("--list-sources", action="store_true",
                       help="List available content sources and exit")
    parser.add_argument("--dry-run", action="store_true",
                       help="Print draft to stdout instead of writing file")
    
    args = parser.parse_args()
    
    # Load sources
    sources = load_content_sources()
    
    if args.list_sources:
        print(f"Found {len(sources)} content sources:")
        for s in sources:
            if isinstance(s, dict):
                print(f"  - {s.get('title', s.get('name', s.get('path', 'unknown')))}")
            else:
                print(f"  - {s}")
        return 0
    
    # Generate
    draft = generate_draft(topic=args.topic, style=args.style, sources=sources)
    
    if args.dry_run:
        print(draft)
        print(f"\n--- Would write to: {args.output} ---")
        return 0
    
    # Write
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        f.write(draft)
    
    print(f"✅ Draft written to {output_path}")
    print(f"   Topic: {args.topic or 'weekly recap'}")
    print(f"   Style: {args.style}")
    print(f"   Sources: {len(sources)} available")
    print(f"   Next: Review and edit the draft, then publish via Pax")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
