# Progress handoff

**Last updated:** 2026-11-17 (evening)  
**Status:** Phase 1 + Phase 2 complete.

## Done

### Phase 1
- BKT + contextual bandit simulation
- Chart: `outputs/phase1_time_to_mastery.png`

### Phase 2
- Question bank: `data/questions/year5_fractions.json` (38 items, 6 skills)
- Prompt templates: `content/prompts/*.txt` (4 methods)
- SymPy verifier: `src/pll/sympy_check.py` (35/35 numeric items OK)
- Lesson generator: `src/pll/lessons.py` (template offline; optional `--llm`)
- Demo lessons: `outputs/lessons/`

```bash
source .venv/bin/activate
PYTHONPATH=src python scripts/run_phase2.py --skill multiply_fractions
```

## Next: Phase 3
Thin live loop: diagnostic quiz → bandit picks method → generate lesson → delayed check stub → print parent summary.
