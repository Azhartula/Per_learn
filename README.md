# Personalized Learning Loop

NGEdu already knows *what* to learn next. This module figures out *how* this child learns best — measured by delayed mastery, not practice scores.

## Quick start

```bash
cd Per_learn
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Phase 1 — bandit simulation chart
python scripts/download_data.py   # if data/as.csv missing
PYTHONPATH=src python scripts/run_phase1.py

# Phase 2 — question bank + method lessons + SymPy checks
PYTHONPATH=src python scripts/validate_bank.py
PYTHONPATH=src python scripts/run_phase2.py --skill multiply_fractions
```

Optional LLM generation (OpenAI-compatible; answers still SymPy-checked):

```bash
export PLL_API_KEY=...
export PLL_BASE_URL=https://api.openai.com/v1   # or Groq / OpenRouter / etc.
export PLL_MODEL=gpt-4o-mini
PYTHONPATH=src python scripts/run_phase2.py --skill multiply_fractions --llm
```

## Phase 1 — simulation

Proves the bandit finds each child's best teaching method faster than fixed/random.

Outputs in `outputs/`:
- `phase1_time_to_mastery.png`
- `phase1_metrics.json`

## Phase 2 — content spine

- `data/questions/year5_fractions.json` — 38 Year 5 items, 6 skills, misconception tags
- `content/prompts/` — one prompt template per teaching method
- SymPy verifies every numeric answer before a lesson is marked safe
- Template lessons work offline; `--llm` is optional

```bash
PYTHONPATH=src python scripts/run_phase2.py --skill ordering_fractions --method visual
```

Lessons land in `outputs/lessons/`.

## Four teaching methods

1. Worked example first  
2. Problem first  
3. Visual explanation  
4. Real-world story / analogy  

## Phase 3 — live loop

```bash
# Simulated student (good for pitches)
PYTHONPATH=src python scripts/run_phase3.py --name Alex --mode demo

# Type answers yourself
PYTHONPATH=src python scripts/run_phase3.py --name Alex --mode interactive
```

Flow: adaptive diagnostic → contextual bandit picks method → SymPy-verified lesson → delayed unassisted check → parent summary.

Outputs in `outputs/sessions/`.

## Phase 4 — shareable demo site

```bash
PYTHONPATH=src python scripts/build_demo_site.py --refresh-session
PYTHONPATH=src python scripts/serve_demo.py
# → http://127.0.0.1:8765/
# → http://127.0.0.1:8765/parent.html
```

Static files live in `docs/` for GitHub Pages:

- Pitch: https://azhartula.github.io/Per_learn/
- Parent dashboard: https://azhartula.github.io/Per_learn/parent.html

