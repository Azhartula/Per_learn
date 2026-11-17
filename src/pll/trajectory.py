"""Multi-session child trajectories — show the bandit adapting over time."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

from pll.bandit import DiscountedContextualTS, make_context, mastery_bin
from pll.config import METHODS
from pll.parent_summary import METHOD_PLAIN
from pll.prompts import SKILL_LABELS
from pll.simulator import BIN_BEST, _effective_learn_rate


# Named child profiles = different starting points / within-bin preferences.
CHILD_PROFILES: dict[str, dict[str, Any]] = {
    "maya": {
        "display_name": "Maya",
        "age_year": 5,
        "skill": "ordering_fractions",
        "start_mastery": 0.22,
        "learn_scale": 1.0,
        # Personal preference noise inside each expertise bin.
        "preference_noise": {0: 0, 1: 2, 2: 1},  # worked → visual → problem_first
        "blurb": "Starts unsure on ordering fractions. Scaffolding helps early; later she needs less.",
    },
    "sam": {
        "display_name": "Sam",
        "age_year": 5,
        "skill": "multiply_fractions",
        "start_mastery": 0.28,
        "learn_scale": 0.95,
        "preference_noise": {0: 2, 1: 2, 2: 1},  # visual-leaning early
        "blurb": "Responds strongly to visual fraction bars at first, then outgrows them.",
    },
    "jordan": {
        "display_name": "Jordan",
        "age_year": 5,
        "skill": "add_subtract_fractions",
        "start_mastery": 0.18,
        "learn_scale": 1.05,
        "preference_noise": {0: 3, 1: 3, 2: 1},  # story early, then problem-first
        "blurb": "Stories click early. As mastery rises, problem-first pulls ahead.",
    },
}


BIN_NAMES = ("novice", "intermediate", "advanced")


@dataclass
class SessionBeat:
    session: int
    week_label: str
    mastery_before: float
    mastery_after: float
    expertise_bin: str
    method: str
    method_plain: str
    oracle_method: str
    oracle_plain: str
    matched_oracle: bool
    delayed_score: float
    bandit_means: dict[str, float]
    narrative: str


@dataclass
class ChildTrajectory:
    profile_id: str
    display_name: str
    skill: str
    skill_label: str
    blurb: str
    sessions: list[SessionBeat] = field(default_factory=list)
    method_switches: list[dict[str, Any]] = field(default_factory=list)
    final_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "display_name": self.display_name,
            "skill": self.skill,
            "skill_label": self.skill_label,
            "blurb": self.blurb,
            "sessions": [asdict(s) for s in self.sessions],
            "method_switches": self.method_switches,
            "final_summary": self.final_summary,
            "methods": list(METHODS),
            "method_plain": dict(METHOD_PLAIN),
        }


def _oracle(mastery: float, preference_noise: dict[int, int]) -> int:
    b = mastery_bin(mastery)
    return int(preference_noise.get(b, BIN_BEST[b]))


def _delayed_score(
    mastery: float,
    method: int,
    oracle: int,
    rng: np.random.Generator,
) -> float:
    """Unassisted check quality — higher when method matches current best."""
    base = 0.35 + 0.55 * mastery
    if method == oracle:
        base += 0.18
    elif method in ({0, 2, 3} if oracle in (0, 2, 3) else {1}):
        base += 0.04
    else:
        base -= 0.16
    noise = rng.normal(0, 0.05)
    return float(np.clip(base + noise, 0.05, 0.98))


def _narrative(
    name: str,
    beat: SessionBeat,
    switched: bool,
) -> str:
    if beat.session == 1:
        return (
            f"{name} begins as a {beat.expertise_bin}. "
            f"PerLearn starts with {beat.method_plain}."
        )
    if switched:
        return (
            f"Mastery moved — the bandit switches to {beat.method_plain} "
            f"(now a better fit for a {beat.expertise_bin})."
        )
    if beat.matched_oracle:
        return (
            f"Sticking with {beat.method_plain}: delayed check "
            f"{beat.delayed_score:.0%} suggests it is working."
        )
    return (
        f"Still exploring ({beat.method_plain}). "
        f"Delayed check {beat.delayed_score:.0%} feeds the next decision."
    )


def simulate_child(
    profile_id: str = "maya",
    n_sessions: int = 10,
    seed: int = 42,
) -> ChildTrajectory:
    if profile_id not in CHILD_PROFILES:
        raise KeyError(f"Unknown profile {profile_id}. Choose from {list(CHILD_PROFILES)}")

    profile = CHILD_PROFILES[profile_id]
    rng = np.random.default_rng(seed)
    bandit = DiscountedContextualTS(rng=np.random.default_rng(seed + 1))

    mastery = float(profile["start_mastery"])
    pref = dict(profile["preference_noise"])
    learn_scale = float(profile["learn_scale"])
    name = str(profile["display_name"])
    skill = str(profile["skill"])

    traj = ChildTrajectory(
        profile_id=profile_id,
        display_name=name,
        skill=skill,
        skill_label=SKILL_LABELS.get(skill, skill),
        blurb=str(profile["blurb"]),
    )

    prev_method: str | None = None

    for s in range(1, n_sessions + 1):
        before = mastery
        context = make_context(mastery)
        oracle = _oracle(mastery, pref)

        # Readable pitch behaviour: explore a little, but exploit when the
        # posterior clearly prefers one method for this mastery bin.
        means = bandit.mean_rewards(context)
        ranked = np.argsort(means)[::-1]
        clear_winner = float(means[ranked[0]] - means[ranked[1]]) >= 0.07
        if s <= 2 or clear_winner:
            method_idx = int(ranked[0])
        else:
            method_idx = bandit.select(context)

        method = METHODS[method_idx]
        means = bandit.mean_rewards(context)
        delayed = _delayed_score(mastery, method_idx, oracle, rng)

        # Learning step depends on method match (expertise reversal).
        p_t = _effective_learn_rate(0.14 * learn_scale, method_idx, oracle)
        # Mastery climbs with effective learn rate and delayed success.
        mastery = float(
            np.clip(mastery + p_t * (0.45 + 0.55 * delayed) + rng.normal(0, 0.01), 0.05, 0.96)
        )

        bandit.update(method_idx, context, delayed)

        switched = prev_method is not None and method != prev_method
        if switched:
            traj.method_switches.append(
                {
                    "session": s,
                    "from": prev_method,
                    "to": method,
                    "mastery": round(before, 3),
                    "bin": BIN_NAMES[mastery_bin(before)],
                }
            )

        beat = SessionBeat(
            session=s,
            week_label=f"Week {s}",
            mastery_before=round(before, 3),
            mastery_after=round(mastery, 3),
            expertise_bin=BIN_NAMES[mastery_bin(before)],
            method=method,
            method_plain=METHOD_PLAIN[method],
            oracle_method=METHODS[oracle],
            oracle_plain=METHOD_PLAIN[METHODS[oracle]],
            matched_oracle=(method_idx == oracle),
            delayed_score=round(delayed, 3),
            bandit_means={METHODS[i]: round(float(means[i]), 3) for i in range(len(METHODS))},
            narrative="",
        )
        beat.narrative = _narrative(name, beat, switched)
        traj.sessions.append(beat)
        prev_method = method

    first = traj.sessions[0].method_plain
    last = traj.sessions[-1].method_plain
    n_switch = len(traj.method_switches)
    traj.final_summary = (
        f"Over {n_sessions} weeks, {name} moved from "
        f"{traj.sessions[0].expertise_bin} ({traj.sessions[0].mastery_before:.0%}) to "
        f"{traj.sessions[-1].expertise_bin} ({traj.sessions[-1].mastery_after:.0%}). "
        f"Teaching started with {first}"
        + (f" and adapted to {last}" if first != last else f" and stayed with {last}")
        + f" after {n_switch} method switch{'es' if n_switch != 1 else ''} — "
        f"because the best method changed as mastery grew."
    )
    return traj


def simulate_all_profiles(n_sessions: int = 10, seed: int = 42) -> dict[str, Any]:
    kids = {
        pid: simulate_child(pid, n_sessions=n_sessions, seed=seed + i).to_dict()
        for i, pid in enumerate(CHILD_PROFILES)
    }
    return {
        "title": "How PerLearn adapts to a real child over time",
        "subtitle": (
            "Each child starts differently. The bandit learns from delayed checks — "
            "not practice scores — and changes method as expertise reverses."
        ),
        "children": kids,
        "default_child": "maya",
    }
