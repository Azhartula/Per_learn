"""Turn any bank item into a multiple-choice question for the UI."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, replace

import numpy as np

from pll.questions import Question
from pll.sympy_check import verify_answer


@dataclass(frozen=True)
class McqQuestion:
    id: str
    skill: str
    difficulty: int
    misconceptions: tuple[str, ...]
    stem: str
    choices: tuple[str, ...]
    answer: str
    explanation: str
    source_type: str

    @property
    def answer_sympy(self) -> str:
        return self.answer


def _seed_for(qid: str) -> int:
    return int(hashlib.md5(qid.encode()).hexdigest()[:8], 16)


def _frac_parts(text: str) -> tuple[int, int] | None:
    m = re.fullmatch(r"\s*(-?\d+)\s*/\s*(-?\d+)\s*", str(text))
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def _distractors_for(answer: object, misconceptions: tuple[str, ...]) -> list[str]:
    ans = answer if not isinstance(answer, list) else ", ".join(str(a) for a in answer)
    ans_s = str(ans).strip()
    out: list[str] = []

    low = ans_s.lower()
    if low in {"yes", "no"}:
        return ["yes" if low == "no" else "no", "not sure", "sometimes"]
    if low in {"true", "false"}:
        return ["true" if low == "false" else "false", "equal", "cannot tell"]

    parts = _frac_parts(ans_s)
    if parts:
        n, d = parts
        candidates = [
            f"{n + d}/{d}" if d else ans_s,  # add across-ish
            f"{n}/{d + n}" if d else ans_s,
            f"{d}/{n}" if n else ans_s,  # invert
            f"{n}/{d + 1}" if d else ans_s,
            f"{n + 1}/{d}" if d else ans_s,
            f"{2 * n}/{2 * d}" if d and abs(n) < 20 else f"{n}/{max(d - 1, 1)}",
            f"{n}/{2 * d}" if d else ans_s,
            f"{n + d}/{n * d}" if n and d else ans_s,
        ]
        if "add_across" in misconceptions:
            candidates.insert(0, f"{n + 1}/{d + 1}" if d else ans_s)
        out.extend(candidates)
    elif re.fullmatch(r"-?\d+", ans_s):
        v = int(ans_s)
        out.extend([str(v + 1), str(v - 1), str(v * 2), str(max(v // 2, 0)), str(v + 2)])
    elif re.fullmatch(r"-?\d+\s+\d+/\d+", ans_s):
        # mixed number like 1 1/4
        out.extend(["5/4", "2 1/4", "1 1/2", "1/4", ans_s.replace(" ", "")])
    elif "," in ans_s:
        bits = [b.strip() for b in ans_s.split(",")]
        if len(bits) >= 2:
            shuffled = list(reversed(bits))
            out.append(", ".join(shuffled))
            if len(bits) >= 3:
                out.append(", ".join([bits[1], bits[0], *bits[2:]]))
            out.append(", ".join(sorted(bits)))
            out.append(bits[0])
    else:
        out.extend(["1/2", "1/3", "2/3", "1", "0"])

    # Dedup while preserving order; drop anything equal to the correct answer.
    clean: list[str] = []
    for c in out:
        c = str(c).strip()
        if not c or c == ans_s:
            continue
        if any(verify_answer(ans_s, c).ok for _ in [0]):
            continue
        if c not in clean:
            clean.append(c)
    return clean


def as_mcq(question: Question, n_choices: int = 4) -> McqQuestion:
    """Return an MCQ view of a bank question (uses existing choices or builds distractors)."""
    if isinstance(question.answer, list):
        correct = ", ".join(str(a) for a in question.answer)
    else:
        correct = str(question.answer)

    if question.choices:
        choices = list(question.choices)
        # Ensure correct answer is among choices.
        if not any(verify_answer(correct, c).ok for c in choices):
            choices = [correct, *choices]
    else:
        distractors = _distractors_for(question.answer, question.misconceptions)
        choices = [correct, *distractors]

    # Unique, capped.
    uniq: list[str] = []
    for c in choices:
        c = str(c).strip()
        if not c:
            continue
        if any(verify_answer(c, u).ok for u in uniq):
            continue
        uniq.append(c)
    # Keep correct + enough distractors.
    correct_item = next((c for c in uniq if verify_answer(correct, c).ok), correct)
    others = [c for c in uniq if not verify_answer(correct, c).ok]
    rng = np.random.default_rng(_seed_for(question.id))
    rng.shuffle(others)
    picked = [correct_item, *others[: max(n_choices - 1, 1)]]
    rng.shuffle(picked)
    # Pad with generic fraction distractors if the bank item had fewer than n choices.
    filler = ["1/2", "1/3", "2/3", "1/4", "3/4", "2/5", "1", "0", "equal", "cannot tell"]
    for pad in filler:
        if len(picked) >= n_choices:
            break
        if any(verify_answer(pad, c).ok for c in picked):
            continue
        if verify_answer(correct, pad).ok:
            continue
        picked.append(pad)
    rng.shuffle(picked)

    return McqQuestion(
        id=question.id,
        skill=question.skill,
        difficulty=question.difficulty,
        misconceptions=question.misconceptions,
        stem=question.stem,
        choices=tuple(picked[:n_choices]),
        answer=correct_item,
        explanation=question.explanation,
        source_type=question.type,
    )


def to_question(mcq: McqQuestion) -> Question:
    """Adapter so existing verify/bank helpers can treat MCQs like Questions."""
    return Question(
        id=mcq.id,
        skill=mcq.skill,
        difficulty=mcq.difficulty,
        misconceptions=mcq.misconceptions,
        stem=mcq.stem,
        type="mcq",
        answer=mcq.answer,
        answer_sympy=mcq.answer,
        explanation=mcq.explanation,
        choices=mcq.choices,
    )
