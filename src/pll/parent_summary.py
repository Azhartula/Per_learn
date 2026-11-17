"""Plain-language parent dashboard text."""

from __future__ import annotations

from pll.bandit import mastery_bin
from pll.config import METHODS
from pll.diagnostic import DiagnosticResult
from pll.prompts import SKILL_LABELS


BIN_LABELS = {
    0: "still building foundations",
    1: "developing",
    2: "working at a stronger level",
}

METHOD_PLAIN = {
    "worked_example": "worked examples first, then practice",
    "problem_first": "trying a problem first, then seeing the explanation",
    "visual": "visual explanations (fraction bars / number lines)",
    "story_analogy": "real-world stories and analogies",
}


def render_parent_summary(
    student_name: str,
    diagnostic: DiagnosticResult,
    method: str,
    misconception_label: str,
    delayed_score: float | None,
    review_due: bool,
    effort_note: str,
    bank_misconceptions: dict[str, str],
) -> str:
    skill = SKILL_LABELS.get(diagnostic.weakest_skill, diagnostic.weakest_skill)
    level = BIN_LABELS[mastery_bin(diagnostic.ability)]
    method_plain = METHOD_PLAIN.get(method, method.replace("_", " "))

    active = []
    if misconception_label:
        active.append(misconception_label)
    for m in diagnostic.active_misconceptions:
        label = bank_misconceptions.get(m, m)
        if label not in active:
            active.append(label)
        if len(active) >= 2:
            break

    why = "; ".join(active) if active else "no clear misconception tagged yet"

    delayed_line = (
        f"{delayed_score:.0%} correct on a mixed check with no help"
        if delayed_score is not None
        else "delayed check not taken yet"
    )

    review_line = (
        "Yes — this skill should come back soon so it is not forgotten."
        if review_due
        else "Not urgently — keep an eye on the next session."
    )

    lines = [
        f"# Parent summary — {student_name}",
        "",
        f"**How they learn best right now:** {method_plain}",
        f"(Based on their current level: {level}.)",
        "",
        f"**Where they are lagging:** {skill}",
        f"**Why:** {why}",
        "",
        f"**Diagnostic:** {diagnostic.n_correct}/{diagnostic.n_items} correct "
        f"(overall estimate {diagnostic.ability:.0%})",
        f"**After the lesson:** {delayed_line}",
        "",
        f"**Due for review?** {review_line}",
        f"**Effort signal:** {effort_note}",
        "",
        "_This is not a fixed learning-style label. We re-measure what works as they grow._",
    ]
    return "\n".join(lines)


def method_preference_line(method_idx: int, means: list[float]) -> str:
    ranking = sorted(range(len(METHODS)), key=lambda i: means[i], reverse=True)
    top = METHODS[ranking[0]]
    return (
        f"Current method preference: {METHOD_PLAIN[top]} "
        f"(scores: " + ", ".join(f"{METHODS[i]}={means[i]:.2f}" for i in ranking) + ")"
    )
