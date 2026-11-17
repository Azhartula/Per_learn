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

### Real local GPU lesson (Ollama)

Requires [Ollama](https://ollama.com) + a light model on your GPU (RTX 3060 works):

```bash
ollama serve          # if not already running
ollama pull qwen2.5:7b
PYTHONPATH=src python scripts/run_live_gpu.py --skill ordering_fractions --mastery 0.25
# or full loop with local model:
PYTHONPATH=src python scripts/run_phase3.py --mode demo --ollama --model qwen2.5:7b
```

Static files live in `docs/` for GitHub Pages:

- Pitch: https://azhartula.github.io/Per_learn/
- **Watch a child adapt:** https://azhartula.github.io/Per_learn/child.html
- **Real GPU lesson sample:** https://azhartula.github.io/Per_learn/live.html
- One-session snapshot: https://azhartula.github.io/Per_learn/parent.html

