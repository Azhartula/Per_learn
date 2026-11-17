"""Charts for the Phase 1 pitch demo."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from pll.simulator import SimResult


POLICY_LABELS = {
    "fixed": "Fixed method\n(worked example)",
    "random": "Random method",
    "bandit": "Contextual bandit\n(our approach)",
}

COLORS = {
    "fixed": "#6B7280",
    "random": "#D97706",
    "bandit": "#0F766E",
}


def plot_time_to_mastery(
    results: dict[str, SimResult],
    out_path: str | Path,
    skill: str,
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    order = ["fixed", "random", "bandit"]
    means = [float(np.mean(results[k].sessions_to_mastery)) for k in order]
    stds = [float(np.std(results[k].sessions_to_mastery)) for k in order]
    # Share of teaching decisions that matched the oracle method for that mastery level.
    recovery = [100.0 * float(np.mean(results[k].choice_match_rate)) for k in order]

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.4), constrained_layout=True)

    ax = axes[0]
    x = np.arange(len(order))
    bars = ax.bar(
        x,
        means,
        yerr=stds,
        color=[COLORS[k] for k in order],
        capsize=4,
        width=0.65,
        error_kw={"elinewidth": 1.2},
    )
    ax.set_xticks(x)
    ax.set_xticklabels([POLICY_LABELS[k] for k in order], fontsize=9)
    ax.set_ylabel("Sessions to mastery (lower is better)")
    ax.set_title("Time to mastery")
    ax.bar_label(bars, fmt="%.1f", padding=3, fontsize=9)
    ax.set_ylim(0, max(means) * 1.35)

    ax = axes[1]
    bars = ax.bar(
        x,
        recovery,
        color=[COLORS[k] for k in order],
        width=0.65,
    )
    ax.set_xticks(x)
    ax.set_xticklabels([POLICY_LABELS[k] for k in order], fontsize=9)
    ax.set_ylabel("% of lessons using the best method\nfor the child's current level")
    ax.set_title("Best-method match rate")
    ax.bar_label(bars, fmt="%.0f%%", padding=3, fontsize=9)
    ax.set_ylim(0, 110)

    fig.suptitle(
        f"Personalized Learning Loop — Phase 1 simulation\nSkill: {skill}",
        fontsize=12,
    )
    fig.savefig(out_path, dpi=160)
    plt.close(fig)
    return out_path


def summarize(results: dict[str, SimResult]) -> str:
    lines = ["Policy comparison"]
    for name in ("fixed", "random", "bandit"):
        r = results[name]
        lines.append(
            f"  {name:7s}  mean sessions={np.mean(r.sessions_to_mastery):5.2f}  "
            f"median={np.median(r.sessions_to_mastery):4.1f}  "
            f"match={100*np.mean(r.choice_match_rate):5.1f}%  "
            f"mean reward={np.mean(r.mean_reward):.3f}"
        )
    return "\n".join(lines)
