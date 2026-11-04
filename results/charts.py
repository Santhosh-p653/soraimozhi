"""Generate benchmark charts from results/measure_local.json.

Produces two PNGs in the results/ directory:
  - chart_benchmarks.png  : Agent vs Baseline on key percentage metrics
  - chart_by_job.png      : Risk correctness (%) by report type

Run from the project root:
    python results/charts.py
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless backend, no display required
import matplotlib.pyplot as plt

# Palette matching the dashboard
AGENT_COLOR = "#2d7a4f"      # green-primary
BASELINE_COLOR = "#e67e22"  # orange / highlight for contrast

HERE = Path(__file__).resolve().parent
JSON_PATH = HERE / "measure_local.json"
OUT_BENCHMARKS = HERE / "chart_benchmarks.png"
OUT_BY_JOB = HERE / "chart_by_job.png"


def _fmt_pct(v):
    """Format a percentage value: whole numbers show no decimals, else 2 dp."""
    if float(v) == int(v):
        return f"{int(v)}%"
    return f"{v:.2f}%"


def _pct_of_true(results, key, total):
    """Percentage of cases where the boolean `key` is truthy."""
    if total == 0:
        return 0.0
    count = sum(1 for r in results if r.get(key))
    return count / total * 100


def _citation_faithfulness(results, total):
    """Percentage of cases where citations_valid == citations."""
    if total == 0:
        return 0.0
    count = sum(1 for r in results if r.get("citations_valid") == r.get("citations"))
    return count / total * 100


def _completeness(results, total):
    """Percentage of cases where complete == 1.0."""
    if total == 0:
        return 0.0
    count = sum(1 for r in results if r.get("complete") == 1.0)
    return count / total * 100


def _risk_correct_by_job(results):
    """Map job -> (correct_count, total_count) from a results list."""
    by_job = {}
    for r in results:
        job = r.get("job")
        if job is None:
            continue
        rec = by_job.setdefault(job, {"correct": 0, "total": 0})
        rec["total"] += 1
        if r.get("risk_correct"):
            rec["correct"] += 1
    return by_job


def chart_benchmarks(data):
    """Grouped horizontal bar chart: Agent vs Baseline on key percentage metrics."""
    agent = data["agent"]
    baseline = data["baseline"]
    agent_results = data["agent_results"]
    baseline_results = data["baseline_results"]
    total = data["cases"]

    metrics = [
        "Emergency recall",
        "Severity correct",
        "Citation faithfulness",
        "Plan completeness",
        "Must-include keywords",
        "Tamil language",
    ]

    agent_vals = [
        agent["emergency_recall"] * 100,
        agent["risk_correct_rate"] * 100,
        _citation_faithfulness(agent_results, total),
        _completeness(agent_results, total),
        _pct_of_true(agent_results, "must_include_ok", total),
        agent["lang_ok_rate"] * 100,
    ]
    baseline_vals = [
        baseline["emergency_recall"] * 100,
        baseline["risk_correct_rate"] * 100,
        _citation_faithfulness(baseline_results, total),
        _completeness(baseline_results, total),
        _pct_of_true(baseline_results, "must_include_ok", total),
        baseline["lang_ok_rate"] * 100,
    ]

    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    import numpy as np

    y = np.arange(len(metrics))
    height = 0.38

    ax.barh(y - height / 2, agent_vals, height, label="Agent", color=AGENT_COLOR)
    ax.barh(y + height / 2, baseline_vals, height, label="Baseline", color=BASELINE_COLOR)

    # Value labels at the end of each bar
    for yi, v in zip(y - height / 2, agent_vals):
        ax.text(v + 1.0, yi, _fmt_pct(v), va="center", ha="left", fontsize=9)
    for yi, v in zip(y + height / 2, baseline_vals):
        ax.text(v + 1.0, yi, _fmt_pct(v), va="center", ha="left", fontsize=9)

    ax.set_yticks(y)
    ax.set_yticklabels(metrics, fontsize=11)
    ax.invert_yaxis()  # first metric at the top
    ax.set_xlabel("Percentage (%)", fontsize=11)
    ax.set_title("SoraiMozhi: Agent vs Baseline (32 cases)", fontsize=13)
    ax.set_xlim(0, 115)
    ax.grid(axis="x", linestyle="--", alpha=0.4)
    ax.grid(axis="y", visible=False)
    ax.legend(fontsize=11, loc="lower right")

    # Unsafe-plans annotation at the bottom of the chart
    agent_unsafe = data["agent"].get("unsafe_count", 0)
    baseline_unsafe = data["baseline"].get("unsafe_count", 0)
    ax.annotate(
        f"Unsafe plans  —  Agent: {agent_unsafe}  |  Baseline: {baseline_unsafe}",
        xy=(0.5, -0.14),
        xycoords="axes fraction",
        ha="center",
        va="top",
        fontsize=10,
        color="#333333",
        bbox=dict(boxstyle="round,pad=0.4", fc="#f4f4f4", ec="#cccccc"),
    )

    plt.tight_layout()
    fig.savefig(OUT_BENCHMARKS, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Wrote {OUT_BENCHMARKS}")


def chart_by_job(data):
    """Grouped vertical bar chart: risk_correct rate (%) by job type, agent vs baseline."""
    agent_results = data["agent_results"]
    baseline_results = data["baseline_results"]

    job_order = ["canal", "rescue", "waterlog", "structural", "drain", "waste"]
    job_labels = ["Canal", "Rescue", "Waterlog", "Structural", "Drain", "Waste"]

    agent_by_job = _risk_correct_by_job(agent_results)
    baseline_by_job = _risk_correct_by_job(baseline_results)

    def rate(by_job, job):
        rec = by_job.get(job, {"correct": 0, "total": 0})
        if rec["total"] == 0:
            return 0.0
        return rec["correct"] / rec["total"] * 100

    agent_vals = [rate(agent_by_job, j) for j in job_order]
    baseline_vals = [rate(baseline_by_job, j) for j in job_order]

    import numpy as np

    fig, ax = plt.subplots(figsize=(10, 5), dpi=150)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    x = np.arange(len(job_labels))
    width = 0.38

    bars_a = ax.bar(x - width / 2, agent_vals, width, label="Agent", color=AGENT_COLOR)
    bars_b = ax.bar(x + width / 2, baseline_vals, width, label="Baseline", color=BASELINE_COLOR)

    # Value labels on top of each bar
    for bar, v in zip(bars_a, agent_vals):
        ax.text(bar.get_x() + bar.get_width() / 2, v + 1.5, _fmt_pct(v),
                ha="center", va="bottom", fontsize=9)
    for bar, v in zip(bars_b, baseline_vals):
        ax.text(bar.get_x() + bar.get_width() / 2, v + 1.5, _fmt_pct(v),
                ha="center", va="bottom", fontsize=9)

    ax.set_xticks(x)
    ax.set_xticklabels(job_labels, fontsize=11)
    ax.set_ylabel("Correct (%)", fontsize=11)
    ax.set_title("Severity Accuracy by Report Type (Agent vs Baseline)", fontsize=13)
    ax.set_ylim(0, 118)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.grid(axis="x", visible=False)
    ax.legend(fontsize=11, loc="upper right")

    plt.tight_layout()
    fig.savefig(OUT_BY_JOB, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Wrote {OUT_BY_JOB}")


def main():
    import json

    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)

    chart_benchmarks(data)
    chart_by_job(data)
    print("Done.")


if __name__ == "__main__":
    main()
