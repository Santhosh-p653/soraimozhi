# SoraiMozhi — Style Guide

## Code conventions

- Python 3.10+ syntax (`from __future__ import annotations` at the top of every module)
- Standard library first; Strands SDK second; boto3 third. No unnecessary deps.
- Every agent gets `callback_handler=None` in production runs (silent); set it to a real handler only for debugging
- Every `Agent()` gets an explicit `name=` parameter for trace readability
- System prompts are short, imperative, and state the constraint: "Call X first. Cite only ids it returns. Never invent Y."
- Structured output models in `plan.py` use Pydantic `Field(description=...)` on every field
- Tools are read-only and curated — no live web scraping, no user-generated content as source

## File naming

- `app.py` — the entrypoint (builds the graph, runs a case)
- `gate.py` — code-owned decisions (Decider, crisis hook)
- `tools.py` — `@tool` functions + plain helpers
- `plan.py` — Pydantic structured output models only
- `score.py` — deterministic scoring (no model calls in here)
- `baseline.py` — the one-prompt baseline
- `*_tool.py` — standalone tool wrappers (shell, sessions)
- `redteam.py` — adversarial evals

## Evidence lines

Every block prints `[tag] text` evidence lines (the video studio turns these into badges):
```python
print(f"[decider] p_emergency {d['p_emergency']:.2f}, priority {d['priority']}", flush=True)
print(f"[critic] pass 1: PASS", flush=True)
print(f"[safety] RED FLAG (canal overflow) -> HAND OFF, agents cancelled", flush=True)
print(f"[plan] graph | 3200 ms", flush=True)
print(f"[shell] $ sort -t, -k3 reports.csv -> exit 0", flush=True)
```

Tags used: `decider`, `critic`, `safety`, `plan`, `shell`, `guard`, `session`, `evals`

## Tamil-first rules

- Tamil script is the primary language; English is the fallback
- `language_of(text)` detects Tamil via `[\u0B80-\u0BFF]` Unicode range
- If the model answers a Tamil case in English, `translate_to_tamil()` via Amazon Translate catches it
- System prompts instruct: "Answer in Tamil (Tamil script)" for `lang == "ta"`
- Zone names have both `name_en` and `name_ta` fields in `zones.json`
- Crisis phrases in `RED_FLAGS` include Tamil variants

## Thresholds and numbers

| Threshold | Value | Source |
|---|---|---|
| Decider `is_emergency` | >= 0.80 | Calibrated on our labelled emergency cases before measurement |
| Graph max passes | 2 | planner → critic → planner, then fail-closed |
| Graph max node executions | 4 | safety cap |
| Swarm max handoffs | 4 | from the workshop default |
| Min cases for measurement | 30 | 8 emergency, 10 Tamil, 5 zone types |
| Emergency recall gate | 100% | no emergencies may be deprioritized |
| Unsafe deprioritization gate | 0 | no emergency below rank 3 |

## Git conventions

- Commit messages: `type: short description` (e.g. `feat: add canal overflow crisis phrases`, `fix: decider threshold calibration`)
- Keep the repo private until the hackathon window opens (28 Oct 2026)
- No secrets, API keys, or credentials in code — use environment variables
- `.gitignore` includes: `.venv/`, `__pycache__/`, `results/_raw/`, `*.webm`

## Agent architecture rules

1. **Code owns the facts.** The Decider gate and crisis hook are code, not model judgment.
2. **The model writes the words.** The planner generates the ranked list; the critic checks it.
3. **People stay in control.** The Confirm intervention means nothing is logged without a human yes.
4. **Fail closed.** If the critic never passes, return "unverified — manual review." Never output unchecked model text.
5. **Every plan has the same fields.** Structured output via Pydantic so `score.py` can score every case deterministically.
6. **The baseline has none of the above.** One agent, one prompt, same model, same data. It must lose.
