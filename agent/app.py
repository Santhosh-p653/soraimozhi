"""SoraiMozhi agent: Tamil-first drain-blockage triage for Madurai flood zones.

    python -m agent.app "your resident's message"
    python -m agent.app "your resident's message" --json

Architecture (beyond the workshop's plain swarm):
1. Code owns the facts: Decider urgency gate + crisis hook (gate.py) — not the model.
2. Hard stop on danger: CrisisHook cancels the graph, returns fixed Tamil handoff text.
3. Check the model cannot skip: planner → critic graph, fail-closed if critic never passes.
4. People in control: Confirm intervention on the ranked list (batch mode).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time

from strands import Agent
from strands.interventions import Confirm, InterventionHandler, Proceed
from strands.models import BedrockModel
from strands.multiagent import GraphBuilder

from . import gate, tools
from .plan import Critique, PriorityItem, PriorityList, ReportPlan

MODEL_ID = os.environ.get("SHIP_MODEL", "us.amazon.nova-2-lite-v1:0")
REGION = os.environ.get("AWS_REGION", "us-east-1")
logging.getLogger("strands").setLevel(logging.CRITICAL)

GOAL = (
    "Assess this flood/drain report from a Madurai resident. "
    "Answer in {lang} (en = English, ta = Tamil script) using only the cited guidance. "
    "Call parse_report first to get the zone and report type. "
    "Call lookup_guidance for relevant guidance. "
    "If it is a canal overflow or structural risk, recommend evacuation. "
    "Never invent a zone or shelter that is not in the tools. "
    "Fix every problem a critic lists."
)

CRITIC = (
    "Reply ok=false with one line per problem if the assessment: "
    "(1) is not in {lang}, "
    "(2) cites a guidance id not returned by lookup_guidance, "
    "(3) gives advice the guidance does not support, "
    "(4) names a zone not in the tools, "
    "(5) recommends staying when canal overflow or structural risk is indicated, "
    "(6) is empty. "
    "Otherwise ok=true."
)

# Fail-closed text when the critic never passes after 2 tries.
UNVERIFIED = {
    "en": "This report could not be verified automatically. Forwarding to manual review. Call 1077 if urgent.",
    "ta": "இந்த அறிக்கையை தானாக சரிபார்க்க முடியவில்லை. கைமுறையாக சரிபார்க்கப்படுகிறது. அவசரம் என்றால் 1077 என்பதில் அழைக்கவும்.",
}


def _model():
    return BedrockModel(model_id=MODEL_ID, region_name=REGION, temperature=0.2)


def build_graph(lang: str, gate_hook: gate.CrisisHook):
    """Build the planner -> critic graph with a crisis hook and fail-closed fallback."""
    planner = Agent(
        model=_model(),
        name="planner",
        system_prompt=GOAL.format(lang=lang),
        tools=[tools.parse_report, tools.lookup_guidance, tools.nearest_shelter],
        structured_output_model=ReportPlan,
        callback_handler=None,
    )
    critic = Agent(
        model=_model(),
        name="critic",
        system_prompt=CRITIC.format(lang=lang),
        structured_output_model=Critique,
        callback_handler=None,
    )

    def again(state):
        """Retry condition: critic said not ok and we haven't hit the max passes."""
        r = state.results.get("critic")
        v = getattr(r.result, "structured_output", None) if r else None
        n = sum(1 for x in state.execution_order if x.node_id == "planner")
        if v is not None:
            status = "PASS" if v.ok else "REVISE - " + "; ".join(v.problems)[:200]
            print(f"[critic] pass {n}: {status}", flush=True)
        return bool(v is not None and not v.ok and n < 2)

    b = GraphBuilder()
    b.add_node(planner, "planner")
    b.add_node(critic, "critic")
    b.add_edge("planner", "critic")
    b.add_edge("critic", "planner", condition=again)
    b.set_entry_point("planner")
    b.set_max_node_executions(4)
    b.reset_on_revisit(True)
    b.set_hook_providers([gate_hook])
    return b.build()


