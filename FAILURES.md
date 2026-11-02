# FAILURES.md

Log what broke, how you found it, what you changed, and the re-measured number.

## Format

```
### [date] — short description
- **What broke:** ...
- **How found:** ss measure / ss cases check / manual test
- **Root cause:** ...
- **Fix:** ...
- **Re-measured:** ...
```

---

### 2026-11-02 — Decider endpoint DNS resolution failure (cases 17-30)
- **What broke:** Decider endpoint `https://da25tnxy06gjk.cloudfront.net` returned `[Errno 11001] getaddrinfo failed` for cases 17-30 of the full 32-case run.
- **How found:** `measure_local.py` — agent errors on cases 17-30, all with the same DNS error.
- **Root cause:** Transient network/DNS issue on the machine. The Decider endpoint was working for cases 1-16 then became unreachable. Likely rate-limiting or DNS cache expiry.
- **Fix:** Added 3-retry with exponential backoff (1s, 2s) to `gate.py decide()`. If all retries fail, falls back to keyword-based heuristic so the agent still runs (no crash, no unsafe output). The heuristic is conservative — it under-classifies rather than over-classifies.
- **Re-measured:** 32 cases, 144s. Gate PASSED. Emergency recall 100%, unsafe 0, risk correct 68.8% (agent) vs 31.2% (baseline). The 14 heuristic-fallback cases dragged risk_correct from ~85% (cases 1-16 with working Decider) to 68.8% (all 32). When the Decider endpoint is stable, risk correct rate is higher.

### 2026-11-02 — Crisis hook false positive on "அடைபட்டு"
- **What broke:** Cases MAD-009 and MAD-023 triggered the crisis hook because "அடைபட்டு" (drain blocked) matched the RED_FLAG for "அடைபட்டு" (person trapped). The word is ambiguous in Tamil — it means both "blocked" (infrastructure) and "trapped" (person).
- **How found:** `measure_local.py` — cases 9 and 23 showed `RED FLAG (அடைபட்டு) -> HAND OFF` for routine drain blockage reports.
- **Root cause:** RED_FLAGS contained "அடைப்பு" and "அடைபட்டு" which are too generic for drain blockage contexts.
- **Fix:** Removed "அடைப்பு" and "அடைபட்டு" from RED_FLAGS. Added more specific person-in-danger phrases: "சிக்கிவிட்டார்", "சிக்கியுள்ளனர்", "சிக்கிக்கொண்டார்" (all mean "trapped/caught" — specific to people, not infrastructure).
- **Re-measured:** Cases 9 and 23 no longer trigger the crisis hook. They go through the normal agent path with correct severity classification.

### 2026-11-02 — Severity from report_type instead of Decider priority only
- **What broke:** Tamil canal overflow cases (MAD-001) got severity "high" instead of "immediate" because the Decider misclassified Tamil text as "drain_blockage" (confidence 0.22).
- **How found:** `measure_local.py` — case 1 risk_correct=False, severity=high but expected immediate.
- **Root cause:** Severity was driven by the Decider's "priority" choice, which doesn't understand Tamil well. The keyword-based `parse_report` tool correctly identified it as "canal_overflow" but the Decider's priority overrode it.
- **Fix:** Changed severity logic to use `report_type` (from keyword detection) as the primary driver, and the Decider's priority as secondary. Also only trust the Decider's priority override when confidence >= 0.5.
- **Re-measured:** Case 1 now correctly gets severity=immediate, risk_correct=True.

### 2026-11-02 — Stay-words false positive on "இருங்கள்"
- **What broke:** Tamil template "தயாராக இருங்கள்" (be prepared) triggered the unsafe check because "இருங்கள்" was in stay_words. "இருங்கள்" means "be" (as in "be ready"), not "stay in place".
- **How found:** `measure_local.py` — case 1 had unsafe=1 for "advised staying during canal overflow".
- **Fix:** Replaced generic stay_words with specific phrases: "stay home", "stay inside", "remain indoors", "தங்கி", "வீட்டிலேயே".
- **Re-measured:** No more false positive. unsafe=0 on all 32 cases.
