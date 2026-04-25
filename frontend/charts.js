/* ════════════════════════════════════════════════════
   charts.js — Load Engine | Real-Time Network Monitor
════════════════════════════════════════════════════ */

/* ─── STATE ──────────────────────────────────────── */
let activeDevice = null;
let forecastChart = null;
let cpuRollChart = null;
let pollingTimers = [];

// Rolling live buffer — combines DB history + live readings
const MAX_POINTS = 40;
let liveBuffer = [];   // [{ time, cpu, predicted }]

const loadMap = { LOW: 1, MEDIUM: 2, HIGH: 3, "N/A": 0 };
function levelFromCpu(cpu) {
    if (cpu < 40) return "LOW";
    if (cpu < 70) return "MEDIUM";
    return "HIGH";
}

/* ════════════════════════════════════════════════════
   DEVICE PICKER
════════════════════════════════════════════════════ */

async function loadDevices() {
    const list = document.getElementById("device-list");
    list.innerHTML = `
    <div class="device-scanning">
      <div class="scan-ring"></div>
      <span>Scanning network…</span>
    </div>`;

    try {
        const res = await fetch("/devices");
        const devices = await res.json();
        list.innerHTML = "";

        if (!devices.length) {
            list.innerHTML = `
        <div class="no-devices">
          No devices detected yet.<br>
          Ask friends to run <strong>metrics_agent.py</strong> on their laptop.
        </div>`;
            return;
        }

        devices.forEach((dev, i) => {
            const btn = document.createElement("button");
            btn.className = "device-row";
            btn.style.animationDelay = (i * 0.07) + "s";

            const isLocal = dev.ip === "local";
            const online = dev.online || isLocal;

            let statusClass = online ? "status-online" : "status-offline";
            let statusText = online ? "● ONLINE" : "○ OFFLINE";
            if (isLocal) { statusClass = "status-self"; statusText = "★ THIS PC"; }

            btn.innerHTML = `
        <span class="device-icon">${isLocal ? "🖥️" : "💻"}</span>
        <span class="device-info">
          <span class="device-name">${escHtml(dev.name)}</span>
          <span class="device-ip">${isLocal ? "localhost" : dev.ip}</span>
        </span>
        <span class="device-status ${statusClass}">${statusText}</span>`;

            btn.onclick = () => selectDevice(dev);
            list.appendChild(btn);
        });

    } catch (err) {
        list.innerHTML = `
      <div class="no-devices">
        Cannot reach server.<br>
        Make sure <strong>api.py</strong> is running.
      </div>`;
    }
}

function selectDevice(dev) {
    activeDevice = dev;
    const label = dev.name;

    ["sidebar-device-name", "hdr-device", "lm-device", "hist-device"]
        .forEach(id => { const el = document.getElementById(id); if (el) el.textContent = label; });

    document.getElementById("picker").classList.add("hidden");
    document.getElementById("dashboard").classList.remove("hidden");

    resetState();
    showView("v-dashboard", document.getElementById("nav-dashboard"));
    startPolling();
}

function goBack() {
    pollingTimers.forEach(clearInterval);
    pollingTimers = [];
    activeDevice = null;
    resetState();

    document.getElementById("dashboard").classList.add("hidden");
    document.getElementById("picker").classList.remove("hidden");
    loadDevices();
}

function resetState() {
    liveBuffer = [];
    if (forecastChart) { forecastChart.destroy(); forecastChart = null; }
    if (cpuRollChart) { cpuRollChart.destroy(); cpuRollChart = null; }
    ["cpu-val", "mem-val", "proc-val", "pred-val", "lm-cpu", "lm-mem", "lm-procs"]
        .forEach(id => setText(id, "--"));
    const fh = document.getElementById("full-hist");
    if (fh) fh.innerHTML = "";
    document.getElementById("alloc-servers").innerHTML = `<div class="empty-processes">Awaiting telemetry...</div>`;
    document.getElementById("alloc-badge").textContent = "Waiting...";
    document.getElementById("alloc-badge").className = "alloc-badge badge-na";
}

