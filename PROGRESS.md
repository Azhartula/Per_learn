# Progress handoff

**Last updated:** 2026-11-18  
**Status:** Real-work track (integrity + offline eval + pilot protocol) — demo polish frozen  
**GitHub:** https://github.com/Azhartula/Per_learn  

## What is real now

- Lesson integrity: `answers_ok` vs `lesson_ok` ([`src/pll/lesson_integrity.py`](src/pll/lesson_integrity.py)); false GPU caption quarantined
- Event JSONL schema v1.0 ([`src/pll/events.py`](src/pll/events.py)) wired into loop + Streamlit
- Offline eval pack: [`outputs/eval/`](outputs/eval/) — BKT holdout + demo/neutral/adversarial policy ablations
- Question bank v2: **86** items, forms A/B/C, distractor→misconception maps
- Pilot protocol + dry-run analysis: [`docs/pilot/`](docs/pilot/), [`outputs/pilot/`](outputs/pilot/)

## Commands

```bash
# Tests
PYTHONPATH=src pytest -q

# Offline eval (ASSISTments + sim ablations)
PYTHONPATH=src python scripts/run_offline_eval.py

# Protocol dry-run (simulated respondents — not human efficacy)
PYTHONPATH=src python scripts/run_pilot_dryrun.py --n 16
PYTHONPATH=src python scripts/run_pilot_analysis.py
```

## Next for human evidence

Recruit 12–20 consented volunteers; run Session 1 + 24–72h Session 2 per [`docs/pilot/PROTOCOL.md`](docs/pilot/PROTOCOL.md).

## Rules

- Never add Cursor/AI as git co-author (use `git commit-tree` if injected).
- Do not claim child efficacy from dry-runs or demo-profile simulations.
