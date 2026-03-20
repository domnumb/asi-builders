#!/usr/bin/env python3
"""linkedin-draft.py — Generate weekly LinkedIn post drafts for ASI Builders.

Usage:
    python3 scripts/linkedin-draft.py [--help] [--output PATH] [--topic TOPIC]

Generates a structured LinkedIn post draft about AI agents/builders
that can be reviewed and posted by Pax.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Project root
ROOT = Path(__file__).parent.parent
DRAFTS_DIR = ROOT / "drafts"

# Weekly themes rotation
THEMES = [
    {
        "topic": "agent-frameworks",
        "hook": "The AI agent framework landscape is shifting fast.",
        "angles": [
            "Which frameworks are production-ready vs. demo-only?",
            "What separates toy agents from reliable ones?",
            "The hidden cost of agent orchestration"
        ]
    },
    {
        "topic": "agent-reliability",
        "hook": "Most AI agents fail silently. Here's what the best ones do differently.",
        "angles": [
            "Verification loops vs. hope-based deployment",
            "Why hallucination detection is table stakes",
            "The 3 failure modes every agent builder should know"
        ]
    },
    {
        "topic": "agent-economics",
        "hook": "Running AI agents 24/7 costs more than you think.",
        "angles": [
            "Token economics: when agents become expensive",
            "The business case for autonomous vs. copilot agents",
            "ROI frameworks for agent deployment"
        ]
    },
    {
        "topic": "agent-safety",
        "hook": "Your AI agent has more access than your junior dev. Are you OK with that?",
        "angles": [
            "Capability boundaries: what agents should NOT do",
            "The principle of least privilege for AI agents",
            "When agents go wrong: real incident patterns"
        ]
    },
    {
        "topic": "building-in-public",
        "hook": "I've been running autonomous AI agents for 3 months. Here's what I learned.",
        "angles": [
            "The gap between demo and production",
            "What breaks first when you deploy agents",
            "Lessons from 10,000+ agent cycles"
        ]
    }
]


def get_week_theme(topic: str | None = None) -> dict:
    """Get theme for current week or by topic."""
    if topic:
        for theme in THEMES:
            if theme["topic"] == topic:
                return theme
        print(f"Unknown topic: {topic}. Available: {[t['topic'] for t in THEMES]}")
        sys.exit(1)
    
    # Rotate based on ISO week number
    week_num = datetime.now().isocalendar()[1]
    return THEMES[week_num % len(THEMES)]


def generate_draft(theme: dict) -> str:
    """Generate a LinkedIn post draft from theme."""
    now = datetime.now()
    week_label = f"W{now.isocalendar()[1]}"
    
    # LinkedIn post structure (optimal: 1200-1500 chars)
    draft = f"""---
type: linkedin-draft
project: asi-builders
topic: {theme['topic']}
week: {week_label}
generated: {now.strftime('%Y-%m-%d %H:%M')}
status: draft
review: none
---

# LinkedIn Post Draft — {week_label} ({theme['topic']})

## Hook (first 2 lines — visible before "see more")

{theme['hook']}
↓

## Body

**Angle options (pick one, expand to 3-5 short paragraphs):**

"""
    
    for i, angle in enumerate(theme['angles'], 1):
        draft += f"{i}. {angle}\n"
    
    draft += f"""
## Draft (edit this)

{theme['hook']}

After running autonomous AI agents in production for months,
here's what actually matters:

1/ [Point 1 — concrete, from experience]

2/ [Point 2 — counterintuitive insight]

3/ [Point 3 — actionable takeaway]

The future of AI isn't about smarter models.
It's about more reliable systems.

---

What's your experience building with AI agents?

#AIAgents #BuildInPublic #ASI #AIEngineering

## Notes for Pax
- Target: 1200-1500 characters final
- Post between Tue-Thu, 8-10am CET for best reach
- Add a personal anecdote from Bernard/OpenClaw experience
- Consider adding a carousel (3-5 slides) for higher engagement
"""
    return draft


def main():
    parser = argparse.ArgumentParser(
        description="Generate weekly LinkedIn post drafts for ASI Builders"
    )
    parser.add_argument(
        "--topic", 
        choices=[t["topic"] for t in THEMES],
        help="Force a specific topic (default: auto-rotate by week)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file path (default: drafts/linkedin-post-WXX.md)"
    )
    parser.add_argument(
        "--list-topics",
        action="store_true",
        help="List available topics and exit"
    )
    args = parser.parse_args()
    
    if args.list_topics:
        for t in THEMES:
            print(f"  {t['topic']:25s} — {t['hook'][:60]}...")
        return
    
    theme = get_week_theme(args.topic)
    draft = generate_draft(theme)
    
    # Output path
    if args.output:
        out_path = Path(args.output)
    else:
        week_label = f"W{datetime.now().isocalendar()[1]}"
        DRAFTS_DIR.mkdir(exist_ok=True)
        out_path = DRAFTS_DIR / f"linkedin-post-{week_label}.md"
    
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(draft)
    print(f"✅ Draft generated: {out_path}")
    print(f"   Topic: {theme['topic']}")
    print(f"   Hook: {theme['hook'][:60]}...")
    print(f"   Next: Review and personalize before posting")


if __name__ == "__main__":
    main()
