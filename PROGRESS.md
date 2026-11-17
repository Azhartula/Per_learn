# Progress handoff

**Last updated:** 2026-11-17 (night)  
**Status:** Phase 1–4 + adaptive child demo + **real local GPU lessons**  
**GitHub:** https://github.com/Azhartula/Per_learn  
**Live demos:**
- https://azhartula.github.io/Per_learn/child.html
- https://azhartula.github.io/Per_learn/live.html

## Real GPU path
```bash
ollama serve
ollama pull qwen2.5:3b
PYTHONPATH=src python scripts/run_live_gpu.py --skill ordering_fractions --mastery 0.25
```
Model: Qwen 2.5 3B via Ollama on RTX 3060. Answers SymPy-gated.

## Rules
- Never add Cursor/AI as git co-author (use `git commit-tree` if injected).
