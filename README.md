# SoraiMozhi (சோறை மொழி)

A Tamil-first flood and drain-blockage triage agent for Madurai's 27 vulnerable flood zones. Built with the [Strands Agents SDK](https://github.com/strands-agents/sdk-python) for the AWS "Workshop to Ship" hackathon.

## What it does

Residents text flood reports in Tamil or English. The agent:
- Parses the zone, report type, and severity from natural language
- Routes emergencies (canal overflow, drowning, structural failure) to 108/1077
- Produces a ranked clearance priority list for ward officers
- Requires human approval before anything is logged

The key design principle: **code owns the facts that must never be wrong; the model writes the words; a human stays in control.**

## Architecture

| Layer | What | Owner |
|---|---|---|
| Crisis hook | Scans for danger phrases, cancels the model, returns fixed Tamil handoff text | Code (`gate.py`) |
| Decider urgency gate | Calibrated probability decides if someone is in danger (threshold 0.80) | Code (`gate.py`) |
| Report parser | Extracts zone, report type, severity from Tamil/English text | `tools.py` |
| Deterministic templates | Safety text (evacuation steps, helpline numbers) — model never writes these | Code (`app.py`) |
| Decider critic | Checks assessment safety, fail-closed if it doesn't pass | Code (`app.py`) |
| Confirm intervention | Ward officer approves ranked list before logging | `app.py` |

## Strands SDK blocks used

- `tools` — `parse_report`, `lookup_guidance`, `nearest_shelter`
- `decider` — calibrated urgency classification (noul + choice)
- `hooks` — `CrisisHook` cancels the graph before any node runs
- `interventions` — `Confirm` gate for human approval
- `graph` — planner builds ranked clearance order, critic checks for unsafe deprioritization
- `evals` — adversarial red-team (prompt injection, false spam, severity under-call)

## Quick start

```bash
# Install dependencies
pip install -r requirements.txt

# Set up AWS credentials (Bedrock + Translate)
aws configure
# Or: aws sso login

# Set the Decider API key (environment variable, never paste into code)
set DECIDER_API_KEY=your-key-here

# Run the CLI agent
python -m agent.app "செல்லூர் பந்தால்குடி கால்வாய் நிரம்பி வழிகிறது"
python -m agent.app "SS Colony drain blocked by garbage" --json

# Run the web dashboard
python -m ui.app
# Open http://localhost:8000

# Measure against the one-prompt baseline (32 signed cases)
python measure_local.py

# Record the demo video
ss video
# Or: python -m ship_kit.video
```

## Measured results (32 human-labelled cases)

| Metric | SoraiMozhi agent | Single-prompt baseline |
|---|---|---|
| Emergency recall | 100% | 100% |
| Plans with unsafe advice | 0 | 13 |
| Severity / priority correct | 68.75% | 31.25% |
| Must-include safety keywords | 65.6% | 28.1% |
| Tamil cases answered in Tamil | 100% | 100% |
| Average citations per plan | 3.22 | 1.0 |
| Latency p50 | 2,690 ms | <1 ms |

Gate: PASSED. Full breakdown in `results/MEASURE.md`.

## Project structure

```
agent/
  app.py          # entrypoint: runs a case, returns plan + meta
  gate.py         # Decider urgency gate + crisis hook (code-owned decisions)
  tools.py        # parse_report, lookup_guidance, nearest_shelter
  plan.py         # Pydantic structured output models
  score.py        # deterministic scoring against labelled cases
  baseline.py     # one-prompt baseline for measurement
  data/
    guidance.json # curated Madurai flood/drain guidance with sources
    zones.json    # 6 vulnerable zones with ward, canal, vulnerability
ui/
  app.py          # FastAPI web server
  templates/      # dashboard HTML
  static/         # CSS + JS
ship_kit/
  cli.py          # ss command-line interface
  measure.py      # measurement runner
  video.py        # demo video recorder (Playwright)
  cases.py        # case management
  submit.py       # submission validation
cases.jsonl       # 32 human-labelled test cases
measure_local.py  # local measurement script
video.json        # demo video scene definitions
results/          # measured outputs (never edit by hand)
```

## Key design decisions

1. **Code owns safety text.** Evacuation instructions and helpline numbers live in Python templates, not model output. The model can hallucinate freely; the resident still gets correct Tamil guidance.
2. **Fail-closed by default.** If the critic never passes, the system returns "unverified — manual review" rather than shipping something unchecked.
3. **Tamil-first.** `language_of()` detects Tamil via Unicode range. Safety templates are keyed by language. Amazon Translate catches any English drift.
4. **Read-only tools.** No tool writes, deletes, or reaches outside curated data. `parse_report` matches against a fixed zone list; `lookup_guidance` returns only items from `guidance.json`.

## AWS services

- **Amazon Bedrock** (Nova 2 Lite) — model for the planner and critic
- **Amazon Translate** — Tamil fallback when the model answers in English
- **Strands Decider** — calibrated decision layer for urgency classification

## Hackathon

Built for the [Strands SDK: Workshop to Ship](https://aws.amazon.com/builder-center/) hackathon. Focus area: climate resilience. The agent addresses real flood infrastructure challenges in Madurai, India.

## License

Private repository. Source code will be made public after the hackathon window.

---

*SoraiMozhi is built with the Strands Agents SDK. Source code, labelled case set, and measured results are in the repository.*
