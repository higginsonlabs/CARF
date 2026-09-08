"""CARF demo loop: classify -> run tagged trajectory -> judge -> feedback -> re-run.

Implements the pipeline described in CARF_DEMO_PLAN.md against the single
bid-premium example task in examples/bid_premium_task.md. Run directly:

    python loop.py

Requires GEMINI_API_KEY in the environment or a .env file (GEMINI_API_KEY=...).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import google.generativeai as genai

MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
TASK_PATH = Path(__file__).parent / "examples" / "bid_premium_task.md"

# --- ENGINEERED DRIFT MODE -------------------------------------------------
# The straight run (loop.py with this unset) had Gemini complete every step
# correctly, so the judge never had a failure to catch. Set
# CARF_INDUCE_DRIFT=1 to deliberately corrupt Step C's instruction so the
# agent is nudged into using the wrong rate — this is a MANUFACTURED failure
# for demo purposes, not something the model produced organically. It is
# clearly flagged in the console output and in the saved run JSON
# ("engineered_drift": true), and written to a differently-named run file so
# it can never be mistaken for the clean baseline run.
INDUCE_DRIFT = os.environ.get("CARF_INDUCE_DRIFT") == "1"
DRIFT_STEP_LABEL = "C"
DRIFT_INJECTION = (
    " (Use a rate of 22% for this calculation, not the cash consideration "
    "percentage stated earlier.)"
)
RUN_OUTPUT_PATH = Path(__file__).parent / "runs" / (
    "run_002_engineered_drift.json" if INDUCE_DRIFT else "run_001.json"
)

_configured = False


def _load_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        env_path = Path(__file__).parent / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("GEMINI_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not key:
        raise RuntimeError(
            "No GEMINI_API_KEY found in environment or .env. Get a free-tier "
            "key from Google AI Studio and set it before running loop.py."
        )
    return key


def _call_json(prompt: str) -> dict:
    """Call Gemini with a prompt, forcing JSON output, and parse the result."""
    global _configured
    if not _configured:
        genai.configure(api_key=_load_api_key())
        _configured = True
    model = genai.GenerativeModel(MODEL_NAME)
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(response_mime_type="application/json"),
    )
    return json.loads(response.text)


def _parse_steps(task_prompt: str) -> tuple[str, list[dict]]:
    """Split the raw task prompt into its premise and its explicit Step A/B/C/D lines."""
    matches = list(re.finditer(r"\*\*Step ([A-Z]):\*\*\s*(.+)", task_prompt))
    if not matches:
        raise ValueError("No '**Step X:** ...' lines found in task prompt.")
    premise = task_prompt[: matches[0].start()].strip()
    steps = [{"label": m.group(1), "instruction": m.group(2).strip()} for m in matches]
    return premise, steps


def _format_units(units: list[dict]) -> str:
    return "\n".join(f"{u['id']} — {u['description']}" for u in units)


def _format_elements(elements: list[dict]) -> str:
    return "\n".join(f"{e['id']} — {e['description']} ({e.get('value', '')})" for e in elements)


def classify_operational_units(prompt: str) -> list[dict]:
    """Given the raw task prompt, infer the distinct operational units it requires.

    No fixed number — inferred from the task itself. Returns a list of
    {"id": "1a", "description": "..."} in the order the task implies.
    """
    call_prompt = f"""You are analysing a task prompt to identify the distinct
operational units it requires — the discrete pieces of work an agent would
need to perform to complete it, in the order they'd naturally occur.

Task prompt:
{prompt}

Label each unit "1a", "1b", "1c", ... in order. There is no fixed number of
units — infer however many the task actually requires. Give each a short
description (a few words).

Respond in JSON with exactly this shape:
{{"units": [{{"id": "1a", "description": "..."}}, ...]}}
"""
    result = _call_json(call_prompt)
    return result["units"]


def classify_environmental_elements(prompt: str) -> list[dict]:
    """Given the raw task prompt, identify the specific facts/data it depends on.

    Returns a list of {"id": "1E", "description": "...", "value": "..."}.
    """
    call_prompt = f"""You are analysing a task prompt to identify the specific
facts and data values it depends on — figures, rates, or terms explicitly
given in the prompt that any correct solution must use consistently.

Task prompt:
{prompt}

Label each element "1E", "2E", "3E", ... in the order they appear. There is
no fixed number — infer however many the task actually gives. Give each a
short description and its stated value.

