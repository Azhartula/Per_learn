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

The headline demo is a **multi-week child simulation**: Maya / Sam / Jordan learn over 10 weeks while the bandit switches teaching methods as mastery grows.

```bash
PYTHONPATH=src python scripts/run_child_demo.py
PYTHONPATH=src python scripts/build_demo_site.py
PYTHONPATH=src python scripts/serve_demo.py
# → http://127.0.0.1:8765/child.html
```

### Learn with me (you answer → it adapts)

**Streamlit UI (recommended):**

```bash
ollama serve          # if using GPU lessons
source .venv/bin/activate
streamlit run app.py
```

**CLI:**

```bash
PYTHONPATH=src python scripts/learn_with_me.py --name Azhar
PYTHONPATH=src python scripts/learn_with_me.py --name Azhar --status
PYTHONPATH=src python scripts/learn_with_me.py --name Azhar --no-ollama
```

Each session: sample quiz → bandit picks method → lesson (Qwen 7B) → practice → **unassisted check trains the bandit** → profile saved under `outputs/learners/`.

### Real local GPU lesson (Ollama)

```bash
PYTHONPATH=src python scripts/run_live_gpu.py --skill ordering_fractions --mastery 0.25
PYTHONPATH=src python scripts/run_phase3.py --mode demo --ollama --model qwen2.5:7b
```

Static files live in `docs/` for GitHub Pages:

- Pitch: https://azhartula.github.io/Per_learn/
- **Watch a child adapt:** https://azhartula.github.io/Per_learn/child.html
- **Real GPU lesson sample:** https://azhartula.github.io/Per_learn/live.html
- One-session snapshot: https://azhartula.github.io/Per_learn/parent.html

