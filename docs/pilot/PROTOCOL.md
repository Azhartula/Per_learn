# PerLearn delayed-outcome pilot protocol

## Purpose

Collect the first **non-simulated** signal that teaching-method assignment relates to delayed mastery. This is a protocol + dry-run package until human volunteers complete Session 2.

## Eligibility

- Consented adults or teens (16+) for the first wave
- Comfortable with Year 5 fraction questions
- Willing to return 24–72 hours later for a short no-help check

## Arms

Randomize participant to:
1. **adaptive_method** — bandit selects among four teaching methods
2. **fixed_worked_example** — always worked example

## Session 1 (~20 min)

1. Consent + learner code (no real names in shared logs)
2. Form A diagnostic (MCQ)
3. Method assignment per arm
4. Template lesson (Ollama optional; must pass integrity)
5. Practice (logged as `practice` — does **not** train policy)
6. Immediate post Form B (`immediate_post`)

## Gap

24–72 hours. No study materials.

## Session 2 (~8 min)

1. Form C delayed check only (`delayed_24h`)
2. For adaptive arm: update bandit with delayed score
3. Debrief

## Data

All events → `outputs/events/session_*.jsonl` (schema v1.0).  
Analysis → `scripts/run_pilot_analysis.py`.

## Ethics note

No school deployment in wave 1. Delete on request. Do not share identifiable data.
