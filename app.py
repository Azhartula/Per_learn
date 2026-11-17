"""PerLearn Streamlit demo — clear pitch + guided MCQ learning session."""

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
    load_or_create,
    save_profile,
)
from pll.lessons import generate_lesson, render_lesson_markdown  # noqa: E402
from pll.mcq import McqQuestion, as_mcq  # noqa: E402
from pll.ollama_client import is_reachable  # noqa: E402
from pll.parent_summary import METHOD_PLAIN  # noqa: E402
from pll.prompts import SKILL_LABELS  # noqa: E402
from pll.questions import Question, QuestionBank  # noqa: E402
from pll.sympy_check import verify_answer  # noqa: E402

BIN_NAMES = ("just starting", "building up", "getting strong")
STEPS = [
    ("quiz", "1. Find the gap"),
    ("bridge", "2. Choose how to teach"),
    ("lesson", "3. Learn"),
    ("practice", "4. Practice"),
    ("check", "5. Check it stuck"),
    ("done", "6. See what changed"),
]


st.set_page_config(page_title="PerLearn", page_icon="📗", layout="centered")

st.markdown(
    """
    <style>
      .block-container { max-width: 760px; padding-top: 1.2rem; padding-bottom: 3rem; }
      h1, h2, h3 { font-family: Georgia, "Iowan Old Style", serif; letter-spacing: -0.02em; }
      .idea-box {
        background: linear-gradient(135deg, #eef6f1, #f7f4ee);
        border: 1px solid #d5e4db;
        border-radius: 16px;
        padding: 1.1rem 1.25rem;
        margin: 0.8rem 0 1.2rem;
      }
      .step-chip {
        display: inline-block;
        background: #e7f0ea;
        color: #1b4d3a;
        border-radius: 999px;
        padding: 0.25rem 0.7rem;
        font-size: 0.85rem;
        font-weight: 700;
        margin-bottom: 0.6rem;
      }
      .why-box {
        border-left: 4px solid #1b7a5a;
        padding: 0.35rem 0 0.35rem 0.9rem;
        margin: 0.8rem 0 1rem;
        color: #24352c;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


def _init_state() -> None:
    defaults = {
        "phase": "home",
        "name": "Azhar",
        "profile": None,
        "bank": None,
        "diag_index": 0,
        "diagnostic": None,
        "method": None,
        "method_idx": None,
        "method_before_session": None,
        "lesson": None,
        "practice_index": 0,
        "practice_correct": 0,
        "practice_total": 0,
        "delayed_items": [],
        "delayed_index": 0,
        "delayed_correct": 0,
        "use_ollama": False,  # default off so demos stay fast/clear
        "model": "qwen2.5:7b",
        "n_diag": 4,
        "mastery_before": 0.28,
        "fast_demo": True,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _bank() -> QuestionBank:
    if st.session_state.bank is None:
        st.session_state.bank = QuestionBank.load()
    return st.session_state.bank


def _short_method(method: str) -> str:
    return {
        "worked_example": "Worked example first",
        "problem_first": "Try a problem first",
        "visual": "Visual (bars / number line)",
        "story_analogy": "Real-world story",
    }.get(method, METHOD_PLAIN.get(method, method))


def _stepper() -> None:
    phase = st.session_state.phase
    mapping = {
        "home": -1,
        "diagnostic": 0,
        "bridge": 1,
        "lesson": 2,
        "practice": 3,
        "delayed": 4,
        "done": 5,
    }
    current = mapping.get(phase, -1)
    if current < 0:
        return
    cols = st.columns(len(STEPS))
    for i, (_, label) in enumerate(STEPS):
        with cols[i]:
            if i < current:
                st.markdown(f"✅ **{label}**")
            elif i == current:
                st.markdown(f"👉 **{label}**")
            else:
                st.caption(label)
    st.divider()


def _render_mcq(q: McqQuestion) -> str | None:
    st.markdown(f"### {q.stem}")
    key = (
        f"mcq_{st.session_state.phase}_{q.id}_"
        f"{st.session_state.get('diag_index', 0)}_"
        f"{st.session_state.get('practice_index', 0)}_"
        f"{st.session_state.get('delayed_index', 0)}"
    )
    labels = [f"{chr(65 + i)})  {c}" for i, c in enumerate(q.choices)]
    choice = st.radio("Pick one answer:", labels, key=key, index=None)
    if choice is None:
        return None
    return choice.split(")  ", 1)[-1]


def _sidebar() -> None:
    st.sidebar.markdown("## PerLearn")
    st.sidebar.caption("Demo for Year 5 fractions")
    st.session_state.name = st.sidebar.text_input("Your name", value=st.session_state.name).strip() or "Learner"

    profile = st.session_state.profile
    if profile is None or profile.name != st.session_state.name:
        st.session_state.profile = load_or_create(st.session_state.name)
        profile = st.session_state.profile

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Your progress")
    st.sidebar.metric("Confidence so far", f"{profile.mastery:.0%}")
    st.sidebar.metric("Sessions done", profile.sessions_completed)
    st.sidebar.write(f"Level: **{BIN_NAMES[mastery_bin(profile.mastery)]}**")
    st.sidebar.write(f"Best teaching style right now:\n\n**{_short_method(profile.preferred_method())}**")

    with st.sidebar.expander("Advanced settings", expanded=False):
        st.session_state.fast_demo = st.toggle(
            "Fast demo (shorter quiz, template lesson)",
            value=st.session_state.fast_demo,
            help="Turn off if you want the local AI model to write the lesson.",
        )
        st.session_state.use_ollama = st.toggle(
            "Use local AI lesson (Ollama / Qwen)",
            value=st.session_state.use_ollama and not st.session_state.fast_demo,
        )
        if st.session_state.use_ollama:
            st.session_state.fast_demo = False
        st.session_state.model = st.text_input("Ollama model", value=st.session_state.model)
        st.session_state.n_diag = 3 if st.session_state.fast_demo else st.slider(
            "Quiz length", 3, 6, st.session_state.n_diag
        )
        if st.session_state.use_ollama and not is_reachable():
            st.warning("Ollama not running. Start it or use Fast demo.")

    if st.sidebar.button("Restart demo flow"):
        keep = {
            "name": st.session_state.name,
            "use_ollama": st.session_state.use_ollama,
            "model": st.session_state.model,
            "n_diag": st.session_state.n_diag,
            "fast_demo": st.session_state.fast_demo,
        }
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        for k, v in keep.items():
            st.session_state[k] = v
        st.session_state.profile = load_or_create(st.session_state.name)
        st.session_state.phase = "home"
        st.rerun()


def phase_home() -> None:
    st.title("PerLearn")
    st.subheader("Most apps pick *what* to learn next. We figure out *how* to teach this child.")

    st.markdown(
        """
        <div class="idea-box">
          <strong>The idea in one line</strong><br/>
          Watch how a learner answers → try a teaching style → check if it really stuck →
          keep the styles that work for <em>this</em> child (and change as they grow).
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### In this 5-minute demo you will:")
    st.markdown(
        """
1. **Answer a few MCQs** — we find a weak spot  
2. **Get a lesson** in a teaching style chosen for you  
3. **Practice**, then take a short **no-help check**  
4. **See how the system updates** what works for you  
        """
    )

    st.markdown("### Four teaching styles we can switch between")
    c1, c2 = st.columns(2)
    with c1:
        st.info("**Worked example first**\n\nShow steps, then practice.")
        st.info("**Visual**\n\nFraction bars / number lines.")
    with c2:
        st.info("**Problem first**\n\nTry it, then explain.")
        st.info("**Story**\n\nPizza, recipes, real life.")

    profile = st.session_state.profile
    if profile.sessions_completed:
        st.success(
            f"Welcome back, {profile.name}. "
            f"After {profile.sessions_completed} session(s), your best style so far looks like: "
            f"**{_short_method(profile.preferred_method())}**."
        )
    else:
        st.caption("First time here — we’ll learn your pattern as you answer.")

    if st.button("Start the demo →", type="primary", use_container_width=True):
        bank = _bank()
        st.session_state.phase = "diagnostic"
        st.session_state.diag_index = 0
        st.session_state.mastery_before = profile.mastery
        st.session_state.method_before_session = profile.preferred_method()
        st.session_state._diag_ability = 0.45
        st.session_state._diag_used = set()
        st.session_state._diag_trials = []
        st.session_state._skill_correct = {s: [] for s in bank.skills}
        st.session_state._current_mcq = None
        st.session_state.lesson = None
        st.session_state.diagnostic = None
        if st.session_state.fast_demo:
            st.session_state.n_diag = 3
            st.session_state.use_ollama = False
        st.rerun()


def _next_diag_question() -> Question | None:
    from pll.diagnostic import _pick_next

    bank = _bank()
    ability = st.session_state._diag_ability
    used = st.session_state._diag_used
    skill_counts = {s: len(v) for s, v in st.session_state._skill_correct.items()}
    rng = np.random.default_rng(
        1000 + st.session_state.profile.sessions_completed + st.session_state.diag_index
    )
    return _pick_next(bank, used, ability, skill_counts, rng)


def phase_diagnostic() -> None:
    st.markdown('<div class="step-chip">Step 1 of 6 · Find the gap</div>', unsafe_allow_html=True)
    st.header("Quick quiz")
    st.markdown(
        '<div class="why-box">Why this step? We need to know <strong>where you’re stuck</strong> '
        "before we choose how to teach.</div>",
        unsafe_allow_html=True,
    )
    i = st.session_state.diag_index
    n = st.session_state.n_diag
    st.progress(i / n, text=f"Question {min(i + 1, n)} of {n}")

    if i >= n:
        _finish_diagnostic()
        return

    if st.session_state.get("_current_mcq") is None:
        raw = _next_diag_question()
        if raw is None:
            st.error("No questions left in the bank.")
            return
        st.session_state._current_mcq = as_mcq(raw)
    q = st.session_state._current_mcq

    ans = _render_mcq(q)
    if st.button("Submit", type="primary", disabled=ans is None, use_container_width=True):
        from pll.diagnostic import Trial, _update_ability

        ok = verify_answer(q.answer, ans).ok
        st.session_state._diag_used.add(q.id)
        st.session_state._diag_ability = _update_ability(
            st.session_state._diag_ability, ok, q.difficulty
        )
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
        st.session_state._current_mcq = None
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
    st.session_state.phase = "bridge"
    st.rerun()


def phase_bridge() -> None:
    st.markdown('<div class="step-chip">Step 2 of 6 · Choose how to teach</div>', unsafe_allow_html=True)
    st.header("Here’s what we noticed")
    d = st.session_state.diagnostic
    method = st.session_state.method
    profile = st.session_state.profile
    bank = _bank()

    skill = SKILL_LABELS.get(d.weakest_skill, d.weakest_skill)
    why = "a common mix-up on this topic"
    if d.active_misconceptions:
        why = bank.misconceptions.get(d.active_misconceptions[0], d.active_misconceptions[0])

    a, b, c = st.columns(3)
    a.metric("Quiz score", f"{d.n_correct}/{d.n_items}")
    b.metric("Confidence", f"{profile.mastery:.0%}")
    c.metric("Level", BIN_NAMES[mastery_bin(profile.mastery)])

    st.markdown(
        f"""
        <div class="idea-box">
          <strong>Weak spot:</strong> {skill}<br/>
          <strong>Likely mix-up:</strong> {why}<br/><br/>
          <strong>So today we’ll teach with:</strong> {_short_method(method)}
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="why-box">This is the core idea: we don’t only pick the next topic — '
        "we pick the <strong>teaching style</strong> that should help <em>you</em> right now.</div>",
        unsafe_allow_html=True,
    )

    if st.button("Show my lesson →", type="primary", use_container_width=True):
        st.session_state.phase = "lesson"
        st.rerun()


def phase_lesson() -> None:
    st.markdown('<div class="step-chip">Step 3 of 6 · Learn</div>', unsafe_allow_html=True)
    st.header("Your personalised lesson")
    diagnostic = st.session_state.diagnostic
    method = st.session_state.method

    st.markdown(
        f'<div class="why-box">Teaching style: <strong>{_short_method(method)}</strong> · '
        f"Topic: <strong>{SKILL_LABELS.get(diagnostic.weakest_skill, diagnostic.weakest_skill)}</strong></div>",
        unsafe_allow_html=True,
    )

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
        label = "Writing lesson with local AI…" if use_ollama else "Preparing lesson…"
        with st.spinner(label):
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
    with st.expander("Lesson", expanded=True):
        # Strip noisy metadata lines for demos
        md = render_lesson_markdown(lesson)
        lines = [
            ln
            for ln in md.splitlines()
            if not ln.startswith("**Source:**")
            and not ln.startswith("**Model:**")
            and not ln.startswith("**All answers")
        ]
        st.markdown("\n".join(lines))

    if st.button("I read it — practice now →", type="primary", use_container_width=True):
        st.session_state.phase = "practice"
        st.session_state.practice_index = 0
        st.session_state.practice_correct = 0
        st.session_state.practice_total = 0
        st.session_state._current_practice_mcq = None
        st.rerun()


def phase_practice() -> None:
    st.markdown('<div class="step-chip">Step 4 of 6 · Practice</div>', unsafe_allow_html=True)
    st.header("Practice questions")
    st.markdown(
        '<div class="why-box">Practice helps you learn — but we <strong>don’t</strong> use practice '
        "scores to decide your teaching style (that can reward easy help). "
        "The next no-help check does.</div>",
        unsafe_allow_html=True,
    )
    lesson = st.session_state.lesson
    items = lesson.practice
    i = st.session_state.practice_index

    if i >= len(items):
        st.success(
            f"Practice finished: {st.session_state.practice_correct}/"
            f"{st.session_state.practice_total} correct"
        )
        if st.button("Final no-help check →", type="primary", use_container_width=True):
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
            st.session_state.delayed_items = [as_mcq(q) for q in pool]
            st.session_state.delayed_index = 0
            st.session_state.delayed_correct = 0
            st.session_state.phase = "delayed"
            st.rerun()
        return

    st.progress(i / max(len(items), 1), text=f"Practice {i + 1} of {len(items)}")
    if st.session_state.get("_current_practice_mcq") is None:
        st.session_state._current_practice_mcq = as_mcq(_bank().get(items[i]["id"]))
    q = st.session_state._current_practice_mcq
    ans = _render_mcq(q)
    if st.button("Check answer", type="primary", disabled=ans is None, use_container_width=True):
        ok = verify_answer(q.answer, ans).ok
        st.session_state.practice_total += 1
        st.session_state.practice_correct += int(ok)
        st.session_state.practice_index += 1
        st.session_state._current_practice_mcq = None
        st.rerun()


def phase_delayed() -> None:
    st.markdown('<div class="step-chip">Step 5 of 6 · Check it stuck</div>', unsafe_allow_html=True)
    st.header("No-help check")
    st.markdown(
        '<div class="why-box">Answer without looking back. '
        "This score tells us if today’s teaching style <strong>actually worked</strong>.</div>",
        unsafe_allow_html=True,
    )
    items = st.session_state.delayed_items
    i = st.session_state.delayed_index
    if i >= len(items):
        _finish_session()
        return

    st.progress(i / max(len(items), 1), text=f"Check {i + 1} of {len(items)}")
    q = items[i]
    ans = _render_mcq(q)
    if st.button("Lock in answer", type="primary", disabled=ans is None, use_container_width=True):
        ok = verify_answer(q.answer, ans).ok
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
    st.markdown('<div class="step-chip">Step 6 of 6 · See what changed</div>', unsafe_allow_html=True)
    st.header("This is the point of PerLearn")

    profile = st.session_state.profile
    before = st.session_state.method_before_session or st.session_state.method
    used = st.session_state.method
    after = profile.preferred_method()
    delayed = st.session_state._last_delayed

    a, b = st.columns(2)
    a.metric("No-help check", f"{delayed:.0%}")
    b.metric(
        "Confidence",
        f"{profile.mastery:.0%}",
        delta=f"{(profile.mastery - st.session_state.mastery_before)*100:.0f} pts",
    )

    st.markdown(
        f"""
        <div class="idea-box">
          <strong>What happened this session</strong><br/>
          We taught with: <strong>{_short_method(used)}</strong><br/>
          Your no-help score was <strong>{delayed:.0%}</strong>.
          That result updates what we think works for you.
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        st.info(f"**Before this session**\n\n{_short_method(before)}")
    with c2:
        st.success(f"**Best guess for next time**\n\n{_short_method(after)}")

    if before != after:
        st.warning(
            f"Adaptation happened: preference moved from **{_short_method(before)}** "
            f"to **{_short_method(after)}** based on whether today’s lesson stuck."
        )
    else:
        st.info(
            f"Still leaning toward **{_short_method(after)}**. "
            "Do another session — as you get stronger, the best style can change."
        )

    st.markdown("### Method fit scores (for your current level)")
    for method, score in sorted(profile.method_scores().items(), key=lambda x: -x[1]):
        st.progress(min(max(score, 0.0), 1.0), text=f"{_short_method(method)} — {score:.2f}")

    st.caption("Run more sessions to see the teaching style shift as mastery grows.")

    if st.button("Do another session", type="primary", use_container_width=True):
        st.session_state.phase = "home"
        st.session_state.lesson = None
        st.session_state.diagnostic = None
        st.rerun()


def main() -> None:
    _init_state()
    if st.session_state.profile is None:
        st.session_state.profile = load_or_create(st.session_state.name)
    _sidebar()
    _stepper()

    phase = st.session_state.phase
    {
        "home": phase_home,
        "diagnostic": phase_diagnostic,
        "bridge": phase_bridge,
        "lesson": phase_lesson,
        "practice": phase_practice,
        "delayed": phase_delayed,
        "done": phase_done,
    }.get(phase, phase_home)()


if __name__ == "__main__":
    main()
