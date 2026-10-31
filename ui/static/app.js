/* SoraiMozhi dashboard — client-side logic */

const consoleEl = document.getElementById("console");
const triageResult = document.getElementById("triageResult");
const priorityList = document.getElementById("priorityList");
const reportInput = document.getElementById("reportInput");
const submitBtn = document.getElementById("submitBtn");
const batchBtn = document.getElementById("batchBtn");
const emergencyAlert = document.getElementById("emergencyAlert");
const statsImmediate = document.getElementById("statImmediate");
const statsTotal = document.getElementById("statTotal");
const statsHandoffs = document.getElementById("statHandoffs");
const chips = document.querySelectorAll(".chip");
const zoneHint = document.getElementById("zoneHint");

// --- Console ---
function consoleLog(tag, text) {
    const line = document.createElement("div");
    line.className = "console-line";
    line.innerHTML = `<span class="tag tag-${tag}">${tag}</span> ${text}`;
    consoleEl.appendChild(line);
    consoleEl.scrollTop = consoleEl.scrollHeight;
}

function clearConsole() {
    consoleEl.innerHTML = "";
}

// --- Severity helpers ---
function severityClass(sev) {
    return { immediate: "badge-immediate", high: "badge-high",
             moderate: "badge-moderate", low: "badge-low" }[sev] || "badge-low";
}

function rankClass(rank) {
    if (rank === 1) return "rank-1";
    if (rank === 2) return "rank-2";
    if (rank === 3) return "rank-3";
    return "rank-default";
}

// --- Zone chips ---
chips.forEach(chip => {
    chip.addEventListener("click", () => {
        chips.forEach(c => c.classList.remove("chip-active"));
        chip.classList.add("chip-active");
        const zone = chip.dataset.zone;
        const lang = chip.dataset.lang;
        zoneHint.textContent = `Selected: ${chip.textContent.trim()}`;
        // Pre-fill a sample report for this zone
        const samples = {
            sellur_ta: "செல்லூர் பந்தால்குடி கால்வாய் நிரம்பி வழிகிறது",
            sellur_en: "Sellur Panthalkudi canal overflowing near tank",
            ss_colony_ta: "எஸ்.எஸ். காலனி வடிகால் குப்பையால் அடைபட்டுள்ளது",
            ss_colony_en: "SS Colony drain blocked by garbage, water rising",
            kalavasal_ta: "காலவாசல் சாலையில் தண்ணீர் நிற்கிறது, போக்குவரத்து நிறுத்தம்",
            kalavasal_en: "Kalavasal main road waterlogged, traffic stopped",
            villapuram_ta: "விலாபுரம் வடிகால் நிரம்பியுள்ளது, தெரு முழுவதும் தண்ணீர்",
            villapuram_en: "Villapuram UGD overflow, street fully waterlogged",
            mattuthavani_ta: "மத்துத்தவனி பேருந்து நிலைய அருகே தண்ணீர் நிற்கிறது",
            mattuthavani_en: "Mattuthavani bus stand area flooded, vehicles submerged",
            arapalayam_ta: "ஆரப்பாளையம் பாலத்தில் விரிசல், பாதுகாப்பாக இல்லை",
            arapalayam_en: "Arapalayam bridge cracks, water level rising",
        };
        const key = `${zone}_${lang || "en"}`;
        if (samples[key]) reportInput.value = samples[key];
    });
});

// --- Submit single report ---
submitBtn.addEventListener("click", async () => {
    const text = reportInput.value.trim();
    if (!text) { alert("Please enter a report."); return; }

    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner"></span> Processing...';
    clearConsole();
    consoleLog("plan", "Starting triage...");
    triageResult.innerHTML = "";
    emergencyAlert.style.display = "none";

    try {
        const resp = await fetch("/api/triage", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text }),
        });
        const data = await resp.json();
        displayTriage(data);
    } catch (err) {
        consoleLog("safety", `ERROR: ${err.message}`);
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = "&#128205; Submit Report";
    }
});

