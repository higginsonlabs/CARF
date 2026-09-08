# CARF Demo — Project Overview (for Claude Code)

## What this project is

A small proof-of-concept for **CARF (Cybernetic Agent Reliability Framework)** — an evaluation approach for AI agents that judges *how* an agent completed a task, not just whether its final answer was correct.

This supports a proposal to the **Mercor Research Fellowship**, extending Mercor's **APEX-Agents** benchmark. APEX-Agents currently grades an agent's final output against a rubric but never examines the trajectory (the sequence of steps) that produced it. CARF's core claim: two agents can land the same final score by very different routes — one steadily self-correcting, another drifting into the right answer — and that difference is invisible to outcome-only grading. CARF makes it visible by tracing whether facts established early in a task survive intact through to where they're used later.

CARF is loosely based on Stafford Beer's Viable System Model (a cybernetics framework for self-regulating systems), adapted so that a set of "judges" play the role of a coordinating/regulating layer above an agent's own actions.

## What this specific demo proves

On one small, hand-checkable task, the demo will show:

1. **Operational units** (what the agent needs to do) and **environmental elements** (the facts/data the task depends on) are both classified automatically from the task prompt alone.
2. The agent's actual trajectory is run step by step, and each step is tagged with which operational unit it fulfils and which environmental element(s) it drew on.
3. A judge examines the full tagged trajectory and: identifies failures, assesses dependencies (does each step correctly use the element it depends on, or does a value silently drift between steps?), and generates a structured reliability signal.
4. That signal is turned into a short, generated correction, fed back to the agent, and the affected step is re-run to see whether it self-corrects.

This is deliberately the smallest version that tests the real claim — that judging *relationships between steps* reveals something a single final-answer check cannot. It is explicitly not trying to cover the full APEX-Agents task set, the other three CARF judges (Process Regulation, Adaptation, Task-Coherence), or integration with Mercor's real evaluation harness (Archipelago) yet — those are deferred until this core mechanism is proven.

## Full step-by-step plan

**See `CARF_DEMO_PLAN.md` in this repo for the authoritative, detailed plan** — task definition, each function's exact responsibility, expected output shapes, and what's explicitly out of scope. Read that file before writing any code; it should be treated as the spec for `loop.py`.

## Current state of the repo

- `CARF_DEMO_PLAN.md` — the detailed plan (read this first)
- `OVERVIEW.md` — short public-facing description (for anyone browsing the repo)
- `loop.py` — scaffold only; all five functions are stubbed with `NotImplementedError` and docstrings describing what each should do
- `examples/bid_premium_task.md` — the one example task the demo runs against
- `.gitignore` — set up to exclude `.venv/`, `.env`, and generated run outputs
- Python virtual environment (`.venv`) already created; `google-generativeai` already installed

## What's needed next

- A Gemini API key (free tier, from Google AI Studio) is needed to actually run anything — not yet added. Check for a `.env` file / ask before assuming it exists.
- Implement the functions in `loop.py` in order, following `CARF_DEMO_PLAN.md` exactly — starting with `classify_operational_units`, since it needs nothing but one API call and no trajectory yet.
- Keep the scope disciplined: do not add extra judges, extra tasks, or Archipelago integration unless explicitly asked — the plan document lists what's deliberately deferred.

## How to use this document

Read this file and `CARF_DEMO_PLAN.md` together before making changes. This file gives the "why" and current status; the plan file gives the exact "what" for each step.
