"""Generate method-specific lessons and SymPy-verify every answer."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib import error, request

from pll.prompts import SKILL_LABELS, build_prompt
from pll.questions import Question, QuestionBank, SKILL_ALIASES
from pll.sympy_check import verify_answer


@dataclass
class Lesson:
    method: str
    skill: str
    misconception_id: str
    misconception_label: str
    title: str
    body: dict[str, Any]
    practice: list[dict[str, Any]]
    all_verified: bool
    source: str  # "template" | "llm"
    prompt: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _ascii_bar(numerator: int, denominator: int, width: int = 24) -> str:
    filled = max(0, min(width, int(round(width * numerator / denominator))))
    return "[" + "#" * filled + "." * (width - filled) + f"] {numerator}/{denominator}"


def _template_lesson(
    method: str,
    skill: str,
    misconception_id: str,
    misconception_label: str,
    example: Question,
    practice: list[Question],
) -> dict[str, Any]:
    skill_label = SKILL_LABELS.get(skill, skill)
    steps = [
        f"Read the problem: {example.stem}",
        example.explanation or "Use the fraction rules for this skill.",
        f"So the answer is {example.answer}.",
        f"Watch out: {misconception_label}",
    ]

    practice_payload = [
        {
            "id": q.id,
            "prompt": q.stem,
            "answer": q.answer,
            "answer_sympy": q.answer_sympy,
            "choices": list(q.choices) if q.choices else None,
        }
        for q in practice
    ]

    if method == "worked_example":
        body = {
            "hook": f"We'll learn {skill_label} by studying one clear example first.",
            "worked_example": {
                "problem": example.stem,
                "steps": steps,
                "answer": example.answer,
            },
            "misconception_check": f"Avoid this trap: {misconception_label}",
            "exit_ticket": {
                "prompt": practice_payload[-1]["prompt"] if practice_payload else example.stem,
                "answer": practice_payload[-1]["answer"] if practice_payload else example.answer,
            },
        }
    elif method == "problem_first":
        body = {
            "challenge": {"problem": example.stem, "answer": example.answer},
            "reveal": {"steps": steps, "answer": example.answer},
            "misconception_check": f"If you thought differently, check: {misconception_label}",
            "exit_ticket": {
                "prompt": practice_payload[-1]["prompt"] if practice_payload else example.stem,
                "answer": practice_payload[-1]["answer"] if practice_payload else example.answer,
            },
        }
    elif method == "visual":
        # Best-effort visual for unit-style fractions in the example answer.
        visual = {
            "type": "fraction_bars",
            "ascii": _ascii_bar(1, 2) + "\n" + _ascii_bar(1, 4),
            "caption": "Longer shaded bar = larger fraction when the whole is the same.",
        }
        body = {
            "visual": visual,
            "explanation": (
                f"Use the picture to understand {skill_label}. "
                f"Example: {example.stem} → {example.answer}. "
                f"{example.explanation}"
            ),
            "misconception_check": f"The picture shows why this is wrong: {misconception_label}",
            "exit_ticket": {
                "prompt": practice_payload[-1]["prompt"] if practice_payload else example.stem,
                "answer": practice_payload[-1]["answer"] if practice_payload else example.answer,
            },
        }
    elif method == "story_analogy":
        body = {
            "story": (
                f"Sam is sharing food with friends and needs {skill_label}. "
                f"The puzzle is: {example.stem}"
            ),
            "maths_in_story": {"steps": steps, "answer": example.answer},
            "misconception_check": f"In the story, don't fall for: {misconception_label}",
            "exit_ticket": {
                "prompt": practice_payload[-1]["prompt"] if practice_payload else example.stem,
                "answer": practice_payload[-1]["answer"] if practice_payload else example.answer,
            },
        }
    else:
        raise ValueError(method)

    return {
        "title": f"{skill_label.title()} — {method.replace('_', ' ')}",
        "method": method,
        **body,
        "practice": practice_payload,
    }


def _verify_lesson_dict(lesson: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Attach verification flags; return (lesson, all_ok)."""
    all_ok = True

    def check_field(obj: dict[str, Any], key: str = "answer") -> None:
        nonlocal all_ok
        if key not in obj:
            return
        # Important: answer_sympy may be present but None for text-only items.
        expected = obj[key] if obj.get("answer_sympy") is None else obj["answer_sympy"]
        got = obj["model_answer"] if obj.get("model_answer") is not None else obj.get(key)
        result = verify_answer(expected, got)
        obj["verified"] = result.ok
        obj["verify_detail"] = result.detail
        all_ok = all_ok and result.ok

    for section in ("worked_example", "challenge", "reveal", "maths_in_story", "exit_ticket"):
        if isinstance(lesson.get(section), dict):
            check_field(lesson[section])

    for item in lesson.get("practice", []):
        check_field(item)

    lesson["all_verified"] = all_ok
    return lesson, all_ok


def _call_openai_compatible(prompt: str, model: str, base_url: str, api_key: str) -> dict[str, Any]:
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "temperature": 0.3,
        "messages": [
            {
                "role": "system",
                "content": "You write Year 5 maths lessons. Reply with valid JSON only.",
            },
            {"role": "user", "content": prompt},
        ],
    }
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    content = data["choices"][0]["message"]["content"]
    # Strip optional markdown fences.
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[-1]
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]
    return json.loads(content)


