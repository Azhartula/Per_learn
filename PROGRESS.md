# Progress handoff

**Last updated:** 2026-11-17 (night)  
**Status:** Phase 1–4 + adaptive child demo + **real local GPU lessons**  
**GitHub:** https://github.com/Azhartula/Per_learn  
**Live demos:**
- https://azhartula.github.io/Per_learn/child.html
- https://azhartula.github.io/Per_learn/live.html

## Learn with me (interactive)
```bash
streamlit run app.py
# or CLI:
PYTHONPATH=src python scripts/learn_with_me.py --name Azhar
```
You answer samples → bandit adapts method → Qwen 7B lesson → delayed check trains the policy.

## Real GPU one-shot
```bash
ollama serve
ollama pull qwen2.5:7b
PYTHONPATH=src python scripts/run_live_gpu.py --skill ordering_fractions --mastery 0.25
```

## Rules
- Never add Cursor/AI as git co-author (use `git commit-tree` if injected).
