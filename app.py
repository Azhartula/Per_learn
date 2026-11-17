"""PerLearn — small Streamlit front end for the adaptive learn-with-me loop."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from pll.bandit import make_context, mastery_bin  # noqa: E402
from pll.config import METHODS  # noqa: E402
from pll.learner import (  # noqa: E402
    SessionRecord,
    adaptation_summary,
    load_or_create,
    save_profile,
)
from pll.lessons import generate_lesson, render_lesson_markdown  # noqa: E402
from pll.ollama_client import is_reachable  # noqa: E402
from pll.parent_summary import METHOD_PLAIN  # noqa: E402
from pll.prompts import SKILL_LABELS  # noqa: E402
from pll.questions import Question, QuestionBank  # noqa: E402
from pll.sympy_check import verify_answer  # noqa: E402

BIN_NAMES = ("novice", "intermediate", "advanced")


st.set_page_config(page_title="PerLearn", page_icon="📗", layout="wide")

st.markdown(
    """
    <style>
      .block-container { max-width: 920px; padding-top: 1.4rem; }
      h1, h2, h3 { font-family: Georgia, serif; letter-spacing: -0.02em; }
      .stMetric { background: #eef5f0; border-radius: 12px; padding: 0.4rem 0.6rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _init_state() -> None:
    defaults = {
        "phase": "home",  # home | diagnostic | lesson | practice | delayed | done
        "name": "Azhar",
        "profile": None,
        "bank": None,
        "diag_questions": [],
        "diag_index": 0,
        "diag_responses": {},
        "diagnostic": None,
        "method": None,
        "method_idx": None,
        "lesson": None,
        "practice_index": 0,
        "practice_correct": 0,
        "practice_total": 0,
        "delayed_items": [],
        "delayed_index": 0,
        "delayed_correct": 0,
        "use_ollama": True,
        "model": "qwen2.5:7b",
        "n_diag": 5,
        "mastery_before": 0.28,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _bank() -> QuestionBank:
    if st.session_state.bank is None:
        st.session_state.bank = QuestionBank.load()
    return st.session_state.bank


def _render_question(q: Question) -> str | None:
    st.markdown(f"**{q.stem}**")
    key = f"ans_{st.session_state.phase}_{q.id}_{st.session_state.get('diag_index', 0)}_{st.session_state.get('practice_index', 0)}_{st.session_state.get('delayed_index', 0)}"
    if q.choices:
        choice = st.radio("Choose one:", list(q.choices), key=key, index=None)
        return choice
    return st.text_input("Your answer", key=key)


def _sidebar_status() -> None:
    st.sidebar.title("PerLearn")
    st.sidebar.caption("You answer → it adapts how it teaches.")
    name = st.sidebar.text_input("Your name", value=st.session_state.name)
    st.session_state.name = name.strip() or "Learner"
    st.session_state.use_ollama = st.sidebar.toggle(
        "Use local Qwen (Ollama)",
        value=st.session_state.use_ollama,
    )
    st.session_state.model = st.sidebar.text_input("Ollama model", value=st.session_state.model)
    st.session_state.n_diag = st.sidebar.slider("Sample quiz length", 3, 8, st.session_state.n_diag)

    if st.sidebar.button("Load / refresh profile"):
        st.session_state.profile = load_or_create(st.session_state.name)
        st.rerun()

    profile = st.session_state.profile
    if profile is None:
        st.session_state.profile = load_or_create(st.session_state.name)
        profile = st.session_state.profile

    st.sidebar.markdown("---")
    st.sidebar.metric("Mastery", f"{profile.mastery:.0%}")
    st.sidebar.metric("Sessions", profile.sessions_completed)
    st.sidebar.write(f"**Level:** {BIN_NAMES[mastery_bin(profile.mastery)]}")
    st.sidebar.write(f"**Preferred now:** {METHOD_PLAIN[profile.preferred_method()]}")
    scores = profile.method_scores()
    st.sidebar.write("Method scores")
    for m, s in sorted(scores.items(), key=lambda x: -x[1]):
        st.sidebar.progress(min(max(s, 0.0), 1.0), text=f"{METHOD_PLAIN[m][:28]} ({s:.2f})")

    if st.sidebar.button("Reset this session flow"):
        for k in list(st.session_state.keys()):
            if k not in {"name", "use_ollama", "model", "n_diag"}:
                del st.session_state[k]
        st.rerun()


def phase_home() -> None:
    st.title("Learn with me")
    st.write(
        "I'll give you a few questions, pick a teaching method based on how you're doing, "
        "generate a lesson, then check you again — that check trains how I teach you next time."
    )
    profile = st.session_state.profile
    st.code(adaptation_summary(profile), language=None)

    ollama_ok = is_reachable()
    if st.session_state.use_ollama and not ollama_ok:
        st.warning("Ollama is not reachable. Start `ollama serve` or turn off local Qwen in the sidebar.")
    elif st.session_state.use_ollama:
        st.success(f"Ollama ready · model `{st.session_state.model}`")

    if st.button("Start a session", type="primary"):
        bank = _bank()
        # Preselect diagnostic items via a dry run with placeholder answers replaced live.
        # We'll pick questions adaptively as the user answers; start with an empty list
        # and generate the next one each step.
        st.session_state.phase = "diagnostic"
        st.session_state.diag_index = 0
        st.session_state.diag_responses = {}
        st.session_state.diag_questions = []
        st.session_state.mastery_before = profile.mastery
        st.session_state._diag_ability = 0.45
        st.session_state._diag_used = set()
        st.session_state._diag_trials = []
        st.session_state._skill_correct = {s: [] for s in bank.skills}
        st.rerun()


def _next_diag_question() -> Question | None:
    from pll.diagnostic import _pick_next

    bank = _bank()
    ability = st.session_state._diag_ability
    used = st.session_state._diag_used
    skill_counts = {s: len(v) for s, v in st.session_state._skill_correct.items()}
    rng = np.random.default_rng(1000 + st.session_state.profile.sessions_completed + st.session_state.diag_index)
    return _pick_next(bank, used, ability, skill_counts, rng)


def phase_diagnostic() -> None:
    st.header("Step 1 · Sample questions")
    st.caption("Answer honestly — this estimates where you are.")
    i = st.session_state.diag_index
    st.progress((i) / st.session_state.n_diag, text=f"Question {min(i + 1, st.session_state.n_diag)} of {st.session_state.n_diag}")

    if i >= st.session_state.n_diag:
        _finish_diagnostic()
        return

    if st.session_state.get("_current_q") is None:
        q = _next_diag_question()
        if q is None:
            st.error("No more questions available.")
            return
        st.session_state._current_q = q
    q = st.session_state._current_q

    ans = _render_question(q)
    if st.button("Submit answer", type="primary", disabled=ans is None or str(ans).strip() == ""):
        from pll.diagnostic import Trial, _update_ability

        expected = q.answer_sympy if q.answer_sympy is not None else q.answer
        ok = verify_answer(expected, ans).ok
        st.session_state._diag_used.add(q.id)
        st.session_state._diag_ability = _update_ability(st.session_state._diag_ability, ok, q.difficulty)
        st.session_state._skill_correct[q.skill].append(ok)
        st.session_state._diag_trials.append(
            Trial(
                question_id=q.id,
                skill=q.skill,
                difficulty=q.difficulty,
                correct=ok,
                response=str(ans),
                misconceptions=q.misconceptions,
            )
        )
        st.session_state.diag_index += 1
        st.session_state._current_q = None
        st.rerun()


def _finish_diagnostic() -> None:
    from pll.diagnostic import DiagnosticResult

    trials = st.session_state._diag_trials
    skill_correct = st.session_state._skill_correct
    skill_scores = {s: (sum(v) / len(v) if v else 0.5) for s, v in skill_correct.items() if v}
    if not skill_scores:
        skill_scores = {_bank().skills[0]: 0.5}
    accuracy = sum(1 for t in trials if t.correct) / max(len(trials), 1)
    ability = float(np.clip(0.6 * st.session_state._diag_ability + 0.4 * accuracy, 0.08, 0.95))
    weakest = min(skill_scores, key=skill_scores.get)
    misc_hits: dict[str, int] = {}
    for t in trials:
        if not t.correct:
            for m in t.misconceptions:
                misc_hits[m] = misc_hits.get(m, 0) + 1
    diagnostic = DiagnosticResult(
        ability=ability,
        n_correct=sum(1 for t in trials if t.correct),
        n_items=len(trials),
        skill_scores=skill_scores,
        active_misconceptions=sorted(misc_hits, key=misc_hits.get, reverse=True),
        weakest_skill=weakest,
        trials=trials,
    )
    st.session_state.diagnostic = diagnostic

    profile = st.session_state.profile
    profile.mastery = float(np.clip(0.55 * profile.mastery + 0.45 * ability, 0.05, 0.95))
    profile.focus_skill = weakest

    bandit = profile.to_bandit(seed=profile.sessions_completed + 7)
    context = make_context(profile.mastery)
    if int(bandit.counts.sum()) < 2:
        method_idx = int(np.argmax(bandit.mean_rewards(context)))
    else:
        method_idx = bandit.select(context)
    st.session_state.method_idx = method_idx
    st.session_state.method = METHODS[method_idx]
    st.session_state._bandit = bandit
    st.session_state.phase = "lesson"
    st.rerun()


def phase_lesson() -> None:
    st.header("Step 2 · Your lesson")
    diagnostic = st.session_state.diagnostic
    method = st.session_state.method
    profile = st.session_state.profile

    c1, c2, c3 = st.columns(3)
    c1.metric("Mastery", f"{profile.mastery:.0%}")
    c2.metric("Diagnostic", f"{diagnostic.n_correct}/{diagnostic.n_items}")
    c3.metric("Method today", METHOD_PLAIN[method].split(",")[0])

    st.write(f"**Focus:** {SKILL_LABELS.get(diagnostic.weakest_skill, diagnostic.weakest_skill)}")
    st.write(f"**Teaching with:** {METHOD_PLAIN[method]}")

    if st.session_state.lesson is None:
        weak_miss: dict[str, int] = {}
        for t in diagnostic.trials:
            if t.skill == diagnostic.weakest_skill and not t.correct:
                for m in t.misconceptions:
                    weak_miss[m] = weak_miss.get(m, 0) + 1
        misconception_id = (
            max(weak_miss, key=weak_miss.get)
            if weak_miss
            else (diagnostic.active_misconceptions[0] if diagnostic.active_misconceptions else None)
        )
        use_ollama = st.session_state.use_ollama and is_reachable()
        with st.spinner("Generating lesson" + (" with local Qwen…" if use_ollama else "…")):
            lesson = generate_lesson(
                method=method,
                skill=diagnostic.weakest_skill,
                misconception_id=misconception_id,
                bank=_bank(),
                use_ollama=use_ollama,
                ollama_model=st.session_state.model if use_ollama else None,
            )
        st.session_state.lesson = lesson

    lesson = st.session_state.lesson
    st.caption(
        f"Source: {lesson.source} · SymPy verified: {lesson.all_verified}"
        + (f" · model: {lesson.model_name}" if lesson.model_name else "")
    )
    st.markdown(render_lesson_markdown(lesson))

    if st.button("I've read it — go to practice", type="primary"):
        st.session_state.phase = "practice"
        st.session_state.practice_index = 0
        st.session_state.practice_correct = 0
        st.session_state.practice_total = 0
        st.rerun()


def phase_practice() -> None:
    st.header("Step 3 · Practice")
    lesson = st.session_state.lesson
    items = lesson.practice
    i = st.session_state.practice_index
    if i >= len(items):
        st.success(
            f"Practice done: {st.session_state.practice_correct}/{st.session_state.practice_total} "
            "(practice does **not** train the bandit)"
        )
        if st.button("Start unassisted check", type="primary"):
            st.session_state.phase = "delayed"
            used = {t.question_id for t in st.session_state.diagnostic.trials} | {
                p["id"] for p in lesson.practice
            }
            bank = _bank()
            pool = [
                q
                for q in bank.by_skill(st.session_state.diagnostic.weakest_skill)
                if q.id not in used
            ]
            pool = sorted(pool, key=lambda q: (q.difficulty, q.id))[:3]
            st.session_state.delayed_items = pool
            st.session_state.delayed_index = 0
            st.session_state.delayed_correct = 0
            st.rerun()
        return

    st.progress(i / max(len(items), 1), text=f"Practice {i + 1} of {len(items)}")
    q = _bank().get(items[i]["id"])
    ans = _render_question(q)
    if st.button("Check", type="primary", disabled=ans is None or str(ans).strip() == ""):
        expected = q.answer_sympy if q.answer_sympy is not None else q.answer
        ok = verify_answer(expected, ans).ok
        st.session_state.practice_total += 1
        st.session_state.practice_correct += int(ok)
        st.session_state.practice_index += 1
        if ok:
            st.success("Correct")
        else:
            st.warning(f"Answer was `{q.answer}`")
        st.rerun()


def phase_delayed() -> None:
    st.header("Step 4 · Unassisted check")
    st.caption("No peeking — this score trains how I teach you next time.")
    items = st.session_state.delayed_items
    i = st.session_state.delayed_index

    if i >= len(items):
        _finish_session()
        return

    st.progress(i / max(len(items), 1), text=f"Check {i + 1} of {len(items)}")
    q = items[i]
    ans = _render_question(q)
    if st.button("Submit", type="primary", disabled=ans is None or str(ans).strip() == ""):
        expected = q.answer_sympy if q.answer_sympy is not None else q.answer
        ok = verify_answer(expected, ans).ok
        st.session_state.delayed_correct += int(ok)
        st.session_state.delayed_index += 1
        st.rerun()


def _finish_session() -> None:
    profile = st.session_state.profile
    bandit = st.session_state._bandit
    method_idx = st.session_state.method_idx
    method = st.session_state.method
    diagnostic = st.session_state.diagnostic
    n = max(len(st.session_state.delayed_items), 1)
    delayed_score = st.session_state.delayed_correct / n
    context = make_context(profile.mastery)
    bandit.update(method_idx, context, delayed_score)
    profile.store_bandit(bandit)
    profile.mastery = float(np.clip(profile.mastery + 0.12 * (delayed_score - 0.5), 0.05, 0.95))
    profile.sessions_completed += 1
    profile.history.append(
        SessionRecord(
            session=profile.sessions_completed,
            timestamp=datetime.now(timezone.utc).isoformat(),
            mastery_before=round(float(st.session_state.mastery_before), 3),
            mastery_after=round(profile.mastery, 3),
            method=method,
            delayed_score=round(delayed_score, 3),
            skill=diagnostic.weakest_skill,
            diagnostic_score=f"{diagnostic.n_correct}/{diagnostic.n_items}",
            notes=f"source={st.session_state.lesson.source}",
        )
    )
    path = save_profile(profile)
    st.session_state.profile = profile
    st.session_state._save_path = str(path)
    st.session_state._last_delayed = delayed_score
    st.session_state.phase = "done"
    st.rerun()


def phase_done() -> None:
    st.header("How I'm adapting to you")
    st.metric("Delayed check", f"{st.session_state._last_delayed:.0%}")
    st.code(adaptation_summary(st.session_state.profile), language=None)
    st.caption(f"Saved: {st.session_state._save_path}")
    if st.button("Do another session", type="primary"):
        st.session_state.phase = "home"
        st.session_state.lesson = None
        st.session_state.diagnostic = None
        st.rerun()
    if st.button("Back to home"):
        st.session_state.phase = "home"
        st.rerun()


def main() -> None:
    _init_state()
    if st.session_state.profile is None:
        st.session_state.profile = load_or_create(st.session_state.name)
    _sidebar_status()

    phase = st.session_state.phase
    if phase == "home":
        phase_home()
    elif phase == "diagnostic":
        phase_diagnostic()
    elif phase == "lesson":
        phase_lesson()
    elif phase == "practice":
        phase_practice()
    elif phase == "delayed":
        phase_delayed()
    elif phase == "done":
        phase_done()
    else:
        st.session_state.phase = "home"
        st.rerun()


if __name__ == "__main__":
    main()
