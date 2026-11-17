# PerLearn evaluation protocol (AI learning platforms)

## Purpose

Prove the **method layer** inside an AI learning product:

diagnose gap → choose teaching style → teach → check if it stuck → update policy.

This is product evaluation for AI platforms — **not** a “go recruit research volunteers” pitch.

## Primary proof path (what we pitch)

**LLM learner agents** (local Qwen) run the same loop a student would:

1. Diagnostic (Form A)
2. Method assignment (`adaptive_method` vs fixed baseline)
3. Lesson + practice
4. Immediate post (Form B)
5. Delayed check with faded memory (Form C) → trains the policy

Command:

```bash
PYTHONPATH=src python scripts/run_qwen_agent_pilot.py --n 16
```

Logs use `respondent=llm_agent`. This matches how AI platforms ship: agent/synthetic traffic + event telemetry before (and alongside) live users.

## What companies actually care about

| Proof | Why it matters |
|-------|----------------|
| Event schema + integrity gates | Safe to embed in their tutor |
| Offline ASSISTments BKT eval | Learner model isn’t vapor |
| Qwen agent cohort delayed loop | Method policy runs end-to-end on AI learners |
| Method match vs mismatch signal | “How we teach” moves outcomes, not only “what next” |

## Optional later (not the pitch)

If a **school / tutoring partner** wants field outcomes on their own learners, reuse this protocol with `respondent=human` and a real 24–72h gap. That is a **partner deployment**, not our go-to-market story.

## Arms

1. `adaptive_method` — contextual bandit picks teaching style  
2. `fixed_worked_example` — fixed pedagogy baseline  

## Data

Events → `outputs/events/session_*.jsonl`  
Qwen pack → `outputs/pilot_qwen/`  
Analysis → `scripts/run_pilot_analysis.py`
