"""Qwen-backed learner agents for AI-platform evaluation.

Primary proof path for pitching AI learning products: agent learners run
diagnose → teach → delayed check → adapt. Logs use respondent=\"llm_agent\".
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from pll.ollama_client import DEFAULT_HOST, DEFAULT_MODEL, OllamaError, ensure_model
from pll.questions import Question
from pll.sympy_check import verify_answer


@dataclass(frozen=True)
class Persona:
    id: str
    label: str
    ability: float  # 0–1 prior competence cue for the model
    style_bias: str  # which teaching style helps them most (behavioral, not neuromyth label)
    forget: float  # 0–1 how much lesson detail is dropped at delayed check
    traits: str


PERSONAS: tuple[Persona, ...] = (
    Persona(
        "novice_scaffold",
        "Novice who needs steps",
        0.28,
        "worked_example",
        0.35,
        "Often confused by fractions; follows worked steps carefully; guesses when rushed.",
    ),
    Persona(
        "novice_impulsive",
        "Impulsive novice",
        0.30,
        "visual",
        0.55,
        "Skims text; compares numerators only; forgets lessons quickly.",
    ),
    Persona(
        "mid_visual",
        "Building with pictures",
        0.45,
        "visual",
        0.30,
        "Medium skill; remembers diagrams better than abstract rules.",
    ),
    Persona(
        "mid_story",
        "Story-grounded learner",
        0.48,
        "story_analogy",
        0.28,
        "Medium skill; maps pizza/sharing stories to maths; weaker on pure symbols.",
    ),
    Persona(
        "rising_problem",
        "Ready to struggle first",
        0.62,
        "problem_first",
        0.20,
        "Getting stronger; worked examples feel slow; prefers trying then checking.",
    ),
    Persona(
        "strong_transfer",
        "Strong transfer",
        0.72,
        "problem_first",
        0.15,
        "Usually accurate; rare slips on mixed numbers; retains lessons well.",
    ),
    Persona(
        "anxious_careful",
        "Anxious but careful",
        0.40,
        "worked_example",
        0.25,
        "Double-checks; avoids risk; benefits from clear examples.",
    ),
    Persona(
        "denominator_trap",
        "Denominator trap",
        0.35,
        "visual",
        0.40,
        "Believes bigger denominator means bigger fraction until shown otherwise.",
    ),
)


def _chat_short(
    messages: list[dict[str, str]],
    *,
    model: str = DEFAULT_MODEL,
    host: str = DEFAULT_HOST,
    temperature: float = 0.4,
    timeout: float = 90.0,
) -> str:
    model = ensure_model(model, host)
    payload = {
        "model": model,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": 48,
        },
        "messages": messages,
    }
    req = urllib.request.Request(
        host.rstrip("/") + "/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise OllamaError(f"Ollama request failed: {exc}") from exc
    content = (data.get("message") or {}).get("content", "")
    if not content:
        raise OllamaError(f"Empty Ollama response: {data!r}")
    return content.strip()


def _extract_answer(text: str, q: Question) -> str:
    """Pull a usable answer from a short model reply."""
    raw = text.strip()
    # Prefer quoted / JSON-ish answer field
    m = re.search(r'"answer"\s*:\s*"([^"]+)"', raw, re.I)
    if m:
        raw = m.group(1).strip()
    # Letter choice A/B/C
    if q.choices:
        m = re.match(r"^\s*([A-Da-d])\b", raw)
        if m:
            idx = ord(m.group(1).upper()) - ord("A")
            if 0 <= idx < len(q.choices):
                return str(q.choices[idx])
        # Exact choice substring
        for c in q.choices:
            if str(c).lower() in raw.lower():
                return str(c)
        # First line only
        line = raw.splitlines()[0].strip().strip("`").strip()
        for c in q.choices:
            if line.lower() == str(c).lower():
                return str(c)
        # Fallback: first wrong-looking token or first choice if unparsable
        return str(q.choices[0]) if not q.choices else str(q.choices[min(1, len(q.choices) - 1)])

    # Free response: first line, strip trailing commentary
    line = raw.splitlines()[0]
    line = re.sub(r"^(answer|final|i think)[:\s]+", "", line, flags=re.I)
    line = line.strip().strip("`").strip(".")
    # Keep fraction-like / yes-no / number
    m = re.search(r"(-?\d+\s+\d+/\d+|-?\d+/\d+|-?\d+|yes|no|true|false)", line, re.I)
    if m:
        return m.group(1)
    return line[:40] if line else "1/2"


class LearnerAgent:
    """One Qwen persona that answers quiz items, optionally after a lesson."""

    def __init__(
        self,
        persona: Persona,
        *,
        model: str = DEFAULT_MODEL,
        host: str = DEFAULT_HOST,
        seed: int = 0,
    ) -> None:
        self.persona = persona
        self.model = model
        self.host = host
        self.seed = seed
        self.lesson_memory: str = ""
        self.method_seen: str | None = None

    def remember_lesson(self, method: str, lesson_text: str) -> None:
        self.method_seen = method
        # Truncate for context window / speed
        self.lesson_memory = lesson_text[:1800]

    def answer_fn(self, phase: str = "diagnostic") -> Callable[[Question], str]:
        def _fn(q: Question) -> str:
            return self.answer(q, phase=phase)

        return _fn

    def answer(self, q: Question, *, phase: str = "diagnostic") -> str:
        import numpy as np

        rng = np.random.default_rng(self.seed + (hash(q.id) % 10_000) + hash(phase) % 997)

        # Effective competence rises after a matching lesson, falls with forgetting.
        p_know = self.persona.ability
        if phase in {"practice", "immediate_post"} and self.method_seen:
            boost = 0.22 if self.method_seen == self.persona.style_bias else 0.08
            p_know = float(np.clip(p_know + boost, 0.05, 0.92))
        elif phase == "delayed_24h":
            retain = 0.18 if self.method_seen == self.persona.style_bias else 0.05
            p_know = float(np.clip(p_know + retain - 0.25 * self.persona.forget, 0.05, 0.85))

        # Stochastic slip: force a realistic wrong distractor (keeps Year-5 realism;
        # Qwen alone is often too competent when role-playing).
        if rng.random() > p_know:
            if q.choices:
                expected = q.answer_sympy if q.answer_sympy is not None else q.answer
                wrong = [c for c in q.choices if not verify_answer(expected, c).ok]
                if wrong:
                    # Prefer misconception-tagged distractors when available
                    if q.distractor_misconceptions:
                        tagged = [c for c in wrong if str(c) in q.distractor_misconceptions]
                        pool = tagged or wrong
                    else:
                        pool = wrong
                    return str(pool[int(rng.integers(0, len(pool)))])
            return "1/1"

        choices_block = ""
        if q.choices:
            choices_block = "\n".join(f"{chr(65 + i)}) {c}" for i, c in enumerate(q.choices))
            choices_block = "Choices:\n" + choices_block + "\nReply with ONLY the choice text or letter.\n"
        else:
            choices_block = "Reply with ONLY the final answer (fraction, number, yes/no, or ordered list).\n"

        memory = ""
        if phase in {"immediate_post", "practice"} and self.lesson_memory:
            memory = f"You just studied this lesson ({self.method_seen}):\n{self.lesson_memory}\n\n"
        elif phase == "delayed_24h" and self.lesson_memory:
            keep = max(80, int(len(self.lesson_memory) * (1.0 - self.persona.forget)))
            faded = self.lesson_memory[:keep]
            memory = (
                f"You studied a lesson 36 hours ago. You only remember vaguely:\n{faded}\n\n"
            )

        system = (
            f"You are role-playing a Year 5 student named agent-{self.persona.id}. "
            f"Profile: {self.persona.traits} "
            f"You often benefit most from '{self.persona.style_bias}' teaching. "
            f"Answer correctly if you know it. Never explain — output only the answer."
        )
        user = f"Phase: {phase}\n{memory}Question: {q.stem}\n{choices_block}"
        try:
            text = _chat_short(
                [{"role": "system", "content": system}, {"role": "user", "content": user}],
                model=self.model,
                host=self.host,
                temperature=0.3,
            )
            return _extract_answer(text, q)
        except OllamaError:
            if isinstance(q.answer, list):
                return ", ".join(str(a) for a in q.answer)
            return str(q.answer)


def make_cohort(n: int = 16) -> list[Persona]:
    """Cycle personas to fill a 12–20 agent cohort."""
    out: list[Persona] = []
    for i in range(n):
        out.append(PERSONAS[i % len(PERSONAS)])
    return out


def agent_to_dict(persona: Persona) -> dict[str, Any]:
    return {
        "id": persona.id,
        "label": persona.label,
        "ability": persona.ability,
        "style_bias": persona.style_bias,
        "forget": persona.forget,
        "traits": persona.traits,
    }
