"""Shared constants for the Phase 1 demo."""

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

# Demo-scaled method effect (ASSISTments RCTs often show smaller effects;
# we amplify so the pitch chart separates cleanly in ~100 simulated kids).
MATCH_BOOST = 3.0
NEAR_MATCH = 0.90
MISMATCH_PENALTY = 0.28

# Contextual Thompson Sampling hyperparameters.
BANDIT_GAMMA = 0.88  # discount so older evidence fades

DATA_PATH = "data/as.csv"
OUTPUT_DIR = "outputs"
