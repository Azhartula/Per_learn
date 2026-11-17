# Qwen agent cohort — AI-platform proof

**respondent=`llm_agent`**

This is the evaluation path we pitch to AI learning companies:

synthetic / agent learners run the same teaching-method loop the product will run on users.

It is **not** a volunteer recruitment study.

## Latest signal (stress test)

See `qwen_agent_summary.json`:

- When assigned method **matched** persona style bias → higher delayed mean
- When **mismatched** → lower delayed mean

Use as a pipeline + method-sensitivity demo. Pair with offline ASSISTments eval for technical depth.

## Run

```bash
PYTHONPATH=src python scripts/run_qwen_agent_pilot.py --n 16
```