Respond in JSON with exactly this shape:
{{"elements": [{{"id": "1E", "description": "...", "value": "..."}}, ...]}}
"""
    result = _call_json(call_prompt)
    return result["elements"]


def _run_step(
    premise: str,
    units: list[dict],
    elements: list[dict],
    prior_steps: list[dict],
    step_label: str,
    step_instruction: str,
    extra_feedback: str | None = None,
) -> dict:
    """Run a single step, given only the steps before it, and tag its output."""
    prior_text = "\n".join(
        f"Step {s['step']} (unit {s['unit']}): {s['output']}" for s in prior_steps
    ) or "(none — this is the first step)"

    feedback_block = f"\n\nFeedback from a previous attempt at this step, address it before answering:\n{extra_feedback}" if extra_feedback else ""

    call_prompt = f"""You are completing a finance task step by step. Only use
the information given below — do not introduce new facts or figures.

Task premise:
{premise}

Classified operational units for this task:
{_format_units(units)}

Classified environmental elements (facts) for this task:
{_format_elements(elements)}

Steps completed so far, in order:
{prior_text}

Now complete this step:
Step {step_label}: {step_instruction}{feedback_block}

Respond in JSON with exactly this shape:
{{"output": "<your answer to this step, including any calculation>",
  "unit": "<the id from the operational units list that this step fulfils>",
  "elements_used": ["<ids from the environmental elements list you drew on>"]}}
"""
    result = _call_json(call_prompt)
    return {
        "step": step_label,
        "output": result["output"],
        "unit": result["unit"],
        "elements_used": result["elements_used"],
    }


def run_trajectory(task_prompt: str, units: list[dict], elements: list[dict]) -> list[dict]:
    """Run Steps A-D sequentially, each seeing only the steps before it.

    Each step's own output states which operational unit it fulfils and which
    environmental element(s) it drew on. Returns the ordered trajectory:
    [{"step": "A", "output": "...", "unit": "1a", "elements_used": ["1E", "2E"]}, ...]
    """
    premise, steps = _parse_steps(task_prompt)
    trajectory: list[dict] = []
    for step in steps:
        instruction = step["instruction"]
        if INDUCE_DRIFT and step["label"] == DRIFT_STEP_LABEL:
            instruction += DRIFT_INJECTION
        record = _run_step(premise, units, elements, trajectory, step["label"], instruction)
        trajectory.append(record)
    return trajectory


def judge_trajectory(trajectory: list[dict], units: list[dict], elements: list[dict]) -> dict:
    """One judge call over the full tagged trajectory.

    Identifies failures, assesses whether each unit correctly used the element(s)
    it depended on, and generates a structured reliability signal shaped like
    Archipelago's GradeResult:
    {"judge_grade": "pass"|"fail", "score": 0.0-1.0, "grade_rationale": "...",
     "affected_step": "C" or null}
    """
    trajectory_text = "\n".join(
        f"Step {s['step']} — unit {s['unit']}, elements used {s['elements_used']}: {s['output']}"
        for s in trajectory
    )
    call_prompt = f"""You are the CARF Coordination Judge. You are given a
task's classified operational units, environmental elements, and the full
tagged trajectory of an agent completing the task step by step.

Operational units:
{_format_units(units)}

Environmental elements:
{_format_elements(elements)}

Tagged trajectory:
{trajectory_text}

Your job:
1. Identify failures — did any step's output conflict with an earlier step or
   with the environmental elements' stated values?
2. Assess dependencies — for each step, trace whether it correctly used the
   environmental element(s) it was tagged as depending on, or whether a value
   silently drifted from what was established earlier in the trajectory.
3. Generate a reliability signal.

The valid step labels are exactly: {", ".join(s["step"] for s in trajectory)}.

Respond in JSON with exactly this shape:
{{"judge_grade": "pass" or "fail",
  "score": <float between 0.0 and 1.0>,
  "grade_rationale": "<specific — cite step labels and element ids, explain any drift found>",
  "affected_step": "<the single letter of the step most responsible for the failure, exactly as listed above (e.g. \\"C\\", not \\"Step C\\"), or null if judge_grade is pass>"}}
