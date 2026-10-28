// TracePulse Main Dashboard Application Controller
let activeMonitors = [];
let currentInspectedMonitorId = null;

document.addEventListener('DOMContentLoaded', () => {
    loadDashboard();
    setupEventListeners();

    // Initialize real-time SSE listener
    const streamer = new SSETelemetryStreamer(handleLiveProbeResult);
    streamer.connect();
});

async function loadDashboard() {
    try {
        const response = await fetch('/api/v1/monitors');
        activeMonitors = await response.json();
        renderClusterOverview();
        renderMonitorsGrid();
    } catch (err) {
        console.error("Failed to load monitors:", err);
    }
}

function renderClusterOverview() {
    const totalCount = activeMonitors.length;
    let totalLatency = 0;
    let latencyCount = 0;
    let totalUptime = 0;
    let totalIncidents = 0;

    activeMonitors.forEach(m => {
        if (m.latest_latency_ms !== null) {
            totalLatency += m.latest_latency_ms;
            latencyCount++;
        }
        totalUptime += (m.uptime_24h_percent || 100);
        totalIncidents += (m.active_incidents_count || 0);
    });

    const avgLatency = latencyCount > 0 ? (totalLatency / latencyCount).toFixed(1) : 0;
    const avgUptime = totalCount > 0 ? (totalUptime / totalCount).toFixed(2) : 100;

    document.getElementById('stat-total-monitors').textContent = totalCount;
    document.getElementById('stat-avg-latency').textContent = `${avgLatency} ms`;
    document.getElementById('stat-sla').textContent = `${avgUptime}%`;
    document.getElementById('stat-incidents').textContent = totalIncidents;

    const clusterBadge = document.getElementById('cluster-status-indicator');
    if (totalIncidents > 0) {
        clusterBadge.className = "flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-rose-500/20 text-rose-400 border border-rose-500/30";
        clusterBadge.innerHTML = `<span class="w-2 h-2 rounded-full bg-rose-500 animate-pulse"></span> Active Outage Detected`;
    } else {
        clusterBadge.className = "flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30";
        clusterBadge.innerHTML = `<span class="w-2 h-2 rounded-full bg-emerald-500 pulse-operational"></span> All Systems Operational`;
    }
}

