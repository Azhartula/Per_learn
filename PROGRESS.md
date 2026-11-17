# Progress handoff

**Last updated:** 2026-11-18  
**Status:** Buyer Results Demo for AI video schools  
**GitHub:** https://github.com/Azhartula/Per_learn  

## Product framing

**ICP:** Homeschool / AI-school platforms that generate AI learning videos.

**Their stack:** generate video → watch → quiz → next topic.  
**Our layer:** evaluate → weak/strong + which style sticks → next **short specialised** video brief.

**Buyer value:** personal-level understanding + **lower render minutes** per mastered skill.

## Meeting demo (default)

```bash
streamlit run app.py
# → Show results demo →
```

Runbook: [`docs/buyer/MEETING_RUNBOOK.md`](docs/buyer/MEETING_RUNBOOK.md)  
Pack: [`outputs/buyer_demo/`](outputs/buyer_demo/)

```bash
PYTHONPATH=src python scripts/build_buyer_results_pack.py
```

## Other proof

```bash
PYTHONPATH=src pytest -q
PYTHONPATH=src python scripts/run_offline_eval.py
PYTHONPATH=src python scripts/run_qwen_agent_pilot.py --n 16
```

## Rules

- Never add Cursor/AI as git co-author.
- Label agent runs `respondent=llm_agent`.
- Cost figures are duration proxies, not GPU invoices.
