"""PerLearn — company pitch deck + guided live demo."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from pll.bandit import make_context, mastery_bin  # noqa: E402
from pll.config import CONTENT_VERSION, METHODS  # noqa: E402
from pll.events import append_event, log_item_response, new_session_id  # noqa: E402
from pll.learner import SessionRecord, load_or_create, save_profile  # noqa: E402
from pll.lessons import generate_lesson, render_lesson_markdown  # noqa: E402
from pll.mcq import McqQuestion, as_mcq  # noqa: E402
from pll.ollama_client import is_reachable  # noqa: E402
from pll.parent_summary import METHOD_PLAIN  # noqa: E402
from pll.prompts import SKILL_LABELS  # noqa: E402
from pll.questions import Question, QuestionBank  # noqa: E402
from pll.sympy_check import verify_answer  # noqa: E402

BIN_NAMES = ("just starting", "building up", "getting strong")
STEPS = [
    ("quiz", "Gap"),
    ("bridge", "Style"),
    ("lesson", "Teach"),
    ("practice", "Practice"),
    ("check", "Check"),
    ("done", "Adapt"),
]
PITCH_SLIDES = [
    "hook",
    "problem",
    "insight",
    "loop",
    "evidence",
    "who",
    "ask",
]


st.set_page_config(
    page_title="PerLearn — Pitch + Demo",
    page_icon="📗",
    layout="centered",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .block-container { max-width: 820px; padding-top: 1rem; padding-bottom: 3rem; }
      h1, h2, h3 { font-family: Georgia, "Iowan Old Style", serif; letter-spacing: -0.02em; }
      .card {
        background: #f3f7f4 !important;
        color: #14241c !important;
        border: 1px solid #c9ddd2;
        border-radius: 16px;
        padding: 1.15rem 1.3rem;
        margin: 0.75rem 0 1rem;
        line-height: 1.55;
      }
      .card strong, .card em, .card span { color: #0f1c16 !important; }
      .chip {
        display: inline-block;
        background: #1b7a5a;
        color: #ffffff !important;
        border-radius: 999px;
        padding: 0.28rem 0.75rem;
        font-size: 0.8rem;
        font-weight: 700;
        margin-bottom: 0.55rem;
        letter-spacing: 0.02em;
      }
      .quote {
        border-left: 4px solid #1b7a5a;
        padding: 0.2rem 0 0.2rem 0.9rem;
        margin: 0.7rem 0 1rem;
        color: #24352c !important;
        font-size: 1.05rem;
      }
      .big-number {
        font-family: Georgia, serif;
        font-size: 2.4rem;
        font-weight: 700;
        color: #1b7a5a !important;
        line-height: 1.1;
        margin: 0.2rem 0;
      }
      .vs-bad {
        background: #f7ebe6 !important;
        border-color: #e2c4b6 !important;
      }
      .vs-good {
        background: #e8f4ee !important;
        border-color: #b7d8c6 !important;
      }
      div[data-testid="stMetricValue"] { font-size: 1.35rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _init_state() -> None:
    defaults = {
        "mode": "landing",  # landing | pitch | demo
        "pitch_i": 0,
        "phase": "home",
        "name": "Guest",
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
        "use_ollama": False,
        "model": "qwen2.5:7b",
        "n_diag": 3,
        "mastery_before": 0.28,
        "fast_demo": True,
        "event_session_id": None,
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


def _phase1() -> dict:
    path = ROOT / "outputs" / "phase1_metrics.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}


def _card(html: str, kind: str = "") -> None:
    cls = f"card {kind}".strip()
    st.markdown(f'<div class="{cls}">{html}</div>', unsafe_allow_html=True)


def _chip(text: str) -> None:
    st.markdown(f'<div class="chip">{text}</div>', unsafe_allow_html=True)


def _nav_row(back_label: str, next_label: str, on_back, on_next) -> None:
    c1, c2 = st.columns(2)
    with c1:
        if st.button(back_label, use_container_width=True):
            on_back()
            st.rerun()
    with c2:
        if st.button(next_label, type="primary", use_container_width=True):
            on_next()
            st.rerun()


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
    st.sidebar.caption("Company pitch + live demo")

    mode = st.session_state.mode
    if st.sidebar.button("🏠 Landing", use_container_width=True, disabled=mode == "landing"):
        st.session_state.mode = "landing"
        st.rerun()
    if st.sidebar.button("🎯 Company pitch", use_container_width=True, disabled=mode == "pitch"):
        st.session_state.mode = "pitch"
        st.session_state.pitch_i = 0
        st.rerun()
    if st.sidebar.button("🧪 Live 5-min try", use_container_width=True, disabled=mode == "demo"):
        st.session_state.mode = "demo"
        st.session_state.phase = "home"
        st.rerun()

    st.sidebar.markdown("---")
    st.session_state.name = (
        st.sidebar.text_input("Demo learner name", value=st.session_state.name).strip() or "Guest"
    )
    profile = st.session_state.profile
    if profile is None or profile.name != st.session_state.name:
        st.session_state.profile = load_or_create(st.session_state.name)
        profile = st.session_state.profile

    st.sidebar.markdown("### Learner snapshot")
    st.sidebar.metric("Confidence", f"{profile.mastery:.0%}")
    st.sidebar.metric("Sessions", profile.sessions_completed)
    st.sidebar.write(f"Best style now:\n\n**{_short_method(profile.preferred_method())}**")

    with st.sidebar.expander("Advanced", expanded=False):
        st.session_state.fast_demo = st.toggle(
            "Fast demo (template lesson)",
            value=st.session_state.fast_demo,
        )
        st.session_state.use_ollama = st.toggle(
            "Local AI lesson (Ollama)",
            value=st.session_state.use_ollama and not st.session_state.fast_demo,
        )
        if st.session_state.use_ollama:
            st.session_state.fast_demo = False
        st.session_state.model = st.text_input("Ollama model", value=st.session_state.model)
        st.session_state.n_diag = (
            3 if st.session_state.fast_demo else st.slider("Quiz length", 3, 6, st.session_state.n_diag)
        )
        if st.session_state.use_ollama and not is_reachable():
            st.warning("Ollama not running.")

    if st.sidebar.button("Reset learner profile"):
        keep = {
            "name": st.session_state.name,
            "use_ollama": st.session_state.use_ollama,
            "model": st.session_state.model,
            "n_diag": st.session_state.n_diag,
            "fast_demo": st.session_state.fast_demo,
            "mode": st.session_state.mode,
            "pitch_i": st.session_state.pitch_i,
        }
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        for k, v in keep.items():
            st.session_state[k] = v
        st.session_state.profile = load_or_create(st.session_state.name)
        st.session_state.phase = "home"
        st.rerun()


# ── Landing ──────────────────────────────────────────────────────────────────


def page_landing() -> None:
    _chip("Pitch-ready demo")
    st.title("PerLearn")
    st.subheader("Most edtech adapts *what* to learn. We adapt *how* to teach.")

    _card(
        "<strong>One sentence for the room</strong><br/>"
        "We measure which teaching style actually sticks for this learner — "
        "then we change it as they get stronger. Not a learning-styles quiz. Not a fixed path."
    )

    st.markdown("### How do you want to run this meeting?")
    c1, c2 = st.columns(2)
    with c1:
        _card(
            "<strong>🎯 Company pitch</strong><br/>"
            "7 slides · problem → proof → partnership ask<br/>"
            "<span style='opacity:0.8'>Best when you’re presenting to a table.</span>"
        )
        if st.button("Start company pitch →", type="primary", use_container_width=True):
            st.session_state.mode = "pitch"
            st.session_state.pitch_i = 0
            st.rerun()
    with c2:
        _card(
            "<strong>🧪 Live 5-minute try</strong><br/>"
            "They take a short quiz → get a lesson → see adaptation<br/>"
            "<span style='opacity:0.8'>Best when you want them to feel it.</span>"
        )
        if st.button("Start live demo →", use_container_width=True):
            st.session_state.mode = "demo"
            st.session_state.phase = "home"
            st.rerun()

    st.caption("Tip: open Company pitch first, then jump to Live try from the last slide.")


# ── Company pitch slides ─────────────────────────────────────────────────────


def page_pitch() -> None:
    i = st.session_state.pitch_i
    n = len(PITCH_SLIDES)
    st.progress((i + 1) / n, text=f"Pitch slide {i + 1} of {n}")
    slide = PITCH_SLIDES[i]
    {
        "hook": _pitch_hook,
        "problem": _pitch_problem,
        "insight": _pitch_insight,
        "loop": _pitch_loop,
        "evidence": _pitch_evidence,
        "who": _pitch_who,
        "ask": _pitch_ask,
    }[slide]()

    def go_back():
        if i == 0:
            st.session_state.mode = "landing"
        else:
            st.session_state.pitch_i = i - 1

    def go_next():
        if i >= n - 1:
            st.session_state.mode = "demo"
            st.session_state.phase = "home"
        else:
            st.session_state.pitch_i = i + 1

    next_label = "Try the live demo →" if i >= n - 1 else "Next →"
    _nav_row("← Back", next_label, go_back, go_next)


def _pitch_hook() -> None:
    _chip("Slide 1 · Hook")
    st.header("Two kids. Same app. Same wrong answers.")
    st.markdown(
        '<p class="quote">One needs a worked example. The other needs to struggle first. '
        "Your product teaches both the same way.</p>",
        unsafe_allow_html=True,
    )
    _card(
        "Adaptive learning today is great at picking the <strong>next topic</strong>.<br/>"
        "It almost never picks the <strong>teaching method</strong> — and never re-checks whether "
        "that method still works as the child grows."
    )
    st.info("That’s the gap PerLearn fills. A method layer on top of any content engine.")


def _pitch_problem() -> None:
    _chip("Slide 2 · The market problem")
    st.header("Why “personalised” still feels generic")

    a, b = st.columns(2)
    with a:
        _card(
            "<strong>What buyers are sold</strong><br/>"
            "• Adaptive difficulty<br/>"
            "• Next-item recommenders<br/>"
            "• Learning-style quizzes<br/>"
            "• More content, same pedagogy",
            "vs-bad",
        )
    with b:
        _card(
            "<strong>What classrooms still feel</strong><br/>"
            "• Kids plateau on the same concept<br/>"
            "• Tutors guess the explanation style<br/>"
            "• Practice scores look fine — tests don’t<br/>"
            "• One path for beginners and near-masters",
            "vs-bad",
        )

    st.warning(
        "Learning-styles labels are a neuromyth. We don’t ask “are you visual?” — "
        "we measure what produces delayed mastery."
    )


def _pitch_insight() -> None:
    _chip("Slide 3 · The insight")
    st.header("Don’t label how they learn. Measure what sticks.")
    st.markdown(
        '<p class="quote">Reward = can they do it <strong>later, without help</strong>? '
        "Not “did practice go well while scaffolding was on.”</p>",
        unsafe_allow_html=True,
    )
    _card(
        "<strong>Expertise reversal (research-backed)</strong><br/>"
        "Beginners often need worked examples. As mastery rises, problem-first and less guidance "
        "win. The best method <em>changes</em> — so the system must keep measuring."
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.success("Worked example")
    c2.success("Problem first")
    c3.success("Visual")
    c4.success("Story / analogy")


def _pitch_loop() -> None:
    _chip("Slide 4 · The product")
    st.header("One continuous loop")
    steps = [
        ("1. Find the gap", "Short adaptive quiz → weak skill + likely mix-up"),
        ("2. Choose how to teach", "Policy picks a style for this learner’s level"),
        ("3. Teach + practice", "Lesson matched to that style (math answers verified)"),
        ("4. No-help check", "Unassisted score updates which styles work"),
        ("5. Adapt", "Next session can switch method as they grow"),
    ]
    for title, body in steps:
        _card(f"<strong>{title}</strong><br/>{body}")


def _pitch_evidence() -> None:
    _chip("Slide 5 · Evidence")
    st.header("It finds better methods faster")
    m = _phase1()
    policies = m.get("policies", {})
    bandit = policies.get("bandit", {})
    fixed = policies.get("fixed", {})
    random = policies.get("random", {})

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            f'<p class="big-number">{bandit.get("mean_sessions", 5.3):.1f}</p>',
            unsafe_allow_html=True,
        )
        st.caption("Bandit · mean sessions to mastery")
    with c2:
        st.markdown(
            f'<p class="big-number">{fixed.get("mean_sessions", 6.0):.1f}</p>',
            unsafe_allow_html=True,
        )
        st.caption("Fixed method · mean sessions")
    with c3:
        st.markdown(
            f'<p class="big-number">{random.get("mean_sessions", 7.1):.1f}</p>',
            unsafe_allow_html=True,
        )
        st.caption("Random method · mean sessions")

    _card(
        f"Simulation on ASSISTments fraction parameters "
        f"({m.get('n_students', 100)} learners). "
        f"Bandit recovers the child’s true preferred method "
        f"<strong>{bandit.get('end_preference_recovery', 0.56):.0%}</strong> of the time by the end — "
        "fixed/random recovery ≈ 0%."
    )

    chart = ROOT / "outputs" / "phase1_time_to_mastery.png"
    if chart.exists():
        st.image(str(chart), caption="Time-to-mastery: bandit vs fixed vs random")
    st.caption("Also available: multi-week child trajectories (Maya / Sam / Jordan) on the demo site.")


def _pitch_who() -> None:
    _chip("Slide 6 · Who this is for")
    st.header("A method layer — not another content library")
    a, b = st.columns(2)
    with a:
        _card(
            "<strong>Perfect fit</strong><br/>"
            "• Tutoring platforms<br/>"
            "• Adaptive homework apps<br/>"
            "• School LMS / practice engines<br/>"
            "• AI tutors that only vary difficulty",
            "vs-good",
        )
    with b:
        _card(
            "<strong>What you keep</strong><br/>"
            "• Your curriculum & brand<br/>"
            "• Your item bank<br/>"
            "• Your UI<br/><br/>"
            "<strong>What we add</strong><br/>"
            "Which explanation style to use — and when to switch.",
            "vs-good",
        )
    st.info("First vertical: Year 5 fractions (UK). Loop is subject-agnostic once you have items + methods.")


def _pitch_ask() -> None:
    _chip("Slide 7 · The ask")
    st.header("What we’re looking for")
    _card(
        "<strong>Pilot partnership (90 days)</strong><br/>"
        "1 skill area · your learners · we run the method loop · you keep the outcome data.<br/><br/>"
        "<strong>Success looks like</strong><br/>"
        "Faster delayed mastery vs your current fixed pedagogy — and a clear “style switched” story "
        "teachers / parents can understand."
    )
    st.markdown("### In the room right now")
    st.markdown(
        """
