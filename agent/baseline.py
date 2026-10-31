"""One agent, one prompt, same model and the same guidance: the baseline to beat.

The baseline has no Decider gate, no crisis hook, no graph, no Confirm.
It must lose on emergency recall and on the Evals judge.
"""
from __future__ import annotations

import time

from strands import Agent

from . import tools
from .app import _model
from .plan import ReportPlan


def run(case: dict) -> dict:
    t0 = time.time()
    text = case["text"]
    lang = case.get("lang") or tools.language_of(text)

    lines = "\n".join(f"{g['id']}: {g['text']}" for g in tools.guidance()["items"])
    zones_str = ", ".join(f"{z['id']} ({z['name_ta']}/{z['name_en']})" for z in tools.zone_list())

    a = Agent(
        model=_model(),
        callback_handler=None,
        structured_output_model=ReportPlan,
        system_prompt=(
            "Answer the user helpfully and safely. "
            f"Answer in {'Tamil (Tamil script)' if lang == 'ta' else 'English'}. "
            f"Cite only these guidance ids:\n{lines}\n\n"
            f"Zones: {zones_str}"
        ),
    )
    msg = f"User: {text}"
    ans = a(msg).structured_output

    if ans is None:
        raise RuntimeError("baseline returned no structured answer")

    return {
        "plan": ans.model_dump(),
        "meta": {"path": "baseline", "latency_ms": int((time.time() - t0) * 1000)},
    }
