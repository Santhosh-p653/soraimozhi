"""Code-owned decisions: Decider urgency gate + crisis hook.

The decision that must never be wrong lives here, not in the model.
- Decider returns a calibrated number for emergency classification.
- CrisisHook bypasses the model entirely for known crisis phrases.
Neither lets the LLM decide what counts as an emergency.
"""
from __future__ import annotations

import json
import os
import urllib.request

from strands.hooks import BeforeNodeCallEvent, HookProvider, HookRegistry


# Crisis phrases that bypass the model entirely (Tamil + English).
# Source: real flood reports from TOI, The Hindu, NIE Oct 2026.
RED_FLAGS = [
    # English
    "drowning", "stranded", "trapped", "unconscious", "swept away",
    "embankment breach", "canal overflow", "wall collapse", "bridge collapse",
    "person in water", "child in water", "body in water",
    "chest pain", "not breathing", "bleeding heavily",
    # Tamil
    "மூழ்கி", "மூழ்கிவிட்டார்", "உயிருக்கு ஆபத்து", "அடைபட்டு", "சிக்கிவிட்டார்",
    "நீரில் அடிபட்டு", "வரப்பு உடைந்து", "சுவர் இடிந்து", "பாலம் இடிந்து",
    "குழந்தை தண்ணீரில்", "ரத்தம்", "மூச்சு விடவில்லை", "மயக்கம்",
]

# Fixed handoff text — no model output touches this path.
HANDOFF = {
    "en": ("This is a life-safety emergency. Call 108 for ambulance immediately. "
           "Move to a higher floor. Do not cross flooded roads. Call 1077 for evacuation."),
    "ta": ("இது உயிருக்கு ஆபத்தான சூழ்நிலை. ஆம்புலன்ஸுக்கு உடனே 108 என்பதில் அழைக்கவும். "
           "மேல் தளத்திற்கு செல்லவும். வெள்ளத்தில் கடக்க வேண்டாம். வெளியேற்றத்திற்கு 1077 என்பதில் அழைக்கவும்."),
}

# Decider endpoint (hosted free by AWS User Group Madurai).
DECIDER_URL = os.environ.get("DECIDER_URL", "https://da25tnxy06gjk.cloudfront.net")
DECIDER_KEY = os.environ.get("DECIDER_API_KEY", "")


def decide(state: str, questions: dict) -> dict:
    """Call the Strands Decider endpoint. Returns calibrated yes/no/choice answers.

    Falls back to a keyword-based heuristic if DECIDER_API_KEY is not set,
    so the agent still runs during local development.
    """
    if DECIDER_KEY:
        req = urllib.request.Request(
            DECIDER_URL + "/v1/decide",
            data=json.dumps({"state": state, "questions": questions}).encode(),
            headers={"Authorization": f"Bearer {DECIDER_KEY}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)["answers"]
    # Fallback: keyword-based urgency scoring when no API key is set.
    return _heuristic_decide(state, questions)


def _heuristic_decide(state: str, questions: dict) -> dict:
    """Local fallback when the Decider endpoint is unavailable.

    Uses keyword matching to approximate emergency detection.
    NOT a substitute for the calibrated Decider — use the real endpoint for measurement.
    """
    lower = state.lower()
    emergency_keywords = [
        "drowning", "stranded", "trapped", "unconscious", "swept away",
        "embankment", "collapse", "canal overflow", "not breathing", "bleeding",
        "மூழ்கி", "உயிருக்கு ஆபத்து", "அடைபட்டு", "வரப்பு உடைந்து", "சுவர் இடிந்து",
        "மயக்கம்", "ரத்தம்", "மூச்சு விடவில்லை",
    ]
    is_emergency = any(kw in lower for kw in emergency_keywords)
    p_emergency = 0.95 if is_emergency else 0.1

    answers = {}
    for qid, q in questions.items():
        if q["type"] == "noul":
            answers[qid] = {"noul": p_emergency, "confidence": 0.9}
        elif q["type"] == "choice":
            if is_emergency:
                answers[qid] = {"choice": "emergency_evacuate", "confidence": 0.9}
            else:
                # route by report type keywords
                if any(w in lower for w in ["canal", "கால்வாய்", "overflow", "நிரம்பி"]):
                    answers[qid] = {"choice": "canal_overflow", "confidence": 0.8}
                elif any(w in lower for w in ["drain", "வடிகால்", "blocked", "அடைப்பு"]):
                    answers[qid] = {"choice": "drain_blockage", "confidence": 0.8}
                elif any(w in lower for w in ["garbage", "குப்பை", "waste", "கழிவு"]):
                    answers[qid] = {"choice": "waste_accumulation", "confidence": 0.7}
                else:
                    answers[qid] = {"choice": "routine", "confidence": 0.6}
    return answers


def urgency_score(message: str) -> dict:
    """Ask the Decider how urgent a report is. Returns numbers to branch on.

    Returns:
        p_emergency: float 0-1, calibrated probability this is a life-safety emergency
        priority: str, one of "emergency_evacuate", "canal_overflow", "drain_blockage",
                  "waste_accumulation", "routine"
        confidence: float 0-1
    """
    a = decide(message, {
        "emergency": {"type": "noul", "instructions": "Is someone in immediate danger to life, health, or trapped by flood water?"},
        "priority": {"type": "choice", "instructions": "What type of flood report is this?",
                     "criteria": {
                         "emergency_evacuate": "person stranded, drowning, injured, or life in danger",
                         "canal_overflow": "canal or tank overflow threatening homes",
                         "drain_blockage": "drain or UGD blocked, water stagnating",
                         "waste_accumulation": "garbage blocking drains, waste accumulation",
                         "routine": "minor waterlogging, no immediate risk",
                     }},
    })
    return {
        "p_emergency": a["emergency"]["noul"],
        "priority": a["priority"]["choice"],
        "confidence": a["priority"].get("confidence", 0),
    }


# Threshold calibrated on labelled cases. Adjust after measurement.
EMERGENCY_THRESHOLD = 0.80


class CrisisHook(HookProvider):
    """Cancels the agent graph if crisis words appear in the user's message.

    The model never gets a chance to respond to crisis phrases — the hook fires
    before any node executes, and the fixed handoff text is returned instead.
    """

    def __init__(self):
        self.tripped: list[str] = []

    def register_hooks(self, registry: HookRegistry, **_):
        registry.add_callback(BeforeNodeCallEvent, self._before)

    def _before(self, event: BeforeNodeCallEvent):
        text = str(event.invocation_state.get("user_text", "")).lower()
        hits = [p for p in RED_FLAGS if p in text or p.lower() in text]
        if hits:
            self.tripped = hits
            event.cancel_node = "crisis: " + ", ".join(hits)