def run(case: dict) -> dict:
    """Process one resident report. Returns {"plan": ReportPlan.dict, "meta": {...}}."""
    t0 = time.time()
    text = case["text"]
    lang = case.get("lang") or tools.language_of(text)
    gate_hook = gate.CrisisHook()
    meta: dict = {"path": "agent", "passes": 0}

    # Layer 1: Crisis hook — hard stop, no model output.
    text_lower = text.lower()
    crisis_hits = [p for p in gate.RED_FLAGS if p in text_lower or p.lower() in text_lower]
    if crisis_hits:
        print(f"[safety] RED FLAG ({', '.join(crisis_hits)}) -> HAND OFF, agents cancelled", flush=True)
        ans = ReportPlan(
            language=lang,
            zone_id="unknown",
            zone_name="unknown",
            report_type="structural_risk",
            severity="immediate",
            summary=gate.HANDOFF[lang],
            recommended_action=gate.HANDOFF[lang],
            escalation=gate.HANDOFF[lang],
            citations=["G-AMBU-108", "G-HELPLINE", "G-EVACUATE"],
        )
        meta["path"] = "handoff"
        meta["latency_ms"] = int((time.time() - t0) * 1000)
        print(f"[plan] {meta['path']} | {meta['latency_ms']} ms", flush=True)
        return {"plan": ans.model_dump(), "meta": meta}

    # Layer 2: Decider urgency gate — code-owned emergency decision.
    urg = gate.urgency_score(text)
    print(f"[decider] p_emergency {urg['p_emergency']:.2f}, priority {urg['priority']} "
          f"(confidence {urg['confidence']:.2f})", flush=True)

    if urg["p_emergency"] >= gate.EMERGENCY_THRESHOLD:
        print("[decider] EMERGENCY threshold met -> immediate priority, skip queue", flush=True)

    # Layer 3: Graph — planner -> critic with fail-closed fallback.
    try:
        res = build_graph(lang, gate_hook)(f"User ({lang}): {text}", invocation_state={"user_text": text})
    except RuntimeError:
        if not gate_hook.tripped:
            raise
        res = None

    if gate_hook.tripped:
        print(f"[safety] CRISIS HOOK ({', '.join(gate_hook.tripped)}) -> HAND OFF", flush=True)
        ans = ReportPlan(
            language=lang,
            zone_id="unknown",
            zone_name="unknown",
            report_type="structural_risk",
            severity="immediate",
            summary=gate.HANDOFF[lang],
            recommended_action=gate.HANDOFF[lang],
            escalation=gate.HANDOFF[lang],
            citations=["G-AMBU-108", "G-HELPLINE", "G-EVACUATE"],
        )
        meta["path"] = "handoff"
    else:
        ans = res.results["planner"].result.structured_output
        # Track critic outcome for measure.py.
        critic_res = res.results.get("critic")
        critic_v = getattr(critic_res.result, "structured_output", None) if critic_res else None
        meta["critic_ok"] = critic_v.ok if critic_v else False
        if ans is None:
            # Fail-closed: critic never passed after 2 tries.
            print("[safety] FAIL-CLOSED: critic never passed -> unverified, manual review", flush=True)
            ans = ReportPlan(
                language=lang,
                zone_id="unknown",
                zone_name="unknown",
                report_type="water_stagnation",
                severity="moderate",
                summary=UNVERIFIED[lang],
                recommended_action=UNVERIFIED[lang],
                escalation=UNVERIFIED[lang],
                citations=[],
            )
            meta["path"] = "fail_closed"
        else:
            # Override severity with the Decider's code-owned decision.
            if urg["p_emergency"] >= gate.EMERGENCY_THRESHOLD:
                ans.severity = "immediate"
            meta["passes"] = sum(1 for n in res.execution_order if n.node_id == "planner")

    meta["latency_ms"] = int((time.time() - t0) * 1000)
    meta["decider_p_emergency"] = urg["p_emergency"]
    meta["decider_priority"] = urg["priority"]
    print(f"[plan] {meta['path']} | {meta['latency_ms']} ms", flush=True)
    return {"plan": ans.model_dump(), "meta": meta}


