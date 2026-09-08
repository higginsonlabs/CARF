# CARF Demo Plan

**Project:** A minimal, working proof of concept for CARF — showing that operational units and environmental elements can be classified directly from a task prompt, that an agent's actual trajectory can be tagged against them, and that a judge can trace whether a dependency between them survives across steps — turning what it finds into feedback that changes the agent's next attempt.

**Maps directly onto the CARF feedback loop diagram** ("APEX Evaluation Structure with CARF Feedback Loop"):
- `Task` → the finance prompt, split into explicit steps.
- `Operational Units` / `Environmental Elements` → classified from the prompt before the agent runs, then tagged onto each step as it runs.
- `Agent` / `World` / `Output` → each step's output, produced one at a time.
- `Judge LM` → the Coordination Judge, checking unit↔element consistency across the full step sequence.
- `CARF Feedback (Regulatory Signal)`: **Identify failures → Assess dependencies → Generate reliability signal**.
- `CARF Output` (grading mode) vs `Optional Feedback Cycle` (returned to the agent) — both produced from the same signal.

---

## Status

- [ ] Step 0 — Task chosen and split into explicit steps
- [ ] Step 1 — Operational Unit Classifier built (from the prompt)
- [ ] Step 2 — Environmental Element Classifier built (from the prompt)
- [ ] Step 3 — Trajectory captured, each step tagged with unit + element used
- [ ] Step 4 — Judge built: identify failures → assess dependencies → generate signal
- [ ] Step 5 — CARF Output and feedback sentence both generated from the signal
- [ ] Step 6 — Loop closed (Attempt 2 compared to Attempt 1)

---

## Step 0 — Pick a task with a real cross-step dependency

A task naturally splittable into a few small steps that all depend on shared facts. Example:

**Note on the manual split below:** for this demo, Steps A–D are called out explicitly and run as separate calls so the trajectory is easy to build and inspect by hand. In a working system, the agent would decide its own steps autonomously while completing the task — this manual split is a simplification for the prototype, not a claim that agents need to be told how to break down a task. The Operational Unit Classifier (Step 1) is what a real system would use instead: it infers the likely steps from the prompt alone, ahead of time, rather than having them hand-authored.

> A merger has a bid premium of 20% and cash consideration of 15%.
> **Step A:** State these deal terms clearly, on their own.
> **Step B:** Using the terms from Step A, calculate the implied offer price on a $40 share price.
> **Step C:** Using the terms from Step A, calculate the cash portion of a $10,000 investment.
> **Step D:** Summarise both results.

## Step 1 — Operational Unit Classifier

Given the task prompt, automatically identify and label the distinct operational units it requires — `1a`, `1b`, `1c`… — with no fixed number, inferred from the task itself, each with a short description. For the example above, this should produce something close to: `1a — state deal terms`, `1b — calculate offer price`, `1c — calculate cash portion`, `1d — summarise results`.

## Step 2 — Environmental Element Classifier

Given the same prompt, identify the specific facts/data the task depends on — the equivalent of Figure 2's `1E`/`2E`/`3E`. For the example: `1E — bid premium (20%)`, `2E — cash consideration (15%)`, `3E — share price ($40)`.

**Done when:** both classifiers run on the task and produce sensible, task-specific lists — not a fixed template.

## Step 3 — Run the trajectory, tagged

Run Steps A–D as separate calls, in sequence, each seeing only the steps before it. As part of each step's own output, have the agent state which operational unit it's fulfilling and which environmental element(s) it used. Save the whole thing — outputs plus tags — as one ordered trajectory record.

**Done when:** you have a saved, ordered sequence of four step-outputs, each tagged with a unit and the element(s) it drew on, and you know by hand whether a drift occurred anywhere in it.

## Step 4 — Build the judge

One judge call, given the full tagged trajectory, instructed to:
1. **Identify failures** — did any step's output conflict with an earlier one?
2. **Assess dependencies** — using the unit/element tags, trace whether each operational unit correctly drew on the environmental element it was supposed to (e.g. did `1b` actually use `1E`'s value, or silently substitute something else?).
3. **Generate a reliability signal** — a structured verdict, not just pass/fail on the final answer.

Output shaped like Archipelago's real `GradeResult`:
```json
{
  "judge_grade": "fail",
  "score": 0.0,
  "grade_rationale": "1E (bid premium, 20%) was correctly used in 1b but not in 1c, which used 22% instead — the dependency broke between 1a and 1c."
}
```

## Step 5 — Produce both CARF outputs

- **CARF Output** — the structured grade above, usable for process-aware scoring on its own.
- **Optional Feedback Cycle** — a short, generated correction sentence derived from the same signal, e.g. *"Note: 1E (bid premium) was stated as 20% in 1a, but 1c used 22%. Recheck 1c against 1a before finalising."*

## Step 6 — Close the loop

Re-run the affected step (1c) with the feedback sentence appended, and see whether it corrects to match 1a. Compare Attempt 1's step output to Attempt 2's.

**Done when:** you can show, side by side — the operational unit list, the environmental element list, the full tagged trajectory (with the drift), the judge's dependency-assessment verdict, the feedback sentence, and the corrected step — as one clean, real example.

---

## What this proves, and what it doesn't

Proves: operational units and environmental elements can be classified directly from a prompt, an agent's real trajectory can be tagged against that classification, and a judge can use those tags to trace whether a dependency survives across steps — catching a specific, attributable break, not just "something's wrong somewhere."

Does not prove: that this scales to the full messy BBDC/TVPG task, or generalises beyond this one example, or improves reliability across many runs.

## Explicitly not in scope for this pass

- A baseline (outcome-only) judge comparison
- The Task-Coherence, Process Regulation, or Adaptation judges
- A second task
- Any Archipelago/Docker integration

## Repo layout

```
carf-apex-agents/
├── CARF_DEMO_PLAN.md
├── loop.py                 # classifiers + tagged trajectory + judge + feedback retry
├── examples/
│   └── bid_premium_task.md
├── runs/
│   └── run_001.json        # units, elements, tagged trajectory, judge signal, feedback, corrected step
└── README.md
```
