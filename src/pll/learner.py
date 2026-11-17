"""Persistent learner profile — bandit + mastery that adapt to your answers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from pll.bandit import DiscountedContextualTS, make_context, mastery_bin
from pll.config import METHODS
from pll.parent_summary import METHOD_PLAIN


LEARNERS_DIR = Path(__file__).resolve().parents[2] / "outputs" / "learners"
BIN_NAMES = ("novice", "intermediate", "advanced")


@dataclass
class SessionRecord:
    session: int
    timestamp: str
    mastery_before: float
    mastery_after: float
    method: str
    delayed_score: float
    skill: str
    diagnostic_score: str
    matched_preference: bool | None = None
    notes: str = ""


@dataclass
class LearnerProfile:
    name: str
    mastery: float = 0.28  # new learners start near novice → scaffolding methods
    focus_skill: str | None = None
    sessions_completed: int = 0
    history: list[SessionRecord] = field(default_factory=list)
    # Bandit posterior per (bin, method)
    bandit_alpha: list[list[float]] = field(default_factory=list)
    bandit_beta: list[list[float]] = field(default_factory=list)
    bandit_counts: list[list[int]] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = _now()
        if not self.bandit_alpha:
            b = DiscountedContextualTS(rng=np.random.default_rng(0))
            self.bandit_alpha = b.alpha.tolist()
            self.bandit_beta = b.beta.tolist()
            self.bandit_counts = b.counts.tolist()

    def to_bandit(self, seed: int = 0) -> DiscountedContextualTS:
        b = DiscountedContextualTS(rng=np.random.default_rng(seed))
        b.alpha = np.array(self.bandit_alpha, dtype=float)
        b.beta = np.array(self.bandit_beta, dtype=float)
        b.counts = np.array(self.bandit_counts, dtype=int)
        return b

    def store_bandit(self, bandit: DiscountedContextualTS) -> None:
        self.bandit_alpha = bandit.alpha.tolist()
        self.bandit_beta = bandit.beta.tolist()
        self.bandit_counts = bandit.counts.tolist()

    def preferred_method(self) -> str:
        bandit = self.to_bandit()
        means = bandit.mean_rewards(make_context(self.mastery))
        return METHODS[int(np.argmax(means))]

    def method_scores(self) -> dict[str, float]:
        bandit = self.to_bandit()
        means = bandit.mean_rewards(make_context(self.mastery))
        return {METHODS[i]: round(float(means[i]), 3) for i in range(len(METHODS))}

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "mastery": self.mastery,
            "focus_skill": self.focus_skill,
            "sessions_completed": self.sessions_completed,
            "history": [asdict(h) for h in self.history],
            "bandit_alpha": self.bandit_alpha,
            "bandit_beta": self.bandit_beta,
            "bandit_counts": self.bandit_counts,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expertise_bin": BIN_NAMES[mastery_bin(self.mastery)],
            "preferred_method": self.preferred_method(),
            "method_scores": self.method_scores(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LearnerProfile:
        hist = [SessionRecord(**h) for h in data.get("history", [])]
        return cls(
            name=data["name"],
            mastery=float(data.get("mastery", 0.35)),
            focus_skill=data.get("focus_skill"),
            sessions_completed=int(data.get("sessions_completed", 0)),
            history=hist,
            bandit_alpha=data.get("bandit_alpha") or [],
            bandit_beta=data.get("bandit_beta") or [],
            bandit_counts=data.get("bandit_counts") or [],
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_name(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name.strip()) or "learner"


def profile_path(name: str, root: Path | None = None) -> Path:
    root = root or LEARNERS_DIR
    return root / f"{_safe_name(name)}.json"


def load_or_create(name: str, root: Path | None = None) -> LearnerProfile:
    path = profile_path(name, root)
    if path.exists():
        return LearnerProfile.from_dict(json.loads(path.read_text(encoding="utf-8")))
    return LearnerProfile(name=name.strip() or "Learner")


def save_profile(profile: LearnerProfile, root: Path | None = None) -> Path:
    root = root or LEARNERS_DIR
    root.mkdir(parents=True, exist_ok=True)
    profile.updated_at = _now()
    path = profile_path(profile.name, root)
    path.write_text(json.dumps(profile.to_dict(), indent=2), encoding="utf-8")
    return path


def adaptation_summary(profile: LearnerProfile) -> str:
    scores = profile.method_scores()
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top = ranked[0][0]
    lines = [
        f"Learner: {profile.name}",
        f"Sessions so far: {profile.sessions_completed}",
        f"Current mastery: {profile.mastery:.0%} ({BIN_NAMES[mastery_bin(profile.mastery)]})",
        f"How you seem to learn best right now: {METHOD_PLAIN[top]}",
        "Method scores at your level:",
    ]
    for method, score in ranked:
        mark = "← preferred" if method == top else ""
        lines.append(f"  {METHOD_PLAIN[method]}: {score:.2f} {mark}")
    if len(profile.history) >= 2:
        prev = profile.history[-2].method
        cur = profile.history[-1].method
        if prev != cur:
            lines.append(
                f"Adaptation: switched from {METHOD_PLAIN[prev]} → {METHOD_PLAIN[cur]} "
                f"after your last delayed check ({profile.history[-1].delayed_score:.0%})."
            )
        else:
            lines.append(
                f"Adaptation: kept {METHOD_PLAIN[cur]} because delayed checks support it."
            )
    elif profile.sessions_completed == 0:
        lines.append("Adaptation: no sessions yet — first answers will teach the bandit about you.")
    return "\n".join(lines)
