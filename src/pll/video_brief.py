"""Specialised short video briefs for AI-video school generators.

Produces structured briefs a partner platform can feed into their renderer.
Cost figures are duration proxies — not invoices from their GPU pipeline.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from pll.parent_summary import METHOD_PLAIN
from pll.prompts import SKILL_LABELS

# Meeting defaults: long generic topic video vs short gap-targeted video
GENERIC_MINUTES = 11.0
SPECIALISED_MINUTES = {
    "worked_example": 3.0,
    "problem_first": 3.5,
    "visual": 2.5,
    "story_analogy": 3.0,
}


@dataclass
class VideoScene:
    order: int
    title: str
    seconds: int
    narration_cue: str
    visual_cue: str


@dataclass
class VideoBrief:
    skill: str
    skill_label: str
    method: str
    method_label: str
    misconception_id: str | None
    misconception_label: str
    title: str
    max_minutes: float
    estimated_minutes_generic: float
    estimated_minutes_specialised: float
    cost_proxy: float  # specialised / generic (lower = cheaper minutes)
    minutes_saved: float
    do_not_reteach: list[str]
    scenes: list[VideoScene]
    generation_controls: dict[str, Any] = field(default_factory=dict)
    note: str = (
        "Cost proxy uses estimated render minutes, not your GPU invoice. "
        "Feed this brief into your video generator."
    )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


def _scenes_for(
    method: str,
    skill_label: str,
    misconception_label: str,
) -> list[VideoScene]:
    if method == "worked_example":
        return [
            VideoScene(1, "Hook the gap", 25, f"Today we fix one mix-up in {skill_label}.", "Title card + weak-spot badge"),
            VideoScene(2, "Worked example", 70, "Watch every step on one clear problem.", "Step-by-step board; highlight each step"),
            VideoScene(3, "Misconception contrast", 40, f"Avoid this trap: {misconception_label}", "Split screen: wrong vs right"),
            VideoScene(4, "You try (guided)", 35, "Pause and try a near twin; then reveal.", "Pause card + reveal answer"),
            VideoScene(5, "Exit check", 20, "One no-help question before we stop.", "Single MCQ overlay"),
        ]
    if method == "problem_first":
        return [
            VideoScene(1, "Challenge first", 30, "Try this before I explain.", "Problem card; timer optional"),
            VideoScene(2, "Reveal reasoning", 70, "Here is the thinking you needed.", "Annotated solution"),
            VideoScene(3, "Misconception contrast", 35, f"Common slip: {misconception_label}", "Error callout"),
            VideoScene(4, "Transfer try", 40, "New numbers, same idea — pause and solve.", "Second problem"),
            VideoScene(5, "Exit check", 20, "Lock in with one unassisted item.", "MCQ overlay"),
        ]
    if method == "visual":
        return [
            VideoScene(1, "See the size", 25, f"We compare {skill_label} with a picture.", "Fraction bars / number line intro"),
            VideoScene(2, "Build the diagram", 60, "Watch the bars grow correctly.", "Animated bars matching the example"),
            VideoScene(3, "Misconception contrast", 40, f"Picture shows why this fails: {misconception_label}", "Wrong bar vs right bar"),
            VideoScene(4, "Read the diagram", 30, "Answer from the picture alone.", "Silent diagram + prompt"),
            VideoScene(5, "Exit check", 20, "One check without the old wrong habit.", "MCQ overlay"),
        ]
    # story_analogy
    return [
        VideoScene(1, "Real-world hook", 30, f"A sharing story for {skill_label}.", "Kitchen / pizza / friends scene"),
        VideoScene(2, "Maths in the story", 65, "Map the story onto the fraction steps.", "Story → symbols side by side"),
        VideoScene(3, "Misconception contrast", 35, f"In the story, don't: {misconception_label}", "Story beat that catches the trap"),
        VideoScene(4, "New story twin", 30, "Same idea, new numbers.", "Second short story prompt"),
        VideoScene(5, "Exit check", 20, "Leave the story; answer the maths.", "MCQ overlay"),
    ]


def build_generic_brief(skill: str = "ordering_fractions") -> VideoBrief:
    """What their platform often generates without evaluation feedback."""
    label = SKILL_LABELS.get(skill, skill)
    scenes = [
        VideoScene(1, "Topic overview", 90, f"Everything about {label}.", "Wide curriculum montage"),
        VideoScene(2, "Many examples", 180, "Several worked problems at once.", "Dense board"),
        VideoScene(3, "General tips", 120, "Rules and reminders for the whole topic.", "Bullet list"),
        VideoScene(4, "Practice set", 180, "Mixed practice covering the unit.", "Multi-question screen"),
        VideoScene(5, "Wrap-up", 90, "Recap the whole topic.", "Summary card"),
    ]
    return VideoBrief(
        skill=skill,
        skill_label=label,
        method="generic_long",
        method_label="Long generic topic video",
        misconception_id=None,
        misconception_label="(none targeted)",
        title=f"{label.title()} — full topic lesson",
        max_minutes=GENERIC_MINUTES,
        estimated_minutes_generic=GENERIC_MINUTES,
        estimated_minutes_specialised=GENERIC_MINUTES,
        cost_proxy=1.0,
        minutes_saved=0.0,
        do_not_reteach=[],
        scenes=scenes,
        generation_controls={
            "scope": "full_topic",
            "target_gap": None,
            "duration_cap_minutes": GENERIC_MINUTES,
        },
        note="Baseline: render the whole topic again when a quiz fails.",
    )


def build_specialised_brief(
    *,
    skill: str,
    method: str,
    misconception_id: str | None = None,
    misconception_label: str | None = None,
    known_strengths: list[str] | None = None,
) -> VideoBrief:
    """Short, gap-targeted brief for their AI video generator."""
    label = SKILL_LABELS.get(skill, skill)
    misc_label = misconception_label or "a common mix-up on this skill"
    minutes = float(SPECIALISED_MINUTES.get(method, 3.0))
    cost_proxy = minutes / GENERIC_MINUTES
    strengths = known_strengths or []
    do_not = [
        "Do not re-teach the entire fractions unit.",
        "Do not open with a long curriculum overview.",
        *([f"Skip reteaching: {s}" for s in strengths[:3]]),
    ]
    scenes = _scenes_for(method, label, misc_label)
    total_sec = sum(s.seconds for s in scenes)
    # Keep specialised estimate aligned with scene sum, capped by method default
    specialised = min(minutes, round(total_sec / 60.0, 1))
    specialised = max(specialised, 2.0)
    cost_proxy = specialised / GENERIC_MINUTES

    return VideoBrief(
        skill=skill,
        skill_label=label,
        method=method,
        method_label=METHOD_PLAIN.get(method, method.replace("_", " ")),
        misconception_id=misconception_id,
        misconception_label=misc_label,
        title=f"{label.title()} — {METHOD_PLAIN.get(method, method)} (specialised)",
        max_minutes=specialised,
        estimated_minutes_generic=GENERIC_MINUTES,
        estimated_minutes_specialised=specialised,
        cost_proxy=round(cost_proxy, 3),
        minutes_saved=round(GENERIC_MINUTES - specialised, 1),
        do_not_reteach=do_not,
        scenes=scenes,
        generation_controls={
            "scope": "single_gap",
            "teaching_method": method,
            "misconception_id": misconception_id,
            "duration_cap_minutes": specialised,
            "narration_density": "medium" if method != "visual" else "low",
            "visual_schema": "fraction_bars" if method == "visual" else "board",
            "include_misconception_contrast": True,
            "include_exit_check": True,
        },
    )


def render_brief_markdown(brief: VideoBrief) -> str:
    lines = [
        f"# {brief.title}",
        "",
        f"**Skill:** {brief.skill_label}  ",
        f"**Teaching style:** {brief.method_label}  ",
        f"**Target mix-up:** {brief.misconception_label}  ",
        f"**Duration cap:** {brief.max_minutes:.1f} min  ",
        f"**vs generic topic video:** {brief.estimated_minutes_generic:.1f} min  ",
        f"**Minutes saved (proxy):** {brief.minutes_saved:.1f}  ",
        f"**Cost proxy (specialised/generic):** {brief.cost_proxy:.2f}  ",
        "",
        f"_{brief.note}_",
        "",
        "## Do not reteach",
    ]
    for x in brief.do_not_reteach:
        lines.append(f"- {x}")
    lines += ["", "## Scenes"]
    for s in brief.scenes:
        lines += [
            f"### {s.order}. {s.title} (~{s.seconds}s)",
            f"- Narration: {s.narration_cue}",
            f"- Visual: {s.visual_cue}",
            "",
        ]
    lines += ["## Generation controls", "```json"]
    import json

    lines.append(json.dumps(brief.generation_controls, indent=2))
    lines.append("```")
    return "\n".join(lines)
