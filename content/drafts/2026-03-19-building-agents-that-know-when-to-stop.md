---
title: "Building Agents That Know When to Stop"
type: public_content
review: none
project: asi-builders
author: bernard
date: 2026-03-19
tags: [ai-safety, agents, autonomy, alignment, engineering]
lang: en
word_count: 400
sources:
  - https://www.anthropic.com/news/the-case-for-targeted-regulation
  - https://arxiv.org/abs/2401.13138
  - https://openai.com/safety
---

# Building Agents That Know When to Stop

The AI safety conversation has largely focused on what models *should not say*. But as we ship autonomous agents — systems that take actions, not just generate text — the critical safety question becomes: **when should an agent stop acting?**

## The Autonomy Boundary Problem

Every agent system faces the same design choice: how much latitude does the agent get before it must check in with a human? Too little, and you've built an expensive autocomplete. Too much, and you're trusting a statistical model with irreversible actions.

The industry's current answer — "the user can always intervene" — is insufficient. If an agent executes 40 actions per minute, human oversight becomes theoretical. You've designed a system where humans *can* intervene but practically *won't*.

## Three Engineering Patterns That Work

From building production agent systems, three patterns consistently improve safety without destroying utility:

**1. Irreversibility scoring.** Every action gets a score: can it be undone? Sending an email = irreversible. Writing a draft = reversible. The agent can freely execute reversible actions but must pause and confirm before crossing the irreversibility threshold. This isn't about trust — it's about physics. Some actions have no undo button.

**2. Confidence-gated escalation.** The agent monitors its own uncertainty. When confidence drops below a threshold — ambiguous instructions, conflicting data, unfamiliar territory — it escalates rather than guessing. The key insight: an agent that says "I'm not sure, here are my options" is more useful than one that confidently picks wrong.

**3. Scope boundaries as architecture, not prompts.** Telling an agent "don't do X" in a system prompt is a suggestion. Encoding "X is not a callable function" in the tool layer is a guarantee. The most reliable safety comes from removing capabilities, not requesting restraint.

## Why This Matters Now

Anthropist's recent case for targeted AI regulation highlights the gap between model-level safety (refusals, RLHF) and system-level safety (what the agent can actually *do* in the world). Anthropic's own research shows that the most dangerous failure modes aren't jailbreaks — they're agents that execute correct-looking actions that compound into harm.

As agents move from demos to production, the builders who ship safely won't be the ones with the best safety disclaimers. They'll be the ones who engineered their agents to **stop before they're told to.**

The best safety feature is an agent that recognizes the edge of its competence — and stays inside it.

---

*ASI Builders: engineering intelligence that serves humanity. Follow for technical safety insights.*
