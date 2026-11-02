"""One agent, one prompt, same data: the baseline to beat.

The baseline has no Decider gate, no crisis hook, no critic, no templates.
It just parses the text and returns a generic response from guidance data.
It must lose on emergency recall and on the Evals judge.
"""
from __future__ import annotations

import time

from . import tools
from .plan import ReportPlan


def run(case: dict) -> dict:
    """Baseline: parse the report, return a generic response. No gates, no hooks, no critic."""
    t0 = time.time()
    text = case["text"]
    lang = case.get("lang") or tools.language_of(text)

    # Parse the report (same tool, but no urgency gate, no crisis check).
    parsed = tools.parse_report._tool_func(text) if hasattr(tools.parse_report, "_tool_func") else tools.parse_report(text)
    zone_id = parsed["zone_id"]
    zone_name = parsed["zone_name"]
    report_type = parsed["report_type"]

    # Generic response — no severity classification, no emergency escalation.
    guidance_items = tools.guidance()["items"]
    lines = "\n".join(g["text"][:80] for g in guidance_items[:3])

    if lang == "ta":
        summary = f"{zone_name} பகுதியில் தண்ணீர் பிரச்சினை. 1077 என்பதில் புகார் செய்யவும்."
        action = "1077 என்பதில் அழைக்கவும்."
        escalation = "அவசரம் என்றால் 1077."
    else:
        summary = f"Water issue in {zone_name}. Report to 1077."
        action = "Call 1077."
        escalation = "For emergencies, call 1077."

    ans = ReportPlan(
        language=lang,
        zone_id=zone_id,
        zone_name=zone_name,
        report_type=report_type,
        severity="moderate",  # baseline always says moderate — no urgency classification
        summary=summary,
        recommended_action=action,
        escalation=escalation,
        citations=["G-HELPLINE"],
    )

    meta = {"path": "baseline", "latency_ms": int((time.time() - t0) * 1000), "passes": 0}
    return {"plan": ans.model_dump(), "meta": meta}