1. Walk the **live 5-minute try** (next button)  
2. Show **before → after teaching style** on the final screen  
3. Leave them with: *we don’t guess learning styles — we measure what sticks*  
        """
    )
    st.success("Ready? Hit **Try the live demo →** and let them take the quiz themselves.")


# ── Live demo ────────────────────────────────────────────────────────────────


def phase_home() -> None:
    _chip("Live demo · ~5 minutes")
    st.header("Feel the loop")
    st.markdown(
        "You’ll answer a few questions. We’ll pick a teaching style, teach you, "
        "then check if it stuck — and show how preference updates."
    )
    _card(
        "<strong>What to watch for (tell the room)</strong><br/>"
        "1. We find a <em>weak spot</em>, not just a score<br/>"
        "2. We choose a <em>teaching style</em> on purpose<br/>"
        "3. The final no-help check updates what we think works for <em>you</em>"
    )

    profile = st.session_state.profile
    if profile.sessions_completed:
        st.success(
            f"Welcome back, {profile.name}. Best style so far: "
            f"**{_short_method(profile.preferred_method())}** "
            f"({profile.sessions_completed} session(s))."
        )

    if st.button("Start my session →", type="primary", use_container_width=True):
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
        sid = new_session_id()
        st.session_state.event_session_id = sid
        append_event(
            sid,
            "session_start",
            learner_id=profile.name,
            payload={"mode": "streamlit", "content_version": CONTENT_VERSION, "respondent": "human"},
        )
        if st.session_state.fast_demo:
            st.session_state.n_diag = 3
            st.session_state.use_ollama = False
        st.rerun()

    if st.button("← Back to company pitch"):
        st.session_state.mode = "pitch"
        st.session_state.pitch_i = len(PITCH_SLIDES) - 1
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
    _chip("Step 1 · Find the gap")
    st.header("Quick quiz")
    st.markdown(
        '<p class="quote">We’re not grading you for a report card — we’re finding where you’re stuck.</p>',
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
        if st.session_state.event_session_id:
            log_item_response(
                st.session_state.event_session_id,
                learner_id=st.session_state.profile.name,
                item_id=q.id,
                skill=q.skill,
                method=None,
                response=str(ans),
                correct=ok,
                outcome_type="diagnostic",
                content_version=CONTENT_VERSION,
                respondent="human",
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
    if st.session_state.event_session_id:
        append_event(
            st.session_state.event_session_id,
            "method_selected",
            learner_id=profile.name,
            payload={
                "method": METHODS[method_idx],
                "method_index": method_idx,
                "context": context.tolist(),
                "policy_probs": bandit.mean_rewards(context).tolist(),
                "content_version": CONTENT_VERSION,
            },
        )
    st.session_state.phase = "bridge"
    st.rerun()


def phase_bridge() -> None:
    _chip("Step 2 · Choose how to teach")
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

    _card(
        f"<strong>Weak spot:</strong> {skill}<br/>"
        f"<strong>Likely mix-up:</strong> {why}<br/><br/>"
        f"<strong>So today we’ll teach with:</strong> {_short_method(method)}"
    )
    st.markdown(
        '<p class="quote">Say this out loud: we didn’t only pick the next topic — '
        "we picked the <strong>teaching style</strong> for this learner right now.</p>",
        unsafe_allow_html=True,
    )

    if st.button("Show my lesson →", type="primary", use_container_width=True):
        st.session_state.phase = "lesson"
        st.rerun()


def phase_lesson() -> None:
    _chip("Step 3 · Teach")
    st.header("Your personalised lesson")
    diagnostic = st.session_state.diagnostic
    method = st.session_state.method

    st.info(
        f"Style: **{_short_method(method)}** · "
        f"Topic: **{SKILL_LABELS.get(diagnostic.weakest_skill, diagnostic.weakest_skill)}**"
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
    _chip("Step 4 · Practice")
    st.header("Practice with support")
    st.markdown(
        '<p class="quote">Practice helps learning — but we <strong>don’t</strong> train the policy on practice scores. '
        "That would reward easy help.</p>",
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
        if st.session_state.event_session_id:
            log_item_response(
                st.session_state.event_session_id,
                learner_id=st.session_state.profile.name,
                item_id=q.id,
                skill=q.skill,
                method=st.session_state.method,
                response=str(ans),
                correct=ok,
                outcome_type="practice",
                content_version=CONTENT_VERSION,
                respondent="human",
            )
        st.session_state.practice_index += 1
        st.session_state._current_practice_mcq = None
        st.rerun()


def phase_delayed() -> None:
    _chip("Step 5 · Check it stuck")
    st.header("No-help check")
    st.markdown(
        '<p class="quote">This score is the reward. Did today’s teaching style <strong>actually work</strong>?</p>',
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
        if st.session_state.event_session_id:
            log_item_response(
                st.session_state.event_session_id,
                learner_id=st.session_state.profile.name,
                item_id=q.id,
                skill=q.skill,
                method=st.session_state.method,
                response=str(ans),
                correct=ok,
                outcome_type="immediate_post",
                content_version=CONTENT_VERSION,
                respondent="human",
            )
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
    if st.session_state.event_session_id:
        append_event(
            st.session_state.event_session_id,
            "session_end",
            learner_id=profile.name,
            payload={
                "method": method,
                "delayed_score": delayed_score,
                "outcome_type": "immediate_post",
                "content_version": CONTENT_VERSION,
            },
        )
    st.session_state.profile = profile
    st.session_state._save_path = str(path)
    st.session_state._last_delayed = delayed_score
    st.session_state.phase = "done"
    st.rerun()


def phase_done() -> None:
    _chip("Step 6 · Adaptation")
    st.header("This is the product moment")

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

    _card(
        f"<strong>What just happened</strong><br/>"
        f"Taught with: <strong>{_short_method(used)}</strong><br/>"
        f"No-help score: <strong>{delayed:.0%}</strong> → updates the policy for this learner."
    )

    c1, c2 = st.columns(2)
    with c1:
        _card(f"<strong>Before this session</strong><br/>{_short_method(before)}", "vs-bad")
    with c2:
        _card(f"<strong>Best guess next time</strong><br/>{_short_method(after)}", "vs-good")

    if before != after:
        st.success(
            f"**Adaptation:** preference moved from {_short_method(before)} → {_short_method(after)}."
        )
    else:
        st.info(
            f"Still leaning **{_short_method(after)}**. Run another session — "
            "as mastery rises, the winning style can flip (expertise reversal)."
        )

    st.markdown("### Method fit at this level")
    for method, score in sorted(profile.method_scores().items(), key=lambda x: -x[1]):
        st.progress(min(max(score, 0.0), 1.0), text=f"{_short_method(method)} — {score:.2f}")

    st.markdown(
        '<p class="quote"><strong>Line for the room:</strong> “We don’t sell a learning-style label. '
        "We sell a loop that keeps finding the method that sticks.”</p>",
        unsafe_allow_html=True,
    )

    x, y = st.columns(2)
    with x:
        if st.button("Do another session", type="primary", use_container_width=True):
            st.session_state.phase = "home"
            st.session_state.lesson = None
            st.session_state.diagnostic = None
            st.rerun()
    with y:
        if st.button("Back to pitch ask", use_container_width=True):
            st.session_state.mode = "pitch"
            st.session_state.pitch_i = len(PITCH_SLIDES) - 1
            st.rerun()


def page_demo() -> None:
    _stepper()
    {
        "home": phase_home,
        "diagnostic": phase_diagnostic,
        "bridge": phase_bridge,
        "lesson": phase_lesson,
        "practice": phase_practice,
        "delayed": phase_delayed,
        "done": phase_done,
    }.get(st.session_state.phase, phase_home)()


def main() -> None:
    _init_state()
    if st.session_state.profile is None:
        st.session_state.profile = load_or_create(st.session_state.name)
    _sidebar()

    mode = st.session_state.mode
    if mode == "pitch":
        page_pitch()
    elif mode == "demo":
        page_demo()
    else:
        page_landing()


if __name__ == "__main__":
    main()