/* ════════════════════════════════════════════════════
   NAVIGATION
════════════════════════════════════════════════════ */

function showView(viewId, navEl) {
    document.querySelectorAll(".view").forEach(v => v.classList.remove("active-view"));
    document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));
    const view = document.getElementById(viewId);
    if (view) view.classList.add("active-view");
    if (navEl) navEl.classList.add("active");
}

/* ════════════════════════════════════════════════════
   POLLING — tight intervals for continuous updates
════════════════════════════════════════════════════ */

function startPolling() {
    // seed from DB first
    seedFromDB();

    // then live metrics every 2.5 s
    fetchAndAppendMetrics();
    fetchAllocation();
    pollingTimers.push(setInterval(fetchAndAppendMetrics, 2500));
    pollingTimers.push(setInterval(fetchAllocation, 2500));

    // refresh DB history (for history tab) every 10 s
    pollingTimers.push(setInterval(seedFromDB, 10000));
}

/* ── Seed chart from DB history on load ─────────────────── */
async function seedFromDB() {
    try {
        const res = await fetch("/predicted-load");
        if (!res.ok) return;
        const rows = await res.json();
        if (!Array.isArray(rows) || !rows.length) return;

        // merge: if time already in liveBuffer skip, else prepend
        const existingTimes = new Set(liveBuffer.map(p => p.time));
        rows.forEach(r => {
            if (!existingTimes.has(r.time)) {
                liveBuffer.push({
                    time: r.time,
                    cpu: r.cpu ?? 0,
                    predicted: r.predicted ?? "N/A",
                    actual: r.actual ?? "N/A"
                });
            }
        });

        // keep sorted and trimmed
        liveBuffer.sort((a, b) => a.time.localeCompare(b.time));
        if (liveBuffer.length > MAX_POINTS) liveBuffer = liveBuffer.slice(-MAX_POINTS);

        redrawForecastChart();
        updateFullHistory();
    } catch (e) { /* ignore */ }
}

/* ── Live metric fetch → append to buffer ────────────────── */
async function fetchAndAppendMetrics() {
    if (!activeDevice) return;
    try {
        const res = await fetch(`/node-metrics/${activeDevice.ip}`);
        if (!res.ok) return;
        const data = await res.json();
        applyMetrics(data);
    } catch (e) { /* ignore */ }
}

function applyMetrics(data) {
    const cpu = Math.round(data.cpu ?? 0);
    const mem = Math.round(data.memory ?? 0);
    const proc = data.processes ?? "--";
    const ts = data.timestamp ?? new Date().toLocaleTimeString();
    const pred = levelFromCpu(cpu);

    // ── KPI ──────────────────────────────────────────────
    setText("cpu-val", cpu);
    setText("mem-val", mem);
    setText("proc-val", proc);
    setText("last-update", ts);
    setText("lm-cpu", cpu);
    setText("lm-mem", mem);
    setText("lm-procs", proc);

    // Predicted Load badge
    const predEl = document.getElementById("pred-val");
    if (predEl) {
        predEl.textContent = pred;
        predEl.style.color = pred === "LOW" ? "var(--status-success)" :
            pred === "HIGH" ? "var(--status-destructive)" : "var(--status-warning)";
    }

    // Progress bars
    setBar("cpu-bar", cpu, cpu > 75 ? "var(--status-destructive)" : cpu > 45 ? "var(--status-warning)" : "var(--foreground)");
    setBar("mem-bar", mem, mem > 80 ? "var(--status-destructive)" : mem > 60 ? "var(--status-warning)" : "var(--muted-foreground)");

    // Status text
    setStatus("cpu-status", cpu,
        ["✓ Optimal", "↑ Elevated", "⚠ Critical"],
        [40, 75], ["var(--status-success)", "var(--status-warning)", "var(--status-destructive)"]);
    setStatus("mem-status", mem,
        ["✓ Normal", "↑ Moderate", "⚠ Pressure"],
        [55, 80], ["var(--status-success)", "var(--status-warning)", "var(--status-destructive)"]);

    // ── Append live point to buffer ───────────────────────
    liveBuffer.push({ time: ts, cpu, predicted: pred, actual: pred });
    if (liveBuffer.length > MAX_POINTS) liveBuffer.shift();

    redrawForecastChart();
    updateCpuRollChart(ts, cpu);
}

