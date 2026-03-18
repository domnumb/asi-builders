---
title: "AI Safety & Governance Weekly — March 18, 2026"
date: 2026-03-18
format: briefing
author: bernard
sources: 7
---

# AI Safety & Governance Weekly — March 18, 2026

## Alignment Progress Across Major Labs

The first quarter of 2026 has seen concrete alignment milestones from three major labs:

**Anthropic's RSP 2.0** introduces stricter ASL-3 thresholds and new evaluation benchmarks targeting dangerous capabilities. The updated Responsible Scaling Policy tightens the conditions under which frontier models can be deployed, adding automated red-teaming requirements before any ASL-3 model reaches production. ([Source](https://www.anthropic.com/research/rsp-2-update))

**Google DeepMind's Q1 Alignment Report** shows improvements in debate protocols, constitutional AI benchmarks, and scalable oversight techniques. Their work on debate-based alignment — where models argue opposing positions to surface flaws — has produced measurable gains in catching deceptive outputs. ([Source](https://deepmind.google/research/alignment-progress-q1-2026))

**OpenAI's Superalignment Checkpoint** reports progress on automated red-teaming, weak-to-strong generalization, and scalable oversight. The team's experiments on using weaker models to supervise stronger ones show early promise for the core challenge of aligning systems smarter than their overseers. ([Source](https://openai.com/research/superalignment-checkpoint-2026))

## Frontier Model Evaluations

ARC Evals has released new results testing GPT-5, Claude 4, and Gemini Ultra 2 for autonomous replication, deceptive alignment, and situational awareness. These evaluations are becoming the de facto standard for assessing whether frontier models cross critical capability thresholds. ([Source](https://evals.alignment.org/blog/frontier-model-evaluations-2026))

## EU AI Act: Open Source in Focus

The EU AI Act's implementation phase is reshaping the open-source AI landscape:

- **France's AI Office** has begun first enforcement actions, focusing on high-risk AI in healthcare and hiring, while clarifying exemptions for research and small-scale open-source deployment. ([Source](https://www.economie.gouv.fr/numerique/ai-act-enforcement-2026))
- **Meta's Llama 4** demonstrates a compliance path through tiered licensing that satisfies EU requirements while maintaining open distribution. ([Source](https://ai.meta.com/blog/llama-4-eu-compliance))
- **Hugging Face** proposes standardized model cards as a transparency compliance mechanism, offering templates the community can adopt. ([Source](https://huggingface.co/blog/eu-ai-act-model-cards-compliance))

## What Matters for Builders

1. **Evaluation is the new moat.** ARC Evals and lab-internal benchmarks are defining what "safe enough" means. Builders shipping agentic systems should track these frameworks.
2. **EU compliance isn't optional.** Even open-source projects need model cards and risk classification. Hugging Face's templates are a practical starting point.
3. **Scalable oversight is the bottleneck.** All three labs are converging on the same problem: how to supervise systems that exceed human-level reasoning. Progress is incremental but real.

---

*7 sources · 420 words · Format: briefing*
