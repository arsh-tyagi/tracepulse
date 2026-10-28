// TracePulse Chart.js Latency Visualizer
let telemetryChartInstance = null;

function renderTelemetryChart(canvasId, timeseriesData) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    if (!timeseriesData || timeseriesData.length === 0) {
        if (telemetryChartInstance) {
            telemetryChartInstance.destroy();
            telemetryChartInstance = null;
        }
        return;
    }

    const labels = timeseriesData.map(d => {
        if (!d.checked_at) return '';
        const dt = new Date(d.checked_at);
        return dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    });

    const dnsData = timeseriesData.map(d => d.dns_ms);
    const tcpData = timeseriesData.map(d => d.tcp_ms);
    const tlsData = timeseriesData.map(d => d.tls_ms);
    const ttfbData = timeseriesData.map(d => d.ttfb_ms);
    const totalData = timeseriesData.map(d => d.total_ms);

    if (telemetryChartInstance) {
        telemetryChartInstance.destroy();
    }

    telemetryChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'TTFB (Time to First Byte)',
                    data: ttfbData,
                    borderColor: '#f59e0b', // Amber
                    backgroundColor: 'rgba(245, 158, 11, 0.15)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3
                },
                {
                    label: 'TLS Handshake',
                    data: tlsData,
                    borderColor: '#8b5cf6', // Purple
                    backgroundColor: 'rgba(139, 92, 246, 0.15)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3
                },
                {
                    label: 'TCP Connect',
                    data: tcpData,
                    borderColor: '#3b82f6', // Blue
                    backgroundColor: 'rgba(59, 130, 246, 0.15)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3
                },
                {
                    label: 'DNS Lookup',
                    data: dnsData,
                    borderColor: '#06b6d4', // Cyan
                    backgroundColor: 'rgba(6, 182, 212, 0.15)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        color: '#9ca3af',
                        font: { size: 12 }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.dataset.label}: ${context.parsed.y} ms`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: '#1f2937' },
                    ticks: { color: '#6b7280', maxTicksLimit: 8 }
                },
                y: {
                    grid: { color: '#1f2937' },
                    ticks: {
                        color: '#6b7280',
                        callback: function(value) { return value + ' ms'; }
                    },
                    beginAtZero: true
                }
            }
        }
    });
}
