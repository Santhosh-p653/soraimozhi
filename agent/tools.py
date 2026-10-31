"""Tools the planner can call, plus plain helpers app.py uses. All read-only, curated sources only."""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path

from strands import tool

DATA = Path(__file__).parent / "data"
TAMIL = re.compile(r"[\u0B80-\u0BFF]")


@lru_cache(maxsize=1)
def guidance() -> dict:
    return json.loads((DATA / "guidance.json").read_text(encoding="utf-8"))


def guidance_ids() -> set[str]:
    return {g["id"] for g in guidance()["items"]}


@lru_cache(maxsize=1)
def zones() -> dict:
    return json.loads((DATA / "zones.json").read_text(encoding="utf-8"))


def zone_list() -> list[dict]:
    return zones()["zones"]


def zone_ids() -> set[str]:
    return {z["id"] for z in zones()["zones"]}


def language_of(text: str) -> str:
    return "ta" if TAMIL.search(text or "") else "en"


def has_tamil(text: str) -> bool:
    return bool(TAMIL.search(text or ""))


def _match_zone(text: str) -> dict | None:
    """Match a resident's text to a zone by Tamil or English name (case-insensitive substring)."""
    lower = (text or "").lower()
    for z in zones()["zones"]:
        if z["name_en"].lower() in lower or z["name_ta"] in text:
            return z
        # also match common aliases
        aliases = {
            "sellur": ["sellur", "செல்லூர்"],
            "ss_colony": ["ss colony", "ss_colony", "எஸ்.எஸ். காலனி", "surveyor colony"],
            "kalavasal": ["kalavasal", "காலவாசல்"],
            "villapuram": ["villapuram", "விலாபுரம்", "villupuram"],
            "mattuthavani": ["mattuthavani", "மத்துத்தவனி", "tm nagar", "matuthavani"],
            "arapalayam": ["arapalayam", "ஆரப்பாளையம்", "arappalayam"],
        }
        for alias in aliases.get(z["id"], []):
            if alias in lower:
                return z
    return None


def translate_to_tamil(texts: list[str]) -> list[str]:
    """Amazon Translate fallback when the model answered a Tamil speaker in English."""
    import boto3
    c = boto3.client("translate", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    return [c.translate_text(Text=t, SourceLanguageCode="en", TargetLanguageCode="ta")["TranslatedText"]
            if t and not has_tamil(t) else t
            for t in texts]


@tool
def parse_report(text: str) -> dict:
    """Parse a resident's flood/drain report into structured fields. Always call this first.

    Extracts the zone, report type, and severity from natural Tamil or English text.

    Args:
        text: the resident's message, in Tamil or English
    """
    z = _match_zone(text)
    lower = text.lower()
    # report type detection by keywords (Tamil + English)
    report_type = "water_stagnation"
    canal_words = ["canal", "கால்வாய்", "panthalkudi", "பந்தால்குடி", "overflow", "நிரம்பி", "வழிகிறது"]
    drain_words = ["drain", "வடிகால்", "blocked", "அடைப்பு", "choke", "அடைபட்ட"]
    waste_words = ["garbage", "குப்பை", "waste", "கழிவு", "rubbish", "பார்ப்பு"]
    struct_words = ["crack", "விரிசல்", "embankment", "வரப்பு", "bridge", "பாலம்", "wall", "சுவர்"]
    if any(w in lower for w in canal_words):
        report_type = "canal_overflow"
    elif any(w in lower for w in drain_words):
        report_type = "drain_blockage"
    elif any(w in lower for w in waste_words):
        report_type = "waste_accumulation"
    elif any(w in lower for w in struct_words):
        report_type = "structural_risk"

    zone_id = z["id"] if z else "unknown"
    zone_name = z["name_ta"] if z and language_of(text) == "ta" else (z["name_en"] if z else "unknown")
    return {
        "zone_id": zone_id,
        "zone_name": zone_name,
        "report_type": report_type,
        "ward": z["ward"] if z else None,
        "vulnerability": z["vulnerability"] if z else "unknown",
    }


@tool
def lookup_guidance(topic: str) -> list[dict]:
    """Find curated, dated flood/drain guidance to cite. Returns items with id and text.

    Args:
        topic: words to match, e.g. "canal", "drain", "evacuate", "வெள்ளம்", "கால்வாய்"
    """
    words = [w for w in re.findall(r"[\w\u0B80-\u0BFF]+", topic.lower()) if len(w) > 2]
    items = guidance()["items"]
    hits = [g for g in items if any(w in (g["id"] + " " + g["text"]).lower() for w in words)]
    return [{"id": g["id"], "text": g["text"]} for g in (hits or items)[:6]]


@tool
def nearest_shelter(zone_id: str) -> str:
    """Find the nearest listed relief shelter for a zone. Never claim the shelter is open now.

    Args:
        zone_id: zone id from parse_report, e.g. sellur, mattuthavani
    """
    for s in zones()["shelters"]:
        if s["zone"] == zone_id:
            return f"{s['name']} (confirm locally before sending residents)"
    return "Call 1077 for nearest shelter information."
