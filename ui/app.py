"""SoraiMozhi web dashboard — FastAPI server.

    python -m ui.app

Resident report input -> agent triage -> ranked clearance list for ward officers.
Green climate resilience theme.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# Add project root to path so agent is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent import app as agent_app
from agent import tools

BASE = Path(__file__).resolve().parent
app = FastAPI(title="SoraiMozhi", description="Madurai flood/drain triage dashboard")

app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE / "templates"))


class ReportRequest(BaseModel):
    text: str
    lang: str | None = None


class BatchRequest(BaseModel):
    reports: list[str]


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    zones = tools.zone_list()
    return templates.TemplateResponse("index.html", {"request": request, "zones": zones})


@app.post("/api/triage")
async def triage(req: ReportRequest):
    """Process a single resident report."""
    case = {"text": req.text, "lang": req.lang or tools.language_of(req.text)}
    result = agent_app.run(case)
    return JSONResponse(result)


@app.post("/api/triage-batch")
async def triage_batch(req: BatchRequest):
    """Process multiple reports into a ranked PriorityList."""
    cases = [{"text": t, "lang": tools.language_of(t)} for t in req.reports]
    result = agent_app.run_batch(cases, auto_confirm=True)
    return JSONResponse(result)


@app.get("/api/zones")
async def get_zones():
    return JSONResponse({"zones": tools.zone_list(), "shelters": tools.zones()["shelters"]})


@app.get("/api/guidance")
async def get_guidance():
    return JSONResponse(tools.guidance())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