def generate_lesson(
    method: str,
    skill: str,
    misconception_id: str | None = None,
    bank: QuestionBank | None = None,
    use_llm: bool = False,
    n_practice: int = 3,
) -> Lesson:
    bank = bank or QuestionBank.load()
    skill = SKILL_ALIASES.get(skill, skill)

    if misconception_id is None:
        # Pick the most common misconception tag among this skill's items.
        counts: dict[str, int] = {}
        for q in bank.by_skill(skill):
            for m in q.misconceptions:
                counts[m] = counts.get(m, 0) + 1
        misconception_id = max(counts, key=counts.get) if counts else "add_across"

    label = bank.misconceptions.get(misconception_id, misconception_id)
    picked = bank.pick_lesson_set(skill, misconception_id, n_practice=n_practice)
    example = picked["examples"][0]
    practice = picked["practice"]
    prompt = build_prompt(method, skill, label, example, practice)

    source = "template"
    if use_llm:
        api_key = os.environ.get("PLL_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
        base_url = os.environ.get("PLL_BASE_URL", "https://api.openai.com/v1")
        model = os.environ.get("PLL_MODEL", "gpt-4o-mini")
        if not api_key:
            raise RuntimeError(
                "use_llm=True but no PLL_API_KEY/OPENAI_API_KEY set. "
                "Use template mode (default) or export a key."
            )
        try:
            body = _call_openai_compatible(prompt, model, base_url, api_key)
            # Force practice answers from the bank (safety layer).
            bank_practice = [
                {
                    "id": q.id,
                    "prompt": q.stem,
                    "answer": q.answer,
                    "answer_sympy": q.answer_sympy,
                    "model_answer": next(
                        (
                            p.get("answer")
                            for p in body.get("practice", [])
                            if p.get("id") == q.id
                        ),
                        q.answer,
                    ),
                    "choices": list(q.choices) if q.choices else None,
                }
                for q in practice
            ]
            body["practice"] = bank_practice
            source = "llm"
        except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError, KeyError) as exc:
            body = _template_lesson(method, skill, misconception_id, label, example, practice)
            body["llm_fallback_reason"] = str(exc)
            source = "template_fallback"
    else:
        body = _template_lesson(method, skill, misconception_id, label, example, practice)

    body, all_ok = _verify_lesson_dict(body)
    return Lesson(
        method=method,
        skill=skill,
        misconception_id=misconception_id,
        misconception_label=label,
        title=body.get("title", f"{skill} / {method}"),
        body=body,
        practice=body.get("practice", []),
        all_verified=all_ok,
        source=source,
        prompt=prompt,
    )


def save_lesson(lesson: Lesson, out_dir: str | Path) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{lesson.skill}__{lesson.method}.json"
    path.write_text(json.dumps(lesson.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def render_lesson_markdown(lesson: Lesson) -> str:
    b = lesson.body
    lines = [
        f"# {lesson.title}",
        f"",
        f"**Method:** {lesson.method}  ",
        f"**Skill:** {lesson.skill}  ",
        f"**Misconception targeted:** {lesson.misconception_label}  ",
        f"**Source:** {lesson.source}  ",
        f"**All answers SymPy-verified:** {'yes' if lesson.all_verified else 'NO'}  ",
        "",
    ]
    if "hook" in b:
        lines += ["## Hook", b["hook"], ""]
    if "story" in b:
        lines += ["## Story", b["story"], ""]
    if "visual" in b:
        v = b["visual"]
        lines += ["## Visual", "```", v.get("ascii", ""), "```", v.get("caption", ""), ""]
    if "worked_example" in b:
        we = b["worked_example"]
        lines += ["## Worked example", we.get("problem", ""), ""]
        for i, s in enumerate(we.get("steps", []), 1):
            lines.append(f"{i}. {s}")
        lines += [f"**Answer:** {we.get('answer')}", ""]
    if "challenge" in b:
        lines += ["## Try this first", b["challenge"].get("problem", ""), ""]
    if "reveal" in b:
        lines += ["## Solution reveal"]
        for i, s in enumerate(b["reveal"].get("steps", []), 1):
            lines.append(f"{i}. {s}")
        lines += [f"**Answer:** {b['reveal'].get('answer')}", ""]
    if "maths_in_story" in b:
        lines += ["## Maths in the story"]
        for i, s in enumerate(b["maths_in_story"].get("steps", []), 1):
            lines.append(f"{i}. {s}")
        lines += [f"**Answer:** {b['maths_in_story'].get('answer')}", ""]
    if "explanation" in b:
        lines += ["## Explanation", b["explanation"], ""]
    if "misconception_check" in b:
        lines += ["## Misconception check", b["misconception_check"], ""]
    lines += ["## Practice"]
    for p in lesson.practice:
        ver = "✓" if p.get("verified") else "✗"
        lines.append(f"- ({p['id']}) {p['prompt']} → `{p['answer']}` [{ver}]")
    if "exit_ticket" in b:
        et = b["exit_ticket"]
        lines += ["", "## Exit ticket", et.get("prompt", ""), f"**Answer:** {et.get('answer')}"]
    return "\n".join(lines)
