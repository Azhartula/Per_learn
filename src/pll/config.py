"""Shared constants for simulation and offline evaluation."""

from __future__ import annotations

# Teaching methods under test (keep small — more methods need more data).
METHODS = (
    "worked_example",
    "problem_first",
    "visual",
    "story_analogy",
)

# ASSISTments 2009 skill names that contain "frac".
FRACTION_SKILLS = (
    "Addition and Subtraction Fractions",
    "Ordering Fractions",
    "Multiplication Fractions",
    "Division Fractions",
    "Equivalent Fractions",
    "Fraction Of",
    "Conversion of Fraction Decimals Percents",
)

# Primary skill for the first chart (balanced prior, clear learn rate).
DEFAULT_SKILL = "Multiplication Fractions"

# Mastery threshold used by the simulator and chart.
MASTERY_THRESHOLD = 0.88
STREAK_REQUIRED = 2  # consecutive strong delayed checks

# Simulation defaults.
N_STUDENTS = 100
MAX_SESSIONS = 30
DELAYED_CHECK_ITEMS = 4
PRACTICE_ITEMS = 2
RNG_SEED = 42

# Expertise-reversal prior: low mastery → scaffolded methods win;
# high mastery → problem-first wins. Indices into METHODS.
# 0=worked_example, 1=problem_first, 2=visual, 3=story_analogy
METHOD_PRIOR_BY_BIN = {
    "novice": (0, 2),       # worked example or visual
    "intermediate": (2, 3), # visual or story
    "advanced": (1,),       # problem first
}

# --- Simulation effect profiles ---
# `demo`: amplified for pitch charts (NOT efficacy evidence).
# `neutral`: modest ATI-sized effects closer to literature.
# `adversarial`: tiny / noisy effects — bandit should not look magical.
SIM_PROFILES: dict[str, dict[str, float | bool]] = {
    "demo": {
        "match_boost": 3.0,
        "near_match": 0.90,
        "mismatch_penalty": 0.28,
        "bandit_warm_start": True,
        "description": "Pitch-scaled effects; circular-friendly. Not for claims.",
    },
    "neutral": {
        "match_boost": 1.45,
        "near_match": 0.95,
        "mismatch_penalty": 0.70,
        "bandit_warm_start": False,
        "description": "Modest method effects; flat bandit priors.",
    },
    "adversarial": {
        "match_boost": 1.10,
        "near_match": 0.98,
        "mismatch_penalty": 0.90,
        "bandit_warm_start": False,
        "description": "Weak effects; stress-test that bandit does not overclaim.",
    },
}

# Back-compat aliases used by older demo code (demo profile).
MATCH_BOOST = float(SIM_PROFILES["demo"]["match_boost"])
NEAR_MATCH = float(SIM_PROFILES["demo"]["near_match"])
MISMATCH_PENALTY = float(SIM_PROFILES["demo"]["mismatch_penalty"])

# Contextual Thompson Sampling hyperparameters.
BANDIT_GAMMA = 0.88  # discount so older evidence fades

DATA_PATH = "data/as.csv"
OUTPUT_DIR = "outputs"
CONTENT_VERSION = 2