function renderMonitorsGrid() {
    const container = document.getElementById('monitors-grid');
    if (!container) return;

    if (activeMonitors.length === 0) {
        container.innerHTML = `
            <div class="col-span-full text-center py-12 text-gray-500">
                <p class="text-lg">No endpoints configured yet.</p>
                <p class="text-sm">Click "+ Create Monitor" above to add your first synthetic target.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = activeMonitors.map(m => {
        let pulseClass = "pulse-operational bg-emerald-500";
        let statusText = "Operational";
        let statusBadgeColor = "text-emerald-400 bg-emerald-500/10 border-emerald-500/30";

        if (m.active_incidents_count > 0 || (m.latest_status_code && m.latest_status_code >= 500)) {
            pulseClass = "pulse-outage bg-rose-500";
            statusText = "Outage";
            statusBadgeColor = "text-rose-400 bg-rose-500/10 border-rose-500/30";
        } else if (m.latest_latency_ms && m.latest_latency_ms > 400) {
            pulseClass = "pulse-degraded bg-amber-500";
            statusText = "High Latency";
            statusBadgeColor = "text-amber-400 bg-amber-500/10 border-amber-500/30";
        }

        const latencyDisplay = m.latest_latency_ms ? `${m.latest_latency_ms} ms` : "Pending";
        const statusDisplay = m.latest_status_code || "---";

        return `
            <div id="card-monitor-${m.id}" class="bg-[#111827] border border-gray-800 hover:border-gray-700 transition rounded-xl p-5 shadow-lg flex flex-col justify-between">
                <div>
                    <div class="flex items-center justify-between mb-3">
                        <div class="flex items-center gap-2.5">
                            <span class="w-3 h-3 rounded-full ${pulseClass}"></span>
                            <h3 class="font-semibold text-gray-100 text-base">${escapeHtml(m.name)}</h3>
                        </div>
                        <span class="text-xs px-2 py-0.5 rounded border ${statusBadgeColor} font-mono">${statusText}</span>
                    </div>

                    <div class="text-xs font-mono text-gray-400 break-all mb-4 bg-gray-900/60 p-2 rounded border border-gray-800/80">
                        <span class="text-cyan-400 font-bold">${m.http_method}</span> ${escapeHtml(m.target_url)}
                    </div>

                    <div class="grid grid-cols-3 gap-2 py-2 border-y border-gray-800/80 text-center mb-4">
                        <div>
                            <div class="text-[11px] text-gray-400 uppercase tracking-wider">Latency</div>
                            <div id="val-latency-${m.id}" class="text-sm font-semibold text-gray-200 mt-0.5">${latencyDisplay}</div>
                        </div>
                        <div>
                            <div class="text-[11px] text-gray-400 uppercase tracking-wider">Status</div>
                            <div id="val-status-${m.id}" class="text-sm font-semibold text-gray-200 mt-0.5">${statusDisplay}</div>
                        </div>
                        <div>
                            <div class="text-[11px] text-gray-400 uppercase tracking-wider">24h SLA</div>
                            <div class="text-sm font-semibold text-emerald-400 mt-0.5">${m.uptime_24h_percent || 100}%</div>
                        </div>
                    </div>
                </div>

                <div class="flex items-center justify-between pt-2">
                    <span class="text-[11px] text-gray-500">Interval: ${m.check_interval_sec}s</span>
                    <div class="flex items-center gap-2">
                        <button onclick="testMonitorNow(${m.id})" id="btn-test-${m.id}" class="px-2.5 py-1 text-xs font-medium rounded bg-gray-800 hover:bg-gray-700 text-gray-300 transition flex items-center gap-1">
                            <span>Check Now</span>
                        </button>
                        <button onclick="inspectTelemetry(${m.id})" class="px-2.5 py-1 text-xs font-medium rounded bg-cyan-600/20 hover:bg-cyan-600/30 text-cyan-400 border border-cyan-500/30 transition">
                            Telemetry
                        </button>
                        <button onclick="deleteMonitor(${m.id})" class="px-2 py-1 text-xs font-medium rounded text-gray-500 hover:text-rose-400 transition" title="Delete">
                            🗑️
                        </button>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

function handleLiveProbeResult(data) {
    const monitorId = data.monitor_id;
    const latencyMs = (data.total_duration_us / 1000.0).toFixed(1);
    
    // Update monitor in local array
    const mon = activeMonitors.find(m => m.id === monitorId);
    if (mon) {
        mon.latest_latency_ms = parseFloat(latencyMs);
        mon.latest_status_code = data.status_code;
    }

    const latencyEl = document.getElementById(`val-latency-${monitorId}`);
    if (latencyEl) {
        latencyEl.textContent = `${latencyMs} ms`;
        latencyEl.classList.add('text-cyan-400');
        setTimeout(() => latencyEl.classList.remove('text-cyan-400'), 1000);
    }

    const statusEl = document.getElementById(`val-status-${monitorId}`);
    if (statusEl) {
        statusEl.textContent = data.status_code;
    }

    // If modal is currently open for this monitor, refresh metrics
    if (currentInspectedMonitorId === monitorId) {
        fetchAndRenderModalMetrics(monitorId);
    }
}

async function testMonitorNow(monitorId) {
    const btn = document.getElementById(`btn-test-${monitorId}`);
    if (btn) {
        btn.innerHTML = `<span class="animate-spin">⏳</span> Probing...`;
        btn.disabled = true;
    }

    try {
        const resp = await fetch(`/api/v1/monitors/${monitorId}/test`, { method: 'POST' });
        const result = await resp.json();
        handleLiveProbeResult(result);
    } catch (err) {
        console.error("Test probe failed:", err);
    } finally {
        if (btn) {
            btn.innerHTML = `<span>Check Now</span>`;
            btn.disabled = false;
        }
    }
}

async function inspectTelemetry(monitorId) {
    currentInspectedMonitorId = monitorId;
    const modal = document.getElementById('telemetry-modal');
    modal.classList.remove('hidden');

    const mon = activeMonitors.find(m => m.id === monitorId);
    document.getElementById('modal-title').textContent = mon ? mon.name : `Monitor #${monitorId}`;
    document.getElementById('modal-target-url').textContent = mon ? `${mon.http_method} ${mon.target_url}` : "";

    await fetchAndRenderModalMetrics(monitorId);
}

async function fetchAndRenderModalMetrics(monitorId) {
    try {
        // Fetch Timeseries
        const tsResp = await fetch(`/api/v1/monitors/${monitorId}/metrics?limit=30`);
        const tsData = await tsResp.json();
        renderTelemetryChart('telemetry-chart', tsData.data);

        // Fetch SLA
        const slaResp = await fetch(`/api/v1/monitors/${monitorId}/sla`);
        const slaData = await slaResp.json();
        if (slaData.sla) {
            document.getElementById('modal-sla-24h').textContent = `${slaData.sla['24h'].uptime_percent}%`;
            document.getElementById('modal-sla-7d').textContent = `${slaData.sla['7d'].uptime_percent}%`;
            document.getElementById('modal-sla-30d').textContent = `${slaData.sla['30d'].uptime_percent}%`;
        }

        // Fetch Percentiles
        const pResp = await fetch(`/api/v1/monitors/${monitorId}/percentiles?hours=24`);
        const pData = await pResp.json();
        if (pData.percentiles) {
            document.getElementById('modal-p50').textContent = `${pData.percentiles.p50_ms} ms`;
            document.getElementById('modal-p90').textContent = `${pData.percentiles.p90_ms} ms`;
            document.getElementById('modal-p99').textContent = `${pData.percentiles.p99_ms} ms`;
            document.getElementById('modal-ttfb').textContent = `${pData.percentiles.avg_ttfb_ms} ms`;
        }

        // Render recent runs table
        renderModalTable(tsData.data);
    } catch (err) {
        console.error("Error fetching modal telemetry:", err);
    }
}

function renderModalTable(runs) {
    const tbody = document.getElementById('modal-runs-tbody');
    if (!tbody) return;

    if (!runs || runs.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="text-center py-6 text-gray-500 font-sans text-xs">
                    No telemetry records found. Click <strong>"Check Now"</strong> on this monitor to execute the first live probe.
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = runs.slice(-10).reverse().map(r => {
        const dt = r.checked_at ? new Date(r.checked_at).toLocaleTimeString() : '---';
        const badgeColor = r.is_success ? "text-emerald-400 bg-emerald-500/10" : "text-rose-400 bg-rose-500/10";
        return `
            <tr class="border-b border-gray-800 text-xs">
                <td class="py-2 text-gray-400 font-mono">${dt}</td>
                <td class="py-2"><span class="px-1.5 py-0.5 rounded font-mono ${badgeColor}">${r.status_code}</span></td>
                <td class="py-2 text-gray-200 font-mono">${r.dns_ms} ms</td>
                <td class="py-2 text-gray-200 font-mono">${r.tcp_ms} ms</td>
                <td class="py-2 text-gray-200 font-mono">${r.tls_ms} ms</td>
                <td class="py-2 text-amber-400 font-mono font-medium">${r.ttfb_ms} ms</td>
                <td class="py-2 text-gray-100 font-mono font-semibold">${r.total_ms} ms</td>
                <td class="py-2 text-gray-500 truncate max-w-xs">${escapeHtml(r.error || 'OK')}</td>
            </tr>
        `;
    }).join('');
}

async function deleteMonitor(monitorId) {
    if (!confirm("Are you sure you want to delete this monitor?")) return;
    try {
        await fetch(`/api/v1/monitors/${monitorId}`, { method: 'DELETE' });
        loadDashboard();
    } catch (err) {
        console.error("Delete failed:", err);
    }
}

function setupEventListeners() {
    // New Monitor Modal
    const createBtn = document.getElementById('btn-open-create-modal');
    const createModal = document.getElementById('create-modal');
    const closeCreateBtn = document.getElementById('btn-close-create-modal');
    const form = document.getElementById('create-monitor-form');

    if (createBtn) createBtn.addEventListener('click', () => createModal.classList.remove('hidden'));
    if (closeCreateBtn) closeCreateBtn.addEventListener('click', () => createModal.classList.add('hidden'));

    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const payload = {
                name: document.getElementById('form-name').value,
                target_url: document.getElementById('form-url').value,
                http_method: document.getElementById('form-method').value,
                check_interval_sec: parseInt(document.getElementById('form-interval').value),
                timeout_ms: parseInt(document.getElementById('form-timeout').value),
                expected_status: parseInt(document.getElementById('form-status').value)
            };

            try {
                const resp = await fetch('/api/v1/monitors', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                if (resp.ok) {
                    createModal.classList.add('hidden');
                    form.reset();
                    loadDashboard();
                } else {
                    alert("Failed to create monitor. Check input values.");
                }
            } catch (err) {
                console.error("Create failed:", err);
            }
        });
    }

    // Close Telemetry Modal
    const closeTelemetryBtn = document.getElementById('btn-close-telemetry-modal');
    if (closeTelemetryBtn) {
        closeTelemetryBtn.addEventListener('click', () => {
            document.getElementById('telemetry-modal').classList.add('hidden');
            currentInspectedMonitorId = null;
        });
    }
}

function escapeHtml(text) {
    if (!text) return '';
    return text.replace(/[&<>"']/g, function(m) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[m];
    });
}
