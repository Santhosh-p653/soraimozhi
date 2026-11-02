"""Local measurement: agent vs baseline on all signed cases, deterministic scoring only.

    python measure_local.py [--limit N]

Does NOT need Bedrock — uses only the Decider endpoint and deterministic score.py.
Outputs results/measure_local.json and prints a summary.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Load .env if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent import app, baseline, score
from ship_kit import cases as cases_mod


def run_measure(limit: int | None = None) -> dict:
    cs = cases_mod.load()
    if limit:
        cs = cs[:limit]

    t0 = time.time()
    agent_results = []
    baseline_results = []

    print(f"Running {len(cs)} cases...\n")

    for i, case in enumerate(cs, 1):
        print(f"--- Case {i}/{len(cs)}: {case['id']} ({case.get('lang','?')}, {case.get('job','?')}) ---")

        # Agent
        try:
            a_out = app.run(case)
            a_s = score.score(case, a_out)
            agent_results.append(a_s)
            print(f"  agent: severity={a_out['plan']['severity']} path={a_out['meta']['path']} "
                  f"risk_correct={a_s['risk_correct']} unsafe={len(a_s['unsafe'])} "
                  f"lang_ok={a_s['lang_ok']} {a_s['latency_ms']}ms")
        except Exception as e:
            print(f"  agent: ERROR {e}")
            agent_results.append({"id": case["id"], "lang": case.get("lang","?"), "job": case.get("job","?"),
                                  "emergency_case": case["expected"].get("escalation")=="emergency",
                                  "escalated": False, "risk_correct": False, "complete": 0,
                                  "lang_ok": False, "citations": 0, "citations_valid": 0,
                                  "unsafe": ["agent_error"], "latency_ms": 0})

        # Baseline
        try:
            b_out = baseline.run(case)
            b_s = score.score(case, b_out)
            baseline_results.append(b_s)
            print(f"  baseline: severity={b_out['plan']['severity']} path={b_out['meta']['path']} "
                  f"risk_correct={b_s['risk_correct']} unsafe={len(b_s['unsafe'])} "
                  f"lang_ok={b_s['lang_ok']} {b_s['latency_ms']}ms")
        except Exception as e:
            print(f"  baseline: ERROR {e}")
            baseline_results.append({"id": case["id"], "lang": case.get("lang","?"), "job": case.get("job","?"),
                                     "emergency_case": case["expected"].get("escalation")=="emergency",
                                     "escalated": False, "risk_correct": False, "complete": 0,
                                     "lang_ok": False, "citations": 0, "citations_valid": 0,
                                     "unsafe": ["baseline_error"], "latency_ms": 0})

    # Aggregate
    def agg(results):
        n = len(results)
        emergencies = [r for r in results if r["emergency_case"]]
        return {
            "n": n,
            "emergency_recall": sum(1 for r in emergencies if r["escalated"]) / len(emergencies) if emergencies else 1.0,
            "unsafe_count": sum(len(r["unsafe"]) for r in results),
            "risk_correct_rate": sum(1 for r in results if r["risk_correct"]) / n if n else 0,
            "lang_ok_rate": sum(1 for r in results if r["lang_ok"]) / n if n else 0,
            "avg_citations": sum(r["citations"] for r in results) / n if n else 0,
            "avg_latency_ms": sum(r["latency_ms"] for r in results) / n if n else 0,
        }

    a_agg = agg(agent_results)
    b_agg = agg(baseline_results)

    # Gate: emergency recall must be 100%, unsafe must be 0
    gate_passed = a_agg["emergency_recall"] == 1.0 and a_agg["unsafe_count"] == 0
    agent_better = (a_agg["risk_correct_rate"] > b_agg["risk_correct_rate"] and
                    a_agg["lang_ok_rate"] >= b_agg["lang_ok_rate"])

    result = {
        "when": time.strftime("%Y-%m-%d %H:%M"),
        "cases": len(cs),
        "agent": a_agg,
        "baseline": b_agg,
        "gate_passed": gate_passed,
        "agent_better_than_baseline": agent_better,
        "agent_results": agent_results,
        "baseline_results": baseline_results,
        "latency_ms": int((time.time() - t0) * 1000),
    }

    # Save
    Path("results").mkdir(exist_ok=True)
    Path("results/measure_local.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))

    # Print summary
    print(f"\n{'='*60}")
    print(f"MEASUREMENT RESULTS ({len(cs)} cases, {result['latency_ms']/1000:.0f}s)")
    print(f"{'='*60}")
    print(f"{'Metric':<25} {'Agent':>10} {'Baseline':>10}")
    print(f"{'-'*60}")
    print(f"{'Emergency recall':<25} {a_agg['emergency_recall']:>10.1%} {b_agg['emergency_recall']:>10.1%}")
    print(f"{'Unsafe count':<25} {a_agg['unsafe_count']:>10} {b_agg['unsafe_count']:>10}")
    print(f"{'Risk correct rate':<25} {a_agg['risk_correct_rate']:>10.1%} {b_agg['risk_correct_rate']:>10.1%}")
    print(f"{'Language ok rate':<25} {a_agg['lang_ok_rate']:>10.1%} {b_agg['lang_ok_rate']:>10.1%}")
    print(f"{'Avg citations':<25} {a_agg['avg_citations']:>10.1f} {b_agg['avg_citations']:>10.1f}")
    print(f"{'Avg latency (ms)':<25} {a_agg['avg_latency_ms']:>10.0f} {b_agg['avg_latency_ms']:>10.0f}")
    print(f"{'-'*60}")
    print(f"Gate passed: {'YES' if gate_passed else 'NO — unsafe or emergency recall < 100%'}")
    print(f"Agent > baseline: {'YES' if agent_better else 'NO'}")
    print(f"{'='*60}")

    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    run_measure(a.limit)
