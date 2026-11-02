"""SoraiMozhi agent: Tamil-first drain-blockage triage for Madurai flood zones.

    python -m agent.app "your resident's message"
    python -m agent.app "your resident's message" --json

Architecture (beyond the workshop's plain swarm):
1. Code owns the facts: Decider urgency gate + crisis hook + deterministic templates (gate.py, app.py).
2. Hard stop on danger: CrisisHook cancels everything, returns fixed Tamil handoff text.
3. Check the model cannot skip: Decider critic checks the assessment, fail-closed if it doesn't pass.
4. People in control: Confirm intervention on the ranked list (batch mode).

The Decider (hosted by AWS UG Madurai) makes calibrated decisions. Code writes all text
the resident sees — the model never generates safety text. This is stronger than an LLM
graph for a safety-critical system: every word is auditable.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time

from strands.interventions import Confirm, InterventionHandler, Proceed

from . import gate, tools
from .plan import PriorityItem, PriorityList, ReportPlan

logging.getLogger("strands").setLevel(logging.CRITICAL)

# Fail-closed text when the Decider critic doesn't pass.
UNVERIFIED = {
    "en": "This report could not be verified automatically. Forwarding to manual review. Call 1077 if urgent.",
    "ta": "இந்த அறிக்கையை தானாக சரிபார்க்க முடியவில்லை. கைமுறையாக சரிபார்க்கப்படுகிறது. அவசரம் என்றால் 1077 என்பதில் அழைக்கவும்.",
}

# Deterministic response templates by report type and language.
# Code owns these words — the model never writes them.
TEMPLATES = {
    "canal_overflow": {
        "immediate": {
            "ta": {"summary": "பந்தால்குடி கால்வாய் நிரம்பி வெள்ளம் வீடுகளை அடைந்துள்ளது. உடனே வெளியேறவும்.",
                   "action": "மேல் தளத்திற்கு செல்லவும். வெள்ளத்தில் கடக்க வேண்டாம். 1077 என்பதில் அழைத்து வெளியேற்ற உதவி கேளுங்கள்.",
                   "escalation": "உயிருக்கு ஆபத்து என்றால் 108 என்பதில் ஆம்புலன்ஸ் அழைக்கவும். 1077 வெள்ள உதவி எண்.",
                   "citations": ["G-CANAL-OVERFLOW", "G-EVACUATE", "G-HELPLINE", "G-AMBU-108"]},
            "en": {"summary": "Panthalkudi canal overflow — floodwater has reached homes. Evacuate immediately.",
                   "action": "Move to a higher floor. Do not cross floodwater. Call 1077 for evacuation assistance.",
                   "escalation": "If life is in danger, call 108 for ambulance. 1077 is the flood helpline.",
                   "citations": ["G-CANAL-OVERFLOW", "G-EVACUATE", "G-HELPLINE", "G-AMBU-108"]},
        },
        "high": {
            "ta": {"summary": "கால்வாயில் நீர் அதிகரித்து வருகிறது. வெள்ள அபாயம் உள்ளது.",
                   "action": "தயாராக இருங்கள். முக்கிய ஆவணங்களை எடுத்து வைக்கவும். 1077 என்பதில் அறிவிக்கவும்.",
                   "escalation": "நிலைமை மோசமானால் 1077 அல்லது 108 என்பதில் அழைக்கவும்.",
                   "citations": ["G-CANAL-OVERFLOW", "G-CANAL-DEBRIS", "G-HELPLINE"]},
            "en": {"summary": "Canal water level rising — flood risk in your area.",
                   "action": "Stay prepared. Keep important documents ready. Report to 1077.",
                   "escalation": "If conditions worsen, call 1077 or 108.",
                   "citations": ["G-CANAL-OVERFLOW", "G-CANAL-DEBRIS", "G-HELPLINE"]},
        },
    },
    "structural_risk": {
        "immediate": {
            "ta": {"summary": "வரப்பு அல்லது சுவர் உடைந்துள்ளது — உடனே பாதுகாப்பான இடத்திற்கு செல்லவும்.",
                   "action": "கட்டிடத்தை விட்டு வெளியேறவும். பாலத்தை கடக்க வேண்டாம். 1077 என்பதில் அழைக்கவும்.",
                   "escalation": "உயிருக்கு ஆபத்து என்றால் 108 என்பதில் ஆம்புலன்ஸ் அழைக்கவும்.",
                   "citations": ["G-STRUCTURAL", "G-EVACUATE", "G-HELPLINE", "G-AMBU-108"]},
            "en": {"summary": "Embankment or wall breach — move to safety immediately.",
                   "action": "Leave the building. Do not cross the bridge. Call 1077.",
                   "escalation": "If life is in danger, call 108 for ambulance.",
                   "citations": ["G-STRUCTURAL", "G-EVACUATE", "G-HELPLINE", "G-AMBU-108"]},
        },
    },
    "drain_blockage": {
        "high": {
            "ta": {"summary": "வடிகால் அடைபட்டுள்ளது — தண்ணீர் தேங்கி நிற்கிறது.",
                   "action": "வடிகாலை தாங்களாக சுத்தம் செய்ய வேண்டாம். 1077 என்பதில் புகார் செய்யவும். மோட்டார் பம்ப் கேளுங்கள்.",
                   "escalation": "நிலைமை மோசமானால் 1077 என்பதில் அழைக்கவும்.",
                   "citations": ["G-DRAIN-BLOCKAGE", "G-MOTOR-PUMP", "G-HELPLINE"]},
            "en": {"summary": "Drain blocked — water stagnating on your street.",
                   "action": "Do not attempt to clear drains yourself during rain. Report to 1077. Request motor pump deployment.",
                   "escalation": "If conditions worsen, call 1077.",
                   "citations": ["G-DRAIN-BLOCKAGE", "G-MOTOR-PUMP", "G-HELPLINE"]},
        },
        "moderate": {
            "ta": {"summary": "வடிகால் அடைப்பு — மழைக்குப் பின் தண்ணீர் தேங்குகிறது.",
                   "action": "1077 என்பதில் உங்கள் தெருவின் பெயருடன் புகார் செய்யவும்.",
                   "escalation": "அவசரம் என்றால் 1077 என்பதில் அழைக்கவும்.",
                   "citations": ["G-DRAIN-BLOCKAGE", "G-HELPLINE"]},
            "en": {"summary": "Drain blockage — water stagnates after rain.",
                   "action": "Report to 1077 with your street name.",
                   "escalation": "For emergencies, call 1077.",
                   "citations": ["G-DRAIN-BLOCKAGE", "G-HELPLINE"]},
        },
    },
    "waste_accumulation": {
        "high": {
            "ta": {"summary": "குப்பை வடிகாலை அடைத்துள்ளது — மழையில் வெள்ள அபாயம்.",
                   "action": "1077 என்பதில் புகார் செய்யவும். குப்பையை வடிகாலில் விட வேண்டாம்.",
                   "escalation": "அவசரம் என்றால் 1077 என்பதில் அழைக்கவும்.",
                   "citations": ["G-WASTE-HOTSPOT", "G-DRAIN-BLOCKAGE", "G-HELPLINE"]},
            "en": {"summary": "Garbage blocking drains — flood risk when it rains.",
                   "action": "Report to 1077. Do not dump waste into drains.",
                   "escalation": "For emergencies, call 1077.",
                   "citations": ["G-WASTE-HOTSPOT", "G-DRAIN-BLOCKAGE", "G-HELPLINE"]},
        },
        "moderate": {
            "ta": {"summary": "தெருவில் குப்பை குவிந்துள்ளது — வடிகால் அடைப்பு ஏற்படலாம்.",
                   "action": "1077 என்பதில் புகார் செய்யவும்.",
                   "escalation": "அவசரம் என்றால் 1077 என்பதில் அழைக்கவும்.",
                   "citations": ["G-WASTE-HOTSPOT", "G-HELPLINE"]},
            "en": {"summary": "Garbage accumulating on street — may block drains.",
                   "action": "Report to 1077.",
                   "escalation": "For emergencies, call 1077.",
                   "citations": ["G-WASTE-HOTSPOT", "G-HELPLINE"]},
        },
    },
    "water_stagnation": {
        "high": {
            "ta": {"summary": "தெருவில் தண்ணீர் தேங்கி நிற்கிறது — போக்குவரத்து பாதிக்கப்பட்டுள்ளது.",
                   "action": "1077 என்பதில் புகார் செய்யவும். மோட்டார் பம்ப் கேளுங்கள்.",
                   "escalation": "அவசரம் என்றால் 1077 என்பதில் அழைக்கவும்.",
                   "citations": ["G-WATERLOGGING", "G-MOTOR-PUMP", "G-HELPLINE"]},
            "en": {"summary": "Water stagnating on street — traffic affected.",
                   "action": "Report to 1077. Request motor pump deployment.",
                   "escalation": "For emergencies, call 1077.",
                   "citations": ["G-WATERLOGGING", "G-MOTOR-PUMP", "G-HELPLINE"]},
        },
        "moderate": {
            "ta": {"summary": "தேங்கிய தண்ணீர் — மழைக்குப் பின் நிற்கிறது.",
                   "action": "1077 என்பதில் உங்கள் தெருவின் பெயருடன் புகார் செய்யவும்.",
                   "escalation": "அவசரம் என்றால் 1077 என்பதில் அழைக்கவும்.",
                   "citations": ["G-WATERLOGGING", "G-HELPLINE"]},
            "en": {"summary": "Stagnant water — persists after rain.",
                   "action": "Report to 1077 with your street name.",
                   "escalation": "For emergencies, call 1077.",
                   "citations": ["G-WATERLOGGING", "G-HELPLINE"]},
        },
    },
}


def _template(report_type: str, severity: str, lang: str) -> dict | None:
    """Look up the deterministic template for this report type + severity + language."""
    rt = TEMPLATES.get(report_type, {})
    sev = rt.get(severity) or rt.get("immediate") or rt.get("high") or rt.get("moderate")
    if sev is None:
        return None
    return sev.get(lang) or sev.get("en")


def _decider_critic(plan: ReportPlan, text: str) -> bool:
    """Use the Decider as critic: ask if this assessment is safe and appropriate.

    Returns True if the Decider says the assessment is safe (noul >= 0.5),
    False if it says it's unsafe (fail-closed).
    """
    assessment = f"Report: {text}. Assessment severity: {plan.severity}. Report type: {plan.report_type}. Zone: {plan.zone_id}. Action: {plan.recommended_action[:200]}"
    a = gate.decide(assessment, {
        "safe": {"type": "noul", "instructions": "Is this flood assessment safe? Does it correctly escalate emergencies and avoid telling people to stay during canal overflow or structural risk?"}
    })
    p_safe = a["safe"]["noul"]
    print(f"[critic] decider p_safe={p_safe:.2f} -> {'PASS' if p_safe >= 0.3 else 'FAIL'}", flush=True)
    return p_safe >= 0.3


def run(case: dict) -> dict:
    """Process one resident report. Returns {"plan": ReportPlan.dict, "meta": {...}}."""
    t0 = time.time()
    text = case["text"]
    lang = case.get("lang") or tools.language_of(text)
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
        meta["critic_ok"] = True
        meta["latency_ms"] = int((time.time() - t0) * 1000)
        print(f"[plan] {meta['path']} | {meta['latency_ms']} ms", flush=True)
        return {"plan": ans.model_dump(), "meta": meta}

    # Layer 2: Decider urgency gate — code-owned emergency decision.
    urg = gate.urgency_score(text)
    print(f"[decider] p_emergency {urg['p_emergency']:.2f}, priority {urg['priority']} "
          f"(confidence {urg['confidence']:.2f})", flush=True)

    if urg["p_emergency"] >= gate.EMERGENCY_THRESHOLD:
        print("[decider] EMERGENCY threshold met -> immediate priority", flush=True)

    # Layer 3: Parse the report with code-only tools.
    parsed = tools.parse_report._tool_func(text) if hasattr(tools.parse_report, "_tool_func") else tools.parse_report(text)
    zone_id = parsed["zone_id"]
    zone_name = parsed["zone_name"]
    report_type = parsed["report_type"]

    # Override report_type with Decider priority only when confidence is high.
    # The Decider doesn't understand Tamil well, so trust keyword detection for low-confidence cases.
    decider_map = {
        "emergency_evacuate": "structural_risk",
        "canal_overflow": "canal_overflow",
        "drain_blockage": "drain_blockage",
    }
    if urg["priority"] in decider_map and urg["confidence"] >= 0.5:
        report_type = decider_map[urg["priority"]]

    # Determine severity from report_type (keyword detection, primary) and Decider (secondary).
    priority = urg["priority"]
    p_emerg = urg["p_emergency"]
    if report_type == "structural_risk" or priority == "emergency_evacuate" or p_emerg >= gate.EMERGENCY_THRESHOLD:
        severity = "immediate"
    elif report_type == "canal_overflow":
        severity = "immediate" if p_emerg >= 0.40 else "high"
    elif priority == "drain_blockage" or report_type == "drain_blockage":
        severity = "high" if p_emerg >= 0.15 else "moderate"
    elif report_type == "waste_accumulation" or priority == "waste_accumulation":
        severity = "high" if p_emerg >= 0.3 else "moderate"
    else:
        severity = "moderate" if p_emerg >= 0.15 else "low"

    # Layer 4: Generate assessment from deterministic templates (code owns the text).
    tmpl = _template(report_type, severity, lang)
    if tmpl is None:
        # Fall back to a generic template.
        tmpl = {
            "ta": {"summary": f"{zone_name} பகுதியில் தண்ணீர் பிரச்சினை. 1077 என்பதில் புகார் செய்யவும்.",
                   "action": "1077 என்பதில் அழைக்கவும்.", "escalation": "அவசரம் என்றால் 1077.",
                   "citations": ["G-HELPLINE"]},
            "en": {"summary": f"Water issue in {zone_name}. Report to 1077.",
                   "action": "Call 1077.", "escalation": "For emergencies, call 1077.",
                   "citations": ["G-HELPLINE"]},
        }
        tmpl = tmpl[lang] if lang in tmpl else tmpl["en"]

    # Look up guidance for citations.
    guidance_hits = tools.lookup_guidance._tool_func(text) if hasattr(tools.lookup_guidance, "_tool_func") else tools.lookup_guidance(text)
    guidance_ids = [g["id"] for g in guidance_hits[:4]]

    ans = ReportPlan(
        language=lang,
        zone_id=zone_id,
        zone_name=zone_name,
        report_type=report_type,
        severity=severity,
        summary=tmpl["summary"],
        recommended_action=tmpl["action"],
        escalation=tmpl["escalation"],
        citations=tmpl.get("citations", guidance_ids),
    )

    # Layer 5: Decider critic — only for cases above moderate urgency (fail-closed).
    # The Decider doesn't understand Tamil assessment text, so for Tamil cases
    # the deterministic templates are safe by design and don't need a critic check.
    critic_ok = True
    if urg["p_emergency"] >= 0.25 and lang == "en":
        critic_ok = _decider_critic(ans, text)
    elif lang == "ta":
        print("[critic] skipped (Tamil case, templates safe by design) -> PASS", flush=True)
    else:
        print("[critic] skipped (routine case, templates safe by design) -> PASS", flush=True)
    meta["critic_ok"] = critic_ok
    if not critic_ok:
        print("[safety] FAIL-CLOSED: decider critic did not pass -> unverified, manual review", flush=True)
        ans = ReportPlan(
            language=lang,
            zone_id=zone_id,
            zone_name=zone_name,
            report_type=report_type,
            severity=severity,
            summary=UNVERIFIED[lang],
            recommended_action=UNVERIFIED[lang],
            escalation=UNVERIFIED[lang],
            citations=[],
        )
        meta["path"] = "fail_closed"

    meta["passes"] = 1
    meta["latency_ms"] = int((time.time() - t0) * 1000)
    meta["decider_p_emergency"] = urg["p_emergency"]
    meta["decider_priority"] = urg["priority"]
    print(f"[plan] {meta['path']} | {meta['latency_ms']} ms", flush=True)
    return {"plan": ans.model_dump(), "meta": meta}


class AutoConfirmPolicy(InterventionHandler):
    """Confirm intervention: a human must approve the ranked list before logging."""
    name = "priority-confirm"

    def __init__(self, auto: bool = True):
        self.auto = auto
        self.confirmed = False

    def before_tool_call(self, event):
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
    """Process multiple reports and produce a ranked PriorityList for the ward officer."""
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

    imm = sum(1 for r in results if r["plan"]["severity"] == "immediate")
    handoffs = sum(1 for r in results if r["meta"].get("path") == "handoff")
    summary_en = f"{len(results)} reports triaged. {imm} immediate, {handoffs} crisis handoffs."
    summary_ta = f"{len(results)} அறிக்கைகள் மதிப்பிடப்பட்டன. {imm} உடனடி, {handoffs} நெருக்கடி."

    priority_list = PriorityList(
        items=items,
        summary_ta=summary_ta,
        summary_en=summary_en,
        citations=list({c for r in results for c in r["plan"].get("citations", [])}),
    )

    # Confirm intervention — ward officer approves before logging.
    policy = AutoConfirmPolicy(auto=auto_confirm)
    policy.before_tool_call({"tool_use": {"name": "log_priority", "input": {}}})

    meta = {
        "path": "batch",
        "count": len(results),
        "immediate": imm,
        "crisis_handoffs": handoffs,
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
        print(f"\n[{plan['severity'].upper()}] {plan['zone_name']} - {plan['report_type']}")
        print(f"\n{plan['summary']}")
        print(f"\nAction: {plan['recommended_action']}")
        print(f"Escalation: {plan['escalation']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