// --- Submit batch (all zone samples) ---
batchBtn.addEventListener("click", async () => {
    batchBtn.disabled = true;
    batchBtn.innerHTML = '<span class="spinner"></span> Processing batch...';
    clearConsole();
    consoleLog("plan", "Starting batch triage across all zones...");

    const samples = [
        "செல்லூர் பந்தால்குடி கால்வாய் நிரம்பி வழிகிறது, வெள்ளம் வீட்டுக்குள் நுழைகிறது",
        "SS Colony drain blocked by garbage, water rising on main street",
        "காலவாசல் சாலையில் தண்ணீர் நிற்கிறது, போக்குவரத்து நிறுத்தம்",
        "Villapuram UGD overflow, street fully waterlogged, need pump",
        "மத்துத்தவனி பகுதியில் வடிகால் சரியாக இல்லை, தண்ணீர் நிற்கிறது",
        "Arapalayam road slope wrong, water doesn't drain, floods for hours",
    ];

    try {
        const resp = await fetch("/api/triage-batch", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ reports: samples }),
        });
        const data = await resp.json();
        displayPriorityList(data);
    } catch (err) {
        consoleLog("safety", `ERROR: ${err.message}`);
    } finally {
        batchBtn.disabled = false;
        batchBtn.innerHTML = "&#9889; Batch Triage All Zones";
    }
});

// --- Display single triage result ---
function displayTriage(data) {
    const plan = data.plan;
    const meta = data.meta;

    if (meta.path === "handoff") {
        emergencyAlert.style.display = "block";
        emergencyAlert.textContent = "⚠️ LIFE-SAFETY EMERGENCY — Crisis hook activated, handed off to 108/1077";
        consoleLog("safety", `RED FLAG detected -> HAND OFF, agents cancelled`);
    }

    if (meta.decider_p_emergency !== undefined) {
        consoleLog("decider", `p_emergency ${meta.decider_p_emergency.toFixed(2)}, priority ${meta.decider_priority}`);
    }
    if (meta.passes) {
        consoleLog("critic", `planner pass ${meta.passes} -> checked`);
    }
    consoleLog("plan", `${meta.path} | ${meta.latency_ms} ms`);

    triageResult.innerHTML = `
        <div class="result-row">
            <span class="result-label">Zone</span>
            <span class="result-value">${plan.zone_name || plan.zone_id}</span>
        </div>
        <div class="result-row">
            <span class="result-label">Report Type</span>
            <span class="result-value">${plan.report_type}</span>
        </div>
        <div class="result-row">
            <span class="result-label">Severity</span>
            <span class="badge ${severityClass(plan.severity)}">${plan.severity}</span>
        </div>
        <div class="result-row">
            <span class="result-label">Language</span>
            <span class="result-value">${plan.language === "ta" ? "தமிழ்" : "English"}</span>
        </div>
        <div class="summary-box">
            <strong>Summary:</strong> ${plan.summary}
        </div>
        <div class="summary-box">
            <strong>Action:</strong> ${plan.recommended_action}
        </div>
        <div class="summary-box">
            <strong>Escalation:</strong> ${plan.escalation}
        </div>
        ${plan.citations && plan.citations.length > 0 ? `
        <div class="summary-box">
            <strong>Citations:</strong> ${plan.citations.join(", ")}
        </div>` : ""}
    `;
}

// --- Display priority list (batch) ---
function displayPriorityList(data) {
    const plan = data.plan;
    const meta = data.meta;

    statsImmediate.textContent = meta.immediate || 0;
    statsTotal.textContent = meta.count || 0;
    statsHandoffs.textContent = meta.crisis_handoffs || 0;

    consoleLog("plan", `batch | ${meta.count} reports | ${meta.immediate} immediate | ${meta.crisis_handoffs} handoffs | ${meta.latency_ms} ms`);
    if (meta.confirmed) consoleLog("guard", "AUTO-CONFIRM (measurement mode)");

    priorityList.innerHTML = `
        <div class="summary-box">
            <strong>தமிழ்:</strong> ${plan.summary_ta}
        </div>
        <div class="summary-box">
            <strong>English:</strong> ${plan.summary_en}
        </div>
    `;

    plan.items.forEach(item => {
        priorityList.innerHTML += `
            <div class="priority-item">
                <div class="priority-rank ${rankClass(item.rank)}">${item.rank}</div>
                <div class="priority-content">
                    <div class="priority-zone">${item.zone_name} <span class="badge ${severityClass(item.severity)}" style="font-size:0.7rem;padding:0.15rem 0.5rem;">${item.severity}</span></div>
                    <div class="priority-reason">${item.reason}</div>
                    <div class="priority-action">→ ${item.action}</div>
                </div>
            </div>
        `;
    });
}

// --- Keyboard shortcut: Ctrl+Enter to submit ---
reportInput.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") submitBtn.click();
});
