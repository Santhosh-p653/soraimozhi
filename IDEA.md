# SoraiMozhi (சோறை மொழி)

## Pitch

A Tamil-first agent that turns resident flood and drain-blockage reports from Madurai's 27 vulnerable zones into a ranked clearance priority list for ward officers — with a human in the loop before anything is logged.

## Who it helps

Residents of Sellur, SS Colony, Kalavasal, Villapuram, Mattuthavani, Arapalayam — the wards worst hit by the crippled waste management system and choked canals during the October 2026 northeast monsoon. Ward officers and Corporation workers who must decide which of 50+ flood-prone spots to clear first when everything is underwater at once.

## The real story

Madurai is on maximum alert. The district administration identified 27 highly vulnerable zones (17 urban, 10 rural). Garbage from SS Colony, Kalavasal, Villapuram is washing directly into the Panthalkudi canal and stormwater drains, blocking drainage channels and triggering severe waterlogging. The canal — which carries overflow from the Sellur tank to the Vaigai — is choked with debris and sewage. Uncollected roadside garbage gets washed into drains during rain. A resident texts "என் தெருவில் தண்ணீர் நிற்கிறது" (water stagnating in my street). The Corporation has 50 spots to fix and no way to triage which one risks canal overflow vs which is just a puddle.

Sources:
- Times of India: "Rain water washes away garbage piles, chokes drains" (Oct 2026)
- Times of India: "Madurai corpn fixing 50 flood-prone spots" (Oct 2026)
- New Indian Express: "Debris in Panthalkudi canal sparks flood fears" (Jul 2026)
- The Hindu: "Monitoring Officer inspects monsoon preparedness" — 27 vulnerable zones, helpline 1077 (Oct 2026)

## Focus area

Climate resilience — extreme rainfall events are increasing in frequency; the agent helps urban drainage infrastructure respond faster and more intelligently.

## The decision that must never be wrong

Not escalating a canal overflow or embankment breach report as low-priority. If a report indicates water rising near a canal bank, a structural risk, or a person in danger, the agent must flag it as immediate — never bury it in the queue.

## What will be measured (this week)

30+ signed cases covering:
- 8+ emergencies (canal overflow, embankment risk, person stranded)
- 10+ in Tamil
- 5+ zone types (Sellur, SS Colony, Kalavasal, Villapuram, Mattuthavani)
- 3+ report types (drain blockage, canal overflow, water stagnation, structural risk)

Metrics:
- Emergency recall: 100% of true emergencies flagged as immediate
- Unsafe-priority rate: 0 cases where an emergency was deprioritized
- Priority accuracy: does the ranked order match a human ward officer's judgment?
- Goal success (Strands Evals judge, 0-1) vs a one-prompt baseline on the same cases
- Every case signed by a named person

## Languages

Tamil first (தமிழ்), English fallback. Amazon Translate for Tamil output when the model slips to English. Amazon Transcribe ta-IN for Tamil voice input (stretch goal).

## Devices

Residents: shared smartphone, WhatsApp text. Ward officers: laptop or smartphone dashboard.

## Strands blocks used (each does a visible job)

| Block | Job | Why it earns its place |
|---|---|---|
| `tools` | Parse location + severity from natural Tamil text, structured output | Every report gets the same fields so you can score and rank |
| `decider` | Classify urgency: drain blockage / canal overflow / immediate evacuation | One fast calibrated yes/no/choice decision, no generated text — routes instantly |
| `graph` | Planner -> critic loop to produce ranked clearance order with reasoning | Counted quality loop, fail-closed if critic never passes |
| `interventions` | Confirm: ward officer approves top-3 action list before logging | A human stays in control of what gets prioritized |
| `sessions` | Track reports per ward across the flood event | Before/after data per zone, cumulative view |
| `evals` | Adversarial red-team: false spam reports, prompt injection, excessive agency | "We attacked it N ways and it held" for the article |
| `shell` | Crunch aggregated report CSV to find spatial clustering | Real data work, sandboxed, host files not visible |

## Novel AWS services

- Amazon Translate (Tamil output)
- Amazon Transcribe ta-IN (Tamil voice input — stretch goal)
- Strands Shell (report data analysis)
- Optional: Amazon Location Service (map reports to zones — stretch goal)

## Scores

| Quarter | Score | Reason |
|---|---|---|
| Social impact | 8/10 | Directly addresses the crippled waste/drain system; real zones, real crisis |
| Technical execution | 8/10 | Decider + graph + Confirm intervention is a clean, distinct stack |
| Communication | 7/10 | Ward officer dashboard is harder to demo than resident-facing; mitigated by Tamil-first reports |
| Originality | 9/10 | No other team will be doing drain triage; combines Decider + interventions in a novel way |
| Buildable in days left | 9/10 | No live sensor data needed; mock ward reports from real zone names work fine |

**Total: 41/50**

## Argument against (Gate 2 judge perspective)

- "Is the impact measurable?" — Yes: emergency recall and priority accuracy are countable on signed cases this week.
- "Would a plain prompt do as well?" — No: a single prompt cannot maintain a ranked queue across multiple reports, cannot Confirm with a human, and cannot fail-closed when the critic disagrees.
- "Who could be harmed?" — If the agent deprioritizes a real canal overflow, residents could be stranded. Mitigated by the Decider urgency gate (code-owned, not model-judged) and the fail-closed graph.
- "Is it just the hackathon example?" — No. HeatSafe Shift is heat-safety; this is flood infrastructure triage. Different user, different decision, different Strands combination.

## Steelman

What would have to be true for it to win: 30 signed Tamil cases showing 100% emergency recall, 0 unsafe deprioritizations, and a measured gap vs baseline on priority accuracy — all from real Madurai zone names with a human ward officer validating the ranked output.

## Not this week

- Live integration with Corporation 1077 helpline
- Real-time sensor data from drains
- Voice pipeline (Amazon Transcribe ta-IN) — stretch goal
- Amazon Location Service routing — stretch goal
- Multi-ward federation across all 27 zones — MVP covers 5 representative zones

## Distinct from other teams

No other team in AWS UG Madurai is building a drain/flood triage agent. The user group (ward officers + residents of specific flood-prone wards), the district (Madurai), the language (Tamil), and the decision (clearance priority ranking) are all specific to this team.
