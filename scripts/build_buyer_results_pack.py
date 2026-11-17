#!/usr/bin/env python3
"""Build a meeting pack: agent cohort → cost proxy + case cards for buyers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pll.video_brief import (  # noqa: E402
    GENERIC_MINUTES,
    SPECIALISED_MINUTES,
    build_specialised_brief,
    render_brief_markdown,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        default=str(ROOT / "outputs" / "pilot_qwen" / "qwen_agent_summary.json"),
    )
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "outputs" / "buyer_demo"),
    )
    args = parser.parse_args()

    src = Path(args.source)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not src.exists():
        raise SystemExit(f"Missing {src}. Run scripts/run_qwen_agent_pilot.py first.")

    summary = json.loads(src.read_text(encoding="utf-8"))
    rows = summary.get("rows") or []
    match = summary.get("method_match_vs_mismatch") or {}

    # Cost model for the meeting: on failure, generic path re-renders a long video;
    # specialised path renders a short brief. Scale by cohort size.
    n = max(len(rows), 1)
    generic_total = n * GENERIC_MINUTES
    specialised_total = 0.0
    case_cards = []
    for r in rows:
        method = r.get("method") or "worked_example"
        minutes = float(SPECIALISED_MINUTES.get(method, 3.0))
        specialised_total += minutes
        case_cards.append(
            {
                "learner": r.get("learner"),
                "persona": r.get("persona"),
                "skill": r.get("skill"),
                "method": method,
                "style_bias": r.get("style_bias"),
                "match_bias": r.get("match_bias"),
                "delayed_score": r.get("delayed_score"),
                "immediate_score": r.get("immediate_score"),
                "estimated_minutes_specialised": minutes,
                "estimated_minutes_generic": GENERIC_MINUTES,
                "minutes_saved_proxy": round(GENERIC_MINUTES - minutes, 1),
            }
        )

    # Prefer interesting cards: one matched high delayed, one mismatch, one denominator/visual
    def pick_cases(cards: list[dict]) -> list[dict]:
        picked = []
        matched = [c for c in cards if c.get("match_bias") and (c.get("delayed_score") or 0) >= 0.5]
        mismatched = sorted(cards, key=lambda c: (c.get("delayed_score") or 0))
        if matched:
            picked.append(matched[0])
        if mismatched:
            picked.append(mismatched[0])
        visualish = [c for c in cards if c.get("method") == "visual" or c.get("persona") == "denominator_trap"]
        for c in visualish:
            if c not in picked:
                picked.append(c)
                break
        # Fill to 3
        for c in cards:
            if len(picked) >= 3:
                break
            if c not in picked:
                picked.append(c)
        return picked[:3]

    highlight = pick_cases(case_cards)
    # Attach full briefs for highlights
    briefs = []
    for c in highlight:
        brief = build_specialised_brief(
            skill=c["skill"] or "ordering_fractions",
            method=c["method"] or "worked_example",
            misconception_id="bigger_denominator_bigger",
            misconception_label="Thinks a bigger denominator means a bigger fraction",
        )
        briefs.append(
            {
                "case": c,
                "brief": brief.to_dict(),
                "brief_markdown": render_brief_markdown(brief),
            }
        )

    pack = {
        "note": (
            "Buyer meeting pack. Cost figures are duration proxies. "
            "Delayed scores are from Qwen llm_agent cohort — pipeline proof, not child RCT."
        ),
        "source": str(src),
        "n_learners": n,
        "method_match_vs_mismatch": match,
        "by_arm": summary.get("by_arm"),
        "cost_proxy": {
            "generic_minutes_if_full_topic_each": round(generic_total, 1),
            "specialised_minutes_sum": round(specialised_total, 1),
            "minutes_saved_proxy": round(generic_total - specialised_total, 1),
            "cost_ratio_specialised_over_generic": round(specialised_total / generic_total, 3),
            "generic_minutes_per_video": GENERIC_MINUTES,
        },
        "case_cards": case_cards,
        "highlight_briefs": briefs,
    }

    json_path = out_dir / "results.json"
    json_path.write_text(json.dumps(pack, indent=2), encoding="utf-8")

    md_lines = [
        "# Buyer results pack — AI video schools",
        "",
        pack["note"],
        "",
        "## Cost proxy (cohort)",
        "",
        f"- Learners: **{n}**",
        f"- If each got a long generic re-teach: **{pack['cost_proxy']['generic_minutes_if_full_topic_each']:.0f} min**",
        f"- If each got a specialised short brief: **{pack['cost_proxy']['specialised_minutes_sum']:.0f} min**",
        f"- Minutes saved (proxy): **{pack['cost_proxy']['minutes_saved_proxy']:.0f}**",
        f"- Cost ratio specialised/generic: **{pack['cost_proxy']['cost_ratio_specialised_over_generic']:.2f}**",
        "",
        "## Delayed mastery signal (agent cohort)",
        "",
        f"- Method matched persona bias: n={match.get('matched_n')}, "
        f"mean delayed={match.get('matched_mean_delayed')}",
        f"- Mismatched: n={match.get('mismatched_n')}, "
        f"mean delayed={match.get('mismatched_mean_delayed')}",
        "",
        "## Highlight cases",
        "",
    ]
    for b in briefs:
        c = b["case"]
        md_lines += [
            f"### {c.get('persona')} → {c.get('method')}",
            f"- Skill: {c.get('skill')}",
            f"- Delayed: {c.get('delayed_score')}",
            f"- Minutes: {c.get('estimated_minutes_specialised')} vs generic {GENERIC_MINUTES}",
            f"- Match bias: {c.get('match_bias')}",
            "",
        ]

    md_lines += [
        "## Meeting line",
        "",
        "*You generate AI videos. We make the next one personal — so you render less, and students learn more.*",
        "",
    ]
    md_path = out_dir / "RESULTS_NOTE.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    # Save first highlight brief as standalone for quick open
    if briefs:
        (out_dir / "sample_brief.md").write_text(briefs[0]["brief_markdown"], encoding="utf-8")

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(json.dumps(pack["cost_proxy"], indent=2))
    print(json.dumps(match, indent=2))


if __name__ == "__main__":
    main()
