# CARF Demo

A small proof-of-concept for **CARF (Cybernetic Agent Reliability Framework)** — an evaluation approach for AI agents that judges *how* an agent completed a task, not just whether its final answer was correct.

Most agent benchmarks grade only the final output. CARF traces whether facts established early in a task survive intact through to where they're used later — catching agents that land on the right answer by drifting through wrong intermediate steps, which outcome-only grading can't see.

This demo runs a single hand-checkable finance task end to end: classify the task's operational units and environmental elements from the prompt alone, run the task step by step, tag each step against those classifications, and have a judge trace whether each step correctly used the facts it depended on — turning what it finds into feedback and re-running the affected step.

See `PROJECT_OVERVIEW.md` and `CARF_DEMO_PLAN.md` for the full design and build plan.