/* ════════════════════════════════════════════════════
   SERVER ALLOCATION PANEL
════════════════════════════════════════════════════ */

async function fetchAllocation() {
    try {
        const res = await fetch("/server-allocation");
        if (!res.ok) return;
        const data = await res.json();
        renderAllocation(data);
    } catch (e) { /* ignore */ }
}

function renderAllocation(data) {
    const badge = document.getElementById("alloc-badge");
    const container = document.getElementById("alloc-servers");
    if (!badge || !container) return;

    const lvl = (data.load_level || "LOW").toLowerCase();
    badge.textContent = data.load_level;
    badge.className = `alloc-badge badge-${lvl}`;

    container.innerHTML = "";
    (data.servers || []).forEach(srv => {
        let procsHtml = srv.processes.map(p => `<span class="process-chip">${p}</span>`).join("");
        if (!procsHtml) procsHtml = `<div class="empty-processes">Idle (Zero tasks assigned)</div>`;

        const card = document.createElement("div");
        card.className = "server-card";
        card.innerHTML = `
            <div class="server-top">
                <span class="server-name">🖥️ ${srv.name}</span>
                <span class="server-load-pct">${srv.load_pct}%</span>
            </div>
            <div class="server-bar-track">
                <div class="server-bar-fill" style="width: ${srv.load_pct}%"></div>
            </div>
            <div class="server-processes">
                ${procsHtml}
            </div>
        `;
        container.appendChild(card);
    });
}

/* ════════════════════════════════════════════════════
   CHART: FORECAST (live-updating)
════════════════════════════════════════════════════ */

