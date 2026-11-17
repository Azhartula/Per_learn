"""Phase 3 live loop: diagnose → pick method → lesson → delayed check → parent summary."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np

from pll.bandit import DiscountedContextualTS, make_context, mastery_bin
from pll.config import CONTENT_VERSION, DELAYED_CHECK_ITEMS, METHODS
from pll.diagnostic import DiagnosticResult, make_simulated_student, run_diagnostic
from pll.events import append_event, log_item_response, new_session_id
from pll.lessons import Lesson, generate_lesson, render_lesson_markdown, save_lesson
from pll.parent_summary import METHOD_PLAIN, render_parent_summary
from pll.prompts import SKILL_LABELS
from pll.questions import Question, QuestionBank
from pll.sympy_check import verify_answer


@dataclass
class DelayedCheckResult:
    n_correct: int
    n_items: int
    score: float
    items: list[dict[str, Any]] = field(default_factory=list)

    @property
    def review_due(self) -> bool:
        return self.score < 0.75


@dataclass
class SessionResult:
    student_name: str
    diagnostic: DiagnosticResult
    method: str
    method_index: int
    lesson: Lesson
    delayed: DelayedCheckResult
    parent_summary: str
    effort_note: str
    created_at: str
    session_id: str = ""
    event_log: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "student_name": self.student_name,
            "session_id": self.session_id,
            "event_log": self.event_log,
            "created_at": self.created_at,
            "method": self.method,
            "method_index": self.method_index,
            "effort_note": self.effort_note,
            "diagnostic": {
                "ability": self.diagnostic.ability,
                "n_correct": self.diagnostic.n_correct,
                "n_items": self.diagnostic.n_items,
                "skill_scores": self.diagnostic.skill_scores,
                "active_misconceptions": self.diagnostic.active_misconceptions,
                "weakest_skill": self.diagnostic.weakest_skill,
                "trials": [asdict(t) for t in self.diagnostic.trials],
            },
            "lesson": {
                "title": self.lesson.title,
                "skill": self.lesson.skill,
                "misconception_id": self.lesson.misconception_id,
                "all_verified": self.lesson.all_verified,
                "source": self.lesson.source,
            },
            "delayed": {
                "n_correct": self.delayed.n_correct,
                "n_items": self.delayed.n_items,
                "score": self.delayed.score,
                "review_due": self.delayed.review_due,
                "items": self.delayed.items,
            },
            "parent_summary": self.parent_summary,
        }


def _format_question(q: Question) -> str:
    lines = [q.stem]
    if q.choices:
        for i, c in enumerate(q.choices):
            lines.append(f"  {chr(65 + i)}) {c}")
    return "\n".join(lines)


def interactive_answer_fn(q: Question) -> str:
    print("\n--- Question ---")
    print(_format_question(q))
    return input("Your answer: ").strip()


def run_delayed_check(
    bank: QuestionBank,
    skill: str,
    answer_fn: Callable[[Question], str],
    exclude_ids: set[str] | None = None,
    n_items: int = DELAYED_CHECK_ITEMS,
) -> DelayedCheckResult:
    exclude_ids = exclude_ids or set()
    pool = [q for q in bank.by_skill(skill) if q.id not in exclude_ids]
    # Prefer a mix of difficulties.
    pool = sorted(pool, key=lambda q: (q.difficulty, q.id))
    selected = pool[:n_items] if pool else bank.by_skill(skill)[:n_items]

    items = []
    n_correct = 0
    for q in selected:
        response = answer_fn(q)
        expected = q.answer_sympy if q.answer_sympy is not None else q.answer
        ok = verify_answer(expected, response).ok
        n_correct += int(ok)
        items.append(
            {
                "id": q.id,
                "stem": q.stem,
                "response": response,
                "correct": ok,
                "answer": q.answer,
            }
        )
    n = len(items)
    return DelayedCheckResult(
        n_correct=n_correct,
        n_items=n,
        score=n_correct / max(n, 1),
        items=items,
    )


def _effort_note(diagnostic: DiagnosticResult) -> str:
    # Demo heuristic: many wrongs on easy items → possible rushing/guessing.
    easy_wrong = sum(
        1 for t in diagnostic.trials if (not t.correct) and t.difficulty == 1
    )
    if easy_wrong >= 2:
        return "Possible rushing or guessing — missed more than one easy question."
    if diagnostic.accuracy >= 0.75:
        return "Looks like steady effort on the diagnostic."
    return "Some struggle on harder items — normal while learning; keep sessions short and focused."


def run_session(
    student_name: str = "Alex",
    mode: str = "demo",
    n_diagnostic: int = 8,
    seed: int = 42,
    use_llm: bool = False,
    use_ollama: bool = False,
    ollama_model: str | None = None,
    bank: QuestionBank | None = None,
    bandit: DiscountedContextualTS | None = None,
) -> SessionResult:
    """
    Full Phase 3 loop.

    mode:
      - demo: simulated Year-5-ish student (non-interactive)
      - interactive: prompts in the terminal
    """
    bank = bank or QuestionBank.load()
    rng = np.random.default_rng(seed)
    bandit = bandit or DiscountedContextualTS(rng=rng)
    session_id = new_session_id()
    respondent = "human" if mode == "interactive" else "simulated"

    if mode == "interactive":
        answer_fn = interactive_answer_fn
    else:
        answer_fn = make_simulated_student(true_ability=0.42, seed=seed)

    append_event(
        session_id,
        "session_start",
        learner_id=student_name,
        payload={"mode": mode, "content_version": CONTENT_VERSION, "respondent": respondent},
    )

    diagnostic = run_diagnostic(bank, answer_fn, n_items=n_diagnostic, seed=seed)
    for t in diagnostic.trials:
        log_item_response(
            session_id,
            learner_id=student_name,
            item_id=t.question_id,
            skill=t.skill,
            method=None,
            response=t.response,
            correct=t.correct,
            outcome_type="diagnostic",
            content_version=CONTENT_VERSION,
            respondent=respondent,
        )
    context = make_context(diagnostic.ability)
    # Thompson sample for learning; for very early/cold picks, prefer posterior mean
    # so novices don't randomly get problem-first in the pitch demo.
    if int(bandit.counts.sum()) < 3:
        method_idx = int(np.argmax(bandit.mean_rewards(context)))
    else:
        method_idx = bandit.select(context)
    method = METHODS[method_idx]
    policy_probs = bandit.mean_rewards(context).tolist()
    append_event(
        session_id,
        "method_selected",
        learner_id=student_name,
        payload={
            "method": method,
            "method_index": method_idx,
            "context": context.tolist(),
            "policy_probs": policy_probs,
            "content_version": CONTENT_VERSION,
        },
    )

    # Prefer a misconception seen on the weakest skill's missed items.
    weak_miss_misc: dict[str, int] = {}
    for t in diagnostic.trials:
        if t.skill == diagnostic.weakest_skill and not t.correct:
            for m in t.misconceptions:
                weak_miss_misc[m] = weak_miss_misc.get(m, 0) + 1
    if weak_miss_misc:
        misconception_id = max(weak_miss_misc, key=weak_miss_misc.get)
    elif diagnostic.active_misconceptions:
        misconception_id = diagnostic.active_misconceptions[0]
    else:
        misconception_id = None
    lesson = generate_lesson(
        method=method,
        skill=diagnostic.weakest_skill,
        misconception_id=misconception_id,
        bank=bank,
        use_llm=use_llm,
        use_ollama=use_ollama,
        ollama_model=ollama_model,
    )

    used = {t.question_id for t in diagnostic.trials}
    # Delayed check: no AI help — same answer_fn but conceptually "later / unassisted".
    delayed = run_delayed_check(
        bank,
        skill=diagnostic.weakest_skill,
        answer_fn=answer_fn,
        exclude_ids=used,
    )
    for item in delayed.items:
        log_item_response(
            session_id,
            learner_id=student_name,
            item_id=item["id"],
            skill=diagnostic.weakest_skill,
            method=method,
            response=item["response"],
            correct=item["correct"],
            outcome_type="immediate_post",
            context=context.tolist(),
            policy_probs=policy_probs,
            content_version=CONTENT_VERSION,
            model_id=lesson.model_name or lesson.source,
            respondent=respondent,
        )

    # Bandit reward = delayed unassisted score (never practice score).
    # Note: true delayed_24h outcomes should call bandit.update from the pilot Session-2 path.
    bandit.update(method_idx, context, delayed.score)
    append_event(
        session_id,
        "session_end",
        learner_id=student_name,
        payload={
            "method": method,
            "delayed_score": delayed.score,
            "outcome_type": "immediate_post",
            "lesson_ok": lesson.lesson_ok,
            "answers_ok": lesson.answers_ok,
            "all_verified": lesson.all_verified,
        },
    )

    effort = _effort_note(diagnostic)
    summary = render_parent_summary(
        student_name=student_name,
        diagnostic=diagnostic,
        method=method,
        misconception_label=lesson.misconception_label,
        delayed_score=delayed.score,
        review_due=delayed.review_due,
        effort_note=effort,
        bank_misconceptions=bank.misconceptions,
    )

    from pll.events import event_path

    return SessionResult(
        student_name=student_name,
        diagnostic=diagnostic,
        method=method,
        method_index=method_idx,
        lesson=lesson,
        delayed=delayed,
        parent_summary=summary,
        effort_note=effort,
        created_at=datetime.now(timezone.utc).isoformat(),
        session_id=session_id,
        event_log=str(event_path(session_id)),
    )


def save_session(session: SessionResult, out_dir: str | Path) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    base = f"session_{session.student_name.lower()}_{stamp}"

    json_path = out_dir / f"{base}.json"
    json_path.write_text(json.dumps(session.to_dict(), indent=2), encoding="utf-8")

    summary_path = out_dir / f"{base}_parent.md"
    summary_path.write_text(session.parent_summary, encoding="utf-8")

    lesson_json = save_lesson(session.lesson, out_dir)
    lesson_md = out_dir / f"{session.lesson.skill}__{session.lesson.method}.md"
    lesson_md.write_text(render_lesson_markdown(session.lesson), encoding="utf-8")

    report = out_dir / f"{base}_report.md"
    bin_name = ["novice", "intermediate", "advanced"][mastery_bin(session.diagnostic.ability)]
    report.write_text(
        "\n".join(
            [
                f"# Live session report — {session.student_name}",
                "",
                f"- Modeled level: **{bin_name}** ({session.diagnostic.ability:.0%})",
                f"- Diagnostic: **{session.diagnostic.n_correct}/{session.diagnostic.n_items}**",
                f"- Weakest skill: **{SKILL_LABELS.get(session.diagnostic.weakest_skill, session.diagnostic.weakest_skill)}**",
                f"- Method chosen: **{METHOD_PLAIN.get(session.method, session.method)}**",
                f"- Lesson SymPy-verified: **{'yes' if session.lesson.all_verified else 'NO'}**",
                f"- Delayed check: **{session.delayed.n_correct}/{session.delayed.n_items}** ({session.delayed.score:.0%})",
                f"- Review due: **{'yes' if session.delayed.review_due else 'no'}**",
                "",
                "## Parent summary",
                "",
                session.parent_summary,
            ]
        ),
        encoding="utf-8",
    )

    return {
        "json": json_path,
        "parent": summary_path,
        "report": report,
        "lesson_json": lesson_json,
        "lesson_md": lesson_md,
    }
