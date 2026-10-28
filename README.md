# TracePulse

TracePulse is a lightweight, open-source synthetic API and health monitoring tool. It pairs a multi-threaded C++ probe engine with a FastAPI backend and a dark-mode web dashboard to monitor endpoint uptime and network latencies in real time.

---

## How It Works

Most basic uptime monitors only check whether an endpoint returns HTTP 200. When an API slows down, it is hard to tell whether the delay came from DNS resolution, TLS negotiation, network congestion, or slow application processing (TTFB).

TracePulse breaks this down into four connected parts:

1. **Probe Engine (`probe-daemon`)**:
   - Built in C++20 using `libcurl` and `std::jthread` worker threads.
   - Measures detailed network timing using `curl_easy_getinfo` (`CURLINFO_*_TIME_T`):
     - **DNS Resolution**: Time spent resolving the target domain name.
     - **TCP Handshake**: Time to establish the TCP connection.
     - **TLS Handshake**: Time to complete SSL/TLS negotiation (for HTTPS).
     - **Time to First Byte (TTFB)**: Time until the server sends the first byte of response data.
     - **Total Duration**: End-to-end request time.
   - Buffers results in memory and sends them in batches to the backend over HTTP.
   - *Note: A mirrored Python worker (`backend/app/services/probe_daemon.py`) is also included so you can run the probe agent without compiling C++ locally.*

2. **Backend & Control Plane (`backend`)**:
   - Built with Python and FastAPI.
   - Manages CRUD operations for monitors and alerting rules.
   - Calculates rolling SLA uptime percentages for 24-hour, 7-day, and 30-day windows.
   - Computes latency percentiles (P50, P90, P95, P99).
   - Evaluates consecutive failure rules and triggers webhook notifications (Slack, Discord, or custom HTTP).
   - Broadcasts real-time probe results to web clients using Server-Sent Events (SSE).

3. **Storage (`db`)**:
   - Primary database: MySQL 8.0 with composite indexes on `(monitor_id, checked_at DESC)` for efficient time-series queries.
   - Automatic local fallback: If MySQL is not detected on startup, the backend automatically switches to SQLite (`tracepulse.db`) so you can run and test locally with zero configuration.

4. **Frontend Dashboard (`frontend`)**:
   - Served directly by FastAPI with zero Node.js / npm dependencies.
   - Dark-mode interface using Tailwind CSS and Chart.js.
   - Live status indicators (operational, degraded, outage) updated in real time via SSE.
   - Drill-down modal showing microsecond latency breakdowns and recent check history.

---

## Architecture Diagram

```
 +---------------------------------------------------------+
 |             Frontend Dashboard (HTML / CSS)             |
 |   - Real-time Chart.js latency decomposition graph      |
 |   - Server-Sent Events (SSE) live telemetry stream      |
 +----------------------------+----------------------------+
                              ^
              Server-Sent     |    REST API
              Events (SSE)    |    (CRUD & History)
                              v
 +---------------------------------------------------------+
 |                 FastAPI Backend Service                 |
 |   - Ingestion endpoint (/api/v1/internal/ingest)        |
 |   - SLA & Percentile calculator (24h, 7d, 30d)          |
 |   - Webhook dispatcher (Slack / Discord / Custom)       |
 +--------------+---------------------------+--------------+
                |                           ^
     SQLAlchemy |                           | Batch Ingest
     Async Pool |                           | (JSON)
                v                           |
 +--------------+------------+  +-----------+--------------+
 |     MySQL / SQLite DB     |  |  C++ Probe Daemon Worker |
 |  - monitors table         |  |   - libcurl HTTP checks  |
 |  - check_runs table       |  |   - Thread pool workers  |
 |  - alert_rules table      |  |   - Timing breakdown     |
 +---------------------------+  +-----------+--------------+
                                            |
                                   HTTP / HTTPS Probes
                                            v
                                  [ Target Endpoints ]
```

---

## Quickstart

### Option 1: Docker Compose

The fastest way to run the full stack (MySQL, FastAPI backend, C++ probe daemon, and mock test server):

```bash
# Clone the repository
git clone https://github.com/arsh-tyagi/tracepulse.git
cd tracepulse

# Start all services
docker compose up --build
```