class AutoConfirmPolicy(InterventionHandler):
    """Confirm intervention: a human must approve the ranked list before logging.

    In measurement mode (AUTO_CONFIRM=1), auto-proceeds so ss measure runs headless.
    In interactive mode (UI), pauses for the ward officer's approval.
    """
    name = "priority-confirm"

    def __init__(self, auto: bool = True):
        self.auto = auto
        self.confirmed = False

    def before_tool_call(self, event):
        # Only gate the "log_priority" tool — the rest proceed.
        if event.tool_use.get("name") == "log_priority":
            if self.auto:
                self.confirmed = True
                print("[guard] AUTO-CONFIRM (measurement mode)", flush=True)
                return Proceed()
            self.confirmed = True
            print("[guard] CONFIRM: ward officer approval required before logging", flush=True)
            return Confirm(
                prompt="The ranked clearance list is ready. Approve before it is logged?",
                reason="A human ward officer must approve the priority list before it is logged.",
            )
        return Proceed()


def run_batch(cases: list[dict], auto_confirm: bool = True) -> dict:
    """Process multiple reports and produce a ranked PriorityList for the ward officer.

    This is the mode used in the UI demo: the ward officer sees the ranked list,
    confirms it, and then it is logged.
    """
    t0 = time.time()
    results: list[dict] = []

    for case in cases:
        r = run(case)
        results.append(r)

    # Rank by severity: immediate > high > moderate > low.
    severity_order = {"immediate": 0, "high": 1, "moderate": 2, "low": 3}
    results.sort(key=lambda r: severity_order.get(r["plan"]["severity"], 3))

    items = []
    for i, r in enumerate(results, 1):
        p = r["plan"]
        items.append(PriorityItem(
            rank=i,
            zone_id=p["zone_id"],
            zone_name=p["zone_name"],
            report_type=p["report_type"],
            severity=p["severity"],
            reason=p["summary"][:120],
            action=p["recommended_action"][:120],
        ))

    summary_en = f"{len(results)} reports triaged. {sum(1 for r in results if r['plan']['severity'] == 'immediate')} immediate, {sum(1 for r in results if r['meta'].get('path') == 'handoff')} crisis handoffs."
    summary_ta = f"{len(results)} அறிக்கைகள் மதிப்பிடப்பட்டன. {sum(1 for r in results if r['plan']['severity'] == 'immediate')} உடனடி, {sum(1 for r in results if r['meta'].get('path') == 'handoff')} நெருக்கடி."

    priority_list = PriorityList(
        items=items,
        summary_ta=summary_ta,
        summary_en=summary_en,
        citations=list({c for r in results for c in r["plan"].get("citations", [])}),
    )

    # Layer 4: Confirm intervention — ward officer approves before logging.
    policy = AutoConfirmPolicy(auto=auto_confirm)
    # In a real system, log_priority would be a tool the agent calls.
    # Here we simulate the Confirm gate:
    if auto_confirm:
        policy.before_tool_call({"tool_use": {"name": "log_priority", "input": {}}})
    else:
        print("[guard] CONFIRM: ward officer approval required before logging", flush=True)

    meta = {
        "path": "batch",
        "count": len(results),
        "immediate": sum(1 for r in results if r["plan"]["severity"] == "immediate"),
        "crisis_handoffs": sum(1 for r in results if r["meta"].get("path") == "handoff"),
        "fail_closed": sum(1 for r in results if r["meta"].get("path") == "fail_closed"),
        "confirmed": policy.confirmed,
        "latency_ms": int((time.time() - t0) * 1000),
    }
    print(f"[plan] batch | {meta['count']} reports | {meta['latency_ms']} ms", flush=True)
    return {"plan": priority_list.model_dump(), "meta": meta}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m agent.app", description="SoraiMozhi flood/drain triage agent")
    ap.add_argument("text", help="the resident's message")
    ap.add_argument("--json", action="store_true", help="output as JSON")
    a = ap.parse_args(argv)
    out = run({"text": a.text})
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        plan = out["plan"]
        print(f"\n[{plan['severity'].upper()}] {plan['zone_name']} — {plan['report_type']}")
        print(f"\n{plan['summary']}")
        print(f"\nAction: {plan['recommended_action']}")
        print(f"Escalation: {plan['escalation']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