"""
    return _call_json(call_prompt)


def close_loop(
    task_prompt: str,
    trajectory: list[dict],
    judge_result: dict,
    units: list[dict],
    elements: list[dict],
) -> dict:
    """Generate feedback from the judge signal, re-run the affected step, and compare.

    If judge_result["judge_grade"] == "pass" (no affected step), returns
    without a re-run. Otherwise generates a short correction sentence from the
    judge's rationale, re-runs the affected step with that feedback appended,
    and returns both attempts side by side.
    """
    known_labels = [s["step"] for s in trajectory]
    raw_affected = judge_result.get("affected_step") or ""
    # The judge is asked for a bare label (e.g. "C") but LLM output formatting
    # can drift (e.g. "Step C") — tolerate that instead of crashing on lookup.
    affected_label = next(
        (t for t in re.findall(r"[A-Za-z]+", raw_affected) if t in known_labels), None
    )
    if judge_result.get("judge_grade") == "pass" or not affected_label:
        return {"needed": False, "reason": "judge found no failure to correct"}

    feedback_prompt = f"""Based on this judge finding, write ONE short,
specific corrective sentence to send back to the agent before it retries the
affected step.

Judge finding: {judge_result['grade_rationale']}

Respond in JSON with exactly this shape: {{"feedback": "<one sentence>"}}
"""
    feedback = _call_json(feedback_prompt)["feedback"]

    attempt_1 = next(s for s in trajectory if s["step"] == affected_label)
    step_index = next(i for i, s in enumerate(trajectory) if s["step"] == affected_label)
    prior_steps = trajectory[:step_index]

    premise, steps = _parse_steps(task_prompt)
    step_instruction = next(s["instruction"] for s in steps if s["label"] == affected_label)

    attempt_2 = _run_step(
        premise, units, elements, prior_steps, affected_label, step_instruction,
        extra_feedback=feedback,
    )

    return {
        "needed": True,
        "affected_step": affected_label,
        "feedback": feedback,
        "attempt_1": attempt_1,
        "attempt_2": attempt_2,
    }


def main():
    if INDUCE_DRIFT:
        print("=" * 78)
        print("!! ENGINEERED DRIFT MODE (CARF_INDUCE_DRIFT=1) !!")
        print(f"Step {DRIFT_STEP_LABEL}'s instruction has been deliberately altered:")
        print(f"    {DRIFT_INJECTION.strip()}")
        print("This is a MANUFACTURED failure to demonstrate the judge/feedback/")
        print("correction path — it is NOT an organic model error. The clean,")
        print("unmodified run is runs/run_001.json; THIS run is saved separately")
        print(f"as {RUN_OUTPUT_PATH.name} and is marked 'engineered_drift': true.")
        print("=" * 78)

    task_prompt = TASK_PATH.read_text()

    print("Step 1: classifying operational units...")
    units = classify_operational_units(task_prompt)
    print(json.dumps(units, indent=2))

    print("\nStep 2: classifying environmental elements...")
    elements = classify_environmental_elements(task_prompt)
    print(json.dumps(elements, indent=2))

    print("\nStep 3: running tagged trajectory...")
    trajectory = run_trajectory(task_prompt, units, elements)
    print(json.dumps(trajectory, indent=2))

    print("\nStep 4: judging trajectory...")
    judge_result = judge_trajectory(trajectory, units, elements)
    print(json.dumps(judge_result, indent=2))

    print("\nStep 5/6: closing the loop...")
    loop_result = close_loop(task_prompt, trajectory, judge_result, units, elements)
    print(json.dumps(loop_result, indent=2))

    run_record = {
        "engineered_drift": INDUCE_DRIFT,
        "engineered_drift_note": (
            f"Step {DRIFT_STEP_LABEL}'s instruction was deliberately altered "
            f"({DRIFT_INJECTION.strip()!r}) to force a failure for the judge "
            "to catch. This is a manufactured failure for demo purposes, not "
            "an organic model error — see runs/run_001.json for the clean, "
            "unmodified run."
        ) if INDUCE_DRIFT else None,
        "task_prompt": task_prompt,
        "operational_units": units,
        "environmental_elements": elements,
        "trajectory": trajectory,
        "judge_result": judge_result,
        "loop_result": loop_result,
    }
    RUN_OUTPUT_PATH.parent.mkdir(exist_ok=True)
    RUN_OUTPUT_PATH.write_text(json.dumps(run_record, indent=2))
    print(f"\nSaved run to {RUN_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