Once started:
- **Web Dashboard**: [http://localhost:8000](http://localhost:8000)
- **API Documentation (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Mock Target Server**: [http://localhost:8080](http://localhost:8080) (provides `/ok`, `/slow`, `/flaky`, and `/down` endpoints for testing)

---

### Option 2: Running Locally (Development Mode)

If you prefer to run directly on your host machine without Docker:

#### 1. Start the Backend

```bash
# Install Python dependencies
pip install -r backend/requirements.txt

# Run the FastAPI server
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

*If MySQL is not running locally, TracePulse automatically creates a local SQLite database (`tracepulse.db`) so the server starts without error.*

#### 2. Start the Probe Worker

In a second terminal window, run the probe poller:

```bash
# Using the Python async worker
python backend/app/services/probe_daemon.py
```

Or build and run the C++ daemon (requires CMake and a C++20 compiler with `libcurl`):

```bash
cd probe-daemon
mkdir build && cd build
cmake ..
cmake --build .
./probe_daemon http://127.0.0.1:8000
```

#### 3. Open the Dashboard

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

---

## API Endpoints

### Monitors
- `GET /api/v1/monitors` — List all configured monitors with their latest status and 24h SLA.
- `POST /api/v1/monitors` — Create a new synthetic monitor.
- `GET /api/v1/monitors/{id}` — Get monitor configuration and latest check run.
- `PUT /api/v1/monitors/{id}` — Update monitor settings (interval, headers, timeout).
- `DELETE /api/v1/monitors/{id}` — Delete a monitor and its history.
- `POST /api/v1/monitors/{id}/test` — Run an immediate on-demand probe and return the timing breakdown.

### Analytics & Streaming
- `GET /api/v1/monitors/{id}/metrics?limit=30` — Get recent check timeseries data for charting.
- `GET /api/v1/monitors/{id}/sla` — Get rolling SLA uptime percentages (24h, 7d, 30d).
- `GET /api/v1/monitors/{id}/percentiles?hours=24` — Get P50, P90, P95, and P99 latency percentiles.
- `GET /api/v1/events/stream` — Server-Sent Events (SSE) stream for real-time dashboard updates.

### Alerting & Internal
- `POST /api/v1/internal/ingest` — Ingestion endpoint used by probe daemons to batch-upload check records.
- `GET /api/v1/alerts/rules` — List active alerting rules.
- `POST /api/v1/alerts/rules` — Create a new rule (consecutive failures, latency threshold, or status code mismatch).
- `GET /api/v1/alerts/incidents` — List open and resolved incidents.
- `GET /api/v1/health` — System status, memory usage, and database connectivity.

---

## Configuration

Settings can be customized using environment variables or a `.env` file in the root folder:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `DATABASE_URL` | `mysql+asyncmy://root:root@127.0.0.1:3306/tracepulse` | Primary MySQL connection string |
| `SQLITE_FALLBACK_URL` | `sqlite+aiosqlite:///./tracepulse.db` | Fallback SQLite database path |
| `INTERNAL_INGEST_KEY` | `tp-internal-probe-secret` | Shared secret header (`x-probe-key`) for daemon ingestion |
| `DEFAULT_CHECK_INTERVAL_SEC` | `10` | Default probe polling interval in seconds |
| `DEFAULT_TIMEOUT_MS` | `5000` | Default HTTP request timeout in milliseconds |
| `ALERT_DISPATCH_TIMEOUT_SEC` | `3.0` | Timeout for firing outbound webhook notifications |

---

## Security Considerations

- **SSRF Protection**: Target URLs are validated before saving. Non-HTTP protocols (`file://`, `ftp://`, `gopher://`) and cloud metadata IPs (`169.254.169.254`, `metadata.google.internal`) are blocked.
- **Header Injection Defense**: Custom headers are validated against CRLF characters (`\r`, `\n`) to prevent HTTP request splitting.
- **Parameterized Queries**: All database queries use SQLAlchemy 2.0 ORM expressions to prevent SQL injection.

---

## Running Tests

Run the test suite with pytest:

```bash
pytest tests/
```

This verifies monitor CRUD operations, libcurl timing parsing, alert state transitions, security validation rules, and end-to-end ingestion.

---

## License

This project is licensed under the [MIT License](LICENSE).
