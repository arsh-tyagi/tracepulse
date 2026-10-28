// TracePulse Real-Time Server-Sent Events (SSE) Listener
class SSETelemetryStreamer {
    constructor(onProbeResultCallback) {
        this.onProbeResult = onProbeResultCallback;
        this.eventSource = null;
        this.reconnectTimeout = null;
    }

    connect() {
        console.log("[SSE] Establishing live telemetry stream connection...");
        this.eventSource = new EventSource('/api/v1/events/stream');

        this.eventSource.addEventListener('connected', (e) => {
            console.log("[SSE] Connected to TracePulse stream:", e.data);
            const badge = document.getElementById('sse-status-badge');
            if (badge) {
                badge.textContent = "LIVE STREAM ACTIVE";
                badge.className = "text-xs font-semibold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30";
            }
        });

        this.eventSource.addEventListener('probe_result', (e) => {
            try {
                const data = JSON.parse(e.data);
                if (this.onProbeResult) {
                    this.onProbeResult(data);
                }
            } catch (err) {
                console.error("[SSE] Error parsing probe_result:", err);
            }
        });

        this.eventSource.onerror = (err) => {
            console.warn("[SSE] Connection interrupted. Reconnecting in 3 seconds...", err);
            const badge = document.getElementById('sse-status-badge');
            if (badge) {
                badge.textContent = "RECONNECTING...";
                badge.className = "text-xs font-semibold px-2 py-0.5 rounded bg-amber-500/20 text-amber-400 border border-amber-500/30";
            }
            this.eventSource.close();
            clearTimeout(this.reconnectTimeout);
            this.reconnectTimeout = setTimeout(() => this.connect(), 3000);
        };
    }
}