function redrawForecastChart() {
    const labels = liveBuffer.map(p => p.time);
    const predicted = liveBuffer.map(p => loadMap[p.predicted] ?? 0);
    const actual = liveBuffer.map(p => loadMap[p.actual] ?? 0);

    if (forecastChart) {
        forecastChart.data.labels = labels;
        forecastChart.data.datasets[0].data = predicted;
        forecastChart.data.datasets[1].data = actual;
        forecastChart.update("none");        // no animation on tick — feels live
        return;
    }

    const el = document.getElementById("forecastChart");
    if (!el) return;
    const ctx = el.getContext("2d");

    const gradBlue = ctx.createLinearGradient(0, 0, 0, 340);
    gradBlue.addColorStop(0, "rgba(250,250,250,0.1)");
    gradBlue.addColorStop(0.6, "rgba(250,250,250,0.02)");
    gradBlue.addColorStop(1, "rgba(250,250,250,0)");

    forecastChart = new Chart(ctx, {
        type: "line",
        data: {
            labels,
            datasets: [
                {
                    label: "Predicted",
                    data: predicted,
                    borderColor: "#fafafa",
                    backgroundColor: gradBlue,
                    borderWidth: 2,
                    pointBackgroundColor: "#fafafa",
                    pointBorderColor: "#18181b",
                    pointRadius: 3, pointHoverRadius: 6,
                    tension: 0.42, fill: true
                },
                {
                    label: "Actual",
                    data: actual,
                    borderColor: "#a1a1aa",
                    backgroundColor: "transparent",
                    borderWidth: 2,
                    borderDash: [5, 4],
                    pointBackgroundColor: "#a1a1aa",
                    pointRadius: 3, pointHoverRadius: 6,
                    tension: 0.42
                }
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            animation: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: "#09090b",
                    borderColor: "#27272a", borderWidth: 1,
                    titleColor: "#fafafa", bodyColor: "#a1a1aa",
                    padding: 14, cornerRadius: 8,
                    callbacks: {
                        label: ctx => {
                            const v = ctx.raw;
                            const name = Object.keys(loadMap).find(k => loadMap[k] === v) ?? "N/A";
                            return `   ${ctx.dataset.label}: ${name}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: "rgba(250,250,250,0.05)", drawBorder: false },
                    ticks: { color: "#a1a1aa", font: { size: 10 }, maxTicksLimit: 8, maxRotation: 0 }
                },
                y: {
                    min: 0, max: 4,
                    grid: { color: "rgba(250,250,250,0.05)", drawBorder: false },
                    ticks: {
                        color: "#a1a1aa", font: { size: 10 },
                        callback: v => Object.keys(loadMap).find(k => loadMap[k] === v) ?? ""
                    }
                }
            }
        }
    });
}

/* ════════════════════════════════════════════════════
   CHART: CPU ROLLING LINE
════════════════════════════════════════════════════ */

function updateCpuRollChart(ts, cpu) {
    if (cpuRollChart) {
        const d = cpuRollChart.data;
        d.labels.push(ts);
        d.datasets[0].data.push(cpu);
        if (d.labels.length > 30) {
            d.labels.shift();
            d.datasets[0].data.shift();
        }
        cpuRollChart.update("none");
        return;
    }

    const el = document.getElementById("cpuRollChart");
    if (!el) return;
    const ctx = el.getContext("2d");

    const grad = ctx.createLinearGradient(0, 0, 0, 340);
    grad.addColorStop(0, "rgba(250,250,250,0.1)");
    grad.addColorStop(1, "rgba(250,250,250,0)");

    cpuRollChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: [ts],
            datasets: [{
                label: "CPU %",
                data: [cpu],
                borderColor: "#fafafa",
                backgroundColor: grad,
                borderWidth: 2,
                tension: 0.4, pointRadius: 0, fill: true
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            animation: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: "#09090b",
                    borderColor: "#27272a", borderWidth: 1,
                    titleColor: "#fafafa", bodyColor: "#a1a1aa",
                    callbacks: { label: ctx => `   CPU: ${ctx.raw}%` }
                }
            },
            scales: {
                x: {
                    grid: { color: "rgba(250,250,250,0.05)" },
                    ticks: { color: "#a1a1aa", font: { size: 10 }, maxTicksLimit: 6, maxRotation: 0 }
                },
                y: {
                    min: 0, max: 100,
                    grid: { color: "rgba(250,250,250,0.05)" },
                    ticks: { color: "#a1a1aa", font: { size: 10 }, callback: v => v + "%" }
                }
            }
        }
    });
}

/* ════════════════════════════════════════════════════
   HISTORY TABLE
════════════════════════════════════════════════════ */

function updateFullHistory() {
    const el = document.getElementById("full-hist");
    if (!el) return;
    el.innerHTML = "";

    [...liveBuffer].reverse().forEach(d => {
        const level = (d.predicted || "na").toLowerCase();
        const row = document.createElement("div");
        row.className = "hist-row";
        row.innerHTML = `
      <span class="hist-time">${d.time}</span>
      <span class="hist-cpu">CPU ${d.cpu ?? "--"}%</span>
      <span class="badge badge-${level}">${d.predicted ?? "N/A"}</span>`;
        el.appendChild(row);
    });
}

/* ════════════════════════════════════════════════════
   HELPERS
════════════════════════════════════════════════════ */

function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
}

function setBar(id, pct, color) {
    const el = document.getElementById(id);
    if (!el) return;
    el.style.width = Math.min(Math.max(pct, 0), 100) + "%";
    el.style.backgroundColor = color; // Used to be just raw hex
}

function setStatus(id, val, labels, thresholds, colors) {
    const el = document.getElementById(id);
    if (!el) return;
    const idx = val > thresholds[1] ? 2 : val > thresholds[0] ? 1 : 0;
    el.textContent = labels[idx];
    el.style.color = colors[idx];
}

function escHtml(str) {
    return String(str)
        .replace(/&/g, "&amp;").replace(/</g, "&lt;")
        .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

/* ── INIT ─────────────────────────────────────────── */
loadDevices();