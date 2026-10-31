"""Structured output models. Every plan has the same fields so score.py can score deterministically."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ReportPlan(BaseModel):
    """One resident's report parsed into structured fields."""
    language: Literal["en", "ta"] = Field(description="Language the resident wrote in: en or ta")
    zone_id: str = Field(description="Zone id from zones.json, e.g. sellur, ss_colony, kalavasal")
    zone_name: str = Field(description="Zone name in the resident's language")
    report_type: Literal["drain_blockage", "canal_overflow", "water_stagnation", "structural_risk", "waste_accumulation"] = \
        Field(description="What kind of report this is")
    severity: Literal["low", "moderate", "high", "immediate"] = Field(description="How urgent, from the decider gate")
    summary: str = Field(description="One short sentence the resident reads, in their language")
    recommended_action: str = Field(description="What the resident should do now, in their language")
    escalation: str = Field(description="Who to contact and when, in their language")
    citations: list[str] = Field(default_factory=list, description="Guidance ids from guidance.json that back this report")


class PriorityItem(BaseModel):
    """One item in the ward officer's ranked clearance list."""
    rank: int = Field(description="Priority rank: 1 = highest, 2 = next, etc.")
    zone_id: str = Field(description="Zone id")
    zone_name: str = Field(description="Zone name in Tamil")
    report_type: str = Field(description="Type of report")
    severity: str = Field(description="Severity level")
    reason: str = Field(description="Why this rank, one short sentence")
    action: str = Field(description="What the officer should do, one short sentence")


class PriorityList(BaseModel):
    """The full ranked list the ward officer sees."""
    items: list[PriorityItem] = Field(description="Ranked clearance items, highest priority first")
    summary_ta: str = Field(description="One-line summary of the situation in Tamil")
    summary_en: str = Field(description="One-line summary in English")
    citations: list[str] = Field(default_factory=list, description="Guidance ids used")


class Critique(BaseModel):
    """Critic checks the planner's ranked list for unsafe deprioritization."""
    ok: bool = Field(description="true only if the priority list breaks none of the rules")
    problems: list[str] = Field(default_factory=list, description="Each rule broken, one short line each")
    unsafe_deprioritized: list[str] = Field(default_factory=list, description="Zone ids that were emergencies but placed below rank 3")
