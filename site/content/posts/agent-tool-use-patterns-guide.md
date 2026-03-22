---
title: "Agent Tool Use: Patterns That Actually Work"
date: 2026-03-22
type: public_content
review: none
author: asi-builders
tags: [agents, tool-use, function-calling, patterns]
description: "Practical patterns for AI agent tool use — from single-shot function calling to multi-step orchestration. Based on real benchmarks and production experience."
---

# Agent Tool Use: Patterns That Actually Work

Tool use is what separates a chatbot from an agent. But the gap between "my agent can call a function" and "my agent reliably completes multi-step tasks" is enormous. Here's what works in production.

## The Tool Use Spectrum

Agent tool use exists on a spectrum of complexity:

1. **Single-shot function calling** — one tool, one result, done. Example: weather lookup.
2. **Sequential chains** — tool A output feeds tool B. Example: search → fetch → summarize.
3. **Conditional branching** — the agent decides which tool to use based on intermediate results.
4. **Parallel execution** — multiple tools called simultaneously when independent.
5. **Recursive tool use** — the agent calls itself as a tool (sub-agents, delegation).

Most production agents live at levels 2-3. Levels 4-5 are where things get interesting — and fragile.

## Pattern 1: Schema-First Design

The most common failure mode isn't the LLM choosing the wrong tool. It's the tool schema being ambiguous.

**What works:**
- Explicit parameter descriptions with examples
- Enum types instead of free-text where possible
- Required vs optional clearly marked
- Return type documented in the description (the model reads it)

**What fails:**
- Generic parameter names (`data`, `input`, `config`)
- Missing descriptions ("the model will figure it out")
- Overloaded tools that do 5 things based on a `mode` parameter

The Berkeley Function-Calling Leaderboard (BFCL) tests exactly this: given a schema, can the model produce a correct call? Top models hit 90%+ on simple calls but drop to 60-70% on nested/complex schemas. The schema is your leverage point.

## Pattern 2: Observation-Action Loops

The ReAct pattern (Reason + Act) remains the most reliable architecture for multi-step tool use:

```
Thought: I need to find the user's recent orders
Action: search_orders(user_id="123", limit=5)
Observation: [order_1, order_2, ...]
Thought: Order 2 has a pending refund, let me check details
Action: get_order(order_id="order_2")
Observation: {status: "refund_pending", amount: 49.99}
```

The key insight: **force the model to observe before acting again**. Without explicit observation steps, agents tend to hallucinate tool results or skip verification.

In production, this means:
- Always inject the tool result back into context
- Don't let the agent assume what a tool returned
- Add a verification step after critical actions ("did the write succeed?")

## Pattern 3: Graceful Degradation

Tools fail. APIs time out. Rate limits hit. The difference between a demo agent and a production agent is how it handles failure.

**Tier 1: Retry with backoff**
```
Tool failed (429) → wait 2s → retry → wait 4s → retry
```

**Tier 2: Fallback tools**
```
Primary API down → use cached data → use alternative source
```

**Tier 3: Honest failure**
```
"I couldn't retrieve your order status — the system returned an error. 
Here's what I can tell you from cached data: ..."
```

The worst pattern is silent failure: the agent pretends the tool worked and confabulates a result. This is where invariant guards and result verification matter most.

## Pattern 4: Tool Budgets

Unbounded tool use is a cost and latency disaster. Production agents need budgets:

- **Call budget**: max N tool calls per task (prevents infinite loops)
- **Token budget**: stop if cumulative tool output exceeds X tokens
- **Time budget**: hard timeout on the overall task
- **Cost budget**: track API costs per tool call

Without budgets, a single malformed query can trigger 50+ API calls. We've seen it. It's expensive and slow.

## Pattern 5: Tool Selection as Classification

When an agent has 20+ tools, selection becomes a classification problem. Two approaches work:

**A. Hierarchical routing**
Group tools into categories. First, classify the intent ("is this a read or write?"), then select within the category. Reduces the choice space from 20 to 5.

**B. Dynamic tool injection**
Don't give the agent all tools at once. Based on context, inject only relevant tools. A customer support agent doesn't need deployment tools.

Both approaches reduce hallucinated tool calls — the agent inventing tools that don't exist because the schema space is too large.

## Pattern 6: Multi-Agent Tool Delegation

The most powerful pattern: agents as tools for other agents.

```
Orchestrator → delegates "research" to Research Agent
            → delegates "code fix" to Coding Agent  
            → delegates "review" to Review Agent
```

This works when:
- Each sub-agent has a focused tool set (not the full menu)
- The orchestrator receives structured results (not raw output)
- There's a timeout/budget per delegation
- Results are verified before aggregation

It fails when:
- Sub-agents have overlapping responsibilities
- The orchestrator can't verify sub-agent output
- There's no isolation (sub-agent A can interfere with sub-agent B)

## Benchmarks: Where We Stand (2025-2026)

The BFCL v3 leaderboard shows current state:
- **Simple function calls**: GPT-4o, Claude 3.5, Gemini 2 all above 90%
- **Parallel calls**: Drop to 75-85% — models struggle with independence detection
- **Multi-step with state**: 60-75% — the real frontier
- **Irrelevant tool rejection**: 80-90% — models are getting better at saying "none of these tools apply"

The gap is in multi-step stateful tasks. This is where architecture (patterns above) matters more than model capability.

## Practical Checklist

Before shipping an agent with tools:

- [ ] Each tool has a clear, unambiguous schema with examples
- [ ] Tool results are always injected back (no assumed results)
- [ ] Failure modes are handled at 3 tiers (retry, fallback, honest failure)
- [ ] Call/token/time budgets are set
- [ ] Tool selection is bounded (hierarchical or dynamic injection)
- [ ] Critical actions have verification steps
- [ ] Sub-agent delegation has timeouts and result validation

## Sources

- [Berkeley Function-Calling Leaderboard (BFCL)](https://gorilla.cs.berkeley.edu/leaderboard.html) — benchmark reference
- [Anthropic: Tool Use Best Practices](https://docs.anthropic.com/en/docs/build-with-claude/tool-use) — schema design
- [OpenAI: Function Calling Guide](https://platform.openai.com/docs/guides/function-calling) — patterns
- [LangChain Tool Use Docs](https://python.langchain.com/docs/how_to/#tools) — orchestration patterns
- [Gorilla LLM Project](https://gorilla.cs.berkeley.edu/) — tool use research
