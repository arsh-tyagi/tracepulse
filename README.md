# TracePulse

[![Build & Tests](https://img.shields.io/badge/tests-7%2F7%20passing-brightgreen.svg)]()
[![C++](https://img.shields.io/badge/probe--daemon-C%2B%2B20-blue.svg)]()
[![FastAPI](https://img.shields.io/badge/backend-FastAPI%20%7C%20Python%203.11%2B-009688.svg)]()
[![Database](https://img.shields.io/badge/storage-MySQL%208.0%20%2F%20SQLite-4479A1.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()

> High-throughput synthetic API & health monitoring engine with a multi-threaded C++ probe daemon, FastAPI control plane, composite-indexed time-series storage, and a real-time dark-mode telemetry dashboard.

---

## Overview

**TracePulse** is a distributed synthetic monitoring platform engineered for low-overhead, high-frequency endpoint health verification. Traditional synthetic tools either carry heavy resource requirements or lack granular network phase breakdowns. TracePulse separates probe execution from the control plane:

1. A **multi-threaded C++ probe daemon** continuously benchmarks target APIs and web services using `libcurl` and native worker thread pools, capturing microsecond-level timing decomposition across DNS lookup, TCP connect, TLS handshake, and Time to First Byte (TTFB).
2. An asynchronous **FastAPI control plane** handles monitor lifecycle management, high-throughput batch ingestion, rolling SLA windowed analytics, and sub-2-second alert evaluations.
3. A **MySQL 8.0 time-series schema** equipped with composite indexing on `(monitor_id, checked_at DESC)` delivers sub-10ms analytical queries across large datasets.
4. A **real-time dark-mode telemetry dashboard** streams live probe metrics and incident states using Server-Sent Events (SSE) and Chart.js with zero frontend build dependencies.

---

## System Architecture

```
                             +-----------------------------------------------+
                             |    Frontend Dashboard (HTML5/Tailwind/CSS)    |
                             |       - Real-time Chart.js Decomposition      |
                             |       - SSE Telemetry EventSource Listener    |
                             +-----------------------+-----------------------+
                                                     ^
                                     Server-Sent     |    REST Management
                                     Events (SSE)    |    & Trigger APIs
                                                     v
                             +-----------------------------------------------+
                             |      FastAPI Asynchronous Control Plane       |
                             |       - Rolling SLA Engine (24h / 7d / 30d)   |
                             |       - Alert State Machine & Webhooks        |
                             |       - Ingestion Buffer & Validation Guards  |
                             +---------------+---------------+---------------+
                                             |               ^
                             SQLAlchemy 2.0  |               |  High-Speed JSON Batch
                             Async Pool      |               |  Ingestion Pipeline
                                             v               |
                             +---------------+----+   +------+-----------------------+
                             |  MySQL 8.0 Storage |   |  C++ Probe Daemon Engine     |
                             |  (Composite Index) |   |  - libcurl Multi-Worker Core |
                             +--------------------+   |  - std::jthread Worker Pool  |
                                                      +--------------+---------------+
                                                                     |
                                                            Microsecond Probes
                                                                     v
                                                        [ Target APIs & Services ]
```

---

## Microsecond Latency Decomposition

TracePulse instruments HTTP/HTTPS requests at microsecond resolution (`uint64_t` / `BIGINT`) via `libcurl` information structures:

$$\text{DNS Lookup Time} = \text{CURLINFO\_NAMELOOKUP\_TIME\_T}$$
$$\text{TCP Connect Time} = \text{CURLINFO\_CONNECT\_TIME\_T} - \text{CURLINFO\_NAMELOOKUP\_TIME\_T}$$
$$\text{TLS Handshake Time} = \text{CURLINFO\_APPCONNECT\_TIME\_T} - \text{CURLINFO\_CONNECT\_TIME\_T}$$
$$\text{Time to First Byte (TTFB)} = \text{CURLINFO\_STARTTRANSFER\_TIME\_T} - \text{CURLINFO\_APPCONNECT\_TIME\_T}$$
$$\text{Total Duration} = \text{CURLINFO\_TOTAL\_TIME\_T}$$

All timing calculations are executed in memory before batching, preventing floating-point precision loss.

---

## Key Features

- **Multi-Threaded Probe Engine**: Built in C++20 with `std::jthread` task queues and thread-safe ring buffers. Emits non-blocking asynchronous requests with zero signal contention (`CURLOPT_NOSIGNAL = 1L`).
- **Decoupled Batch Ingestion**: Probe metrics are buffered locally and flushed in bulk to `/api/v1/internal/ingest`, isolating probing from database locking or connection saturation.
- **SLA & Percentile Analytics**: On-demand calculation of rolling 24-hour, 7-day, and 30-day availability percentages alongside P50, P90, P95, and P99 latency distribution percentiles.
- **Incident State Machine**: Tracks transitions between `OK`, `ALERTING`, and `RESOLVED` states. Automatically opens incidents upon threshold breach (consecutive 5xx errors, latency thresholds, or status code mismatch) and dispatches webhooks to Slack, Discord, or custom HTTP endpoints.
- **Security & Integrity Controls**:
  - **SSRF Prevention**: Strict URL validation blocking non-HTTP schemes (`file://`, `gopher://`, etc.) and cloud metadata addresses (`169.254.169.254`, `metadata.google.internal`).
  - **CRLF Injection Prevention**: Header sanitation rejecting newline characters in key-value pairs.
  - **SQL Injection Immunity**: 100% parameterized queries via SQLAlchemy 2.0 ORM.
  - **Zero-Build Frontend**: Plain HTML5, Tailwind CSS, and Chart.js delivered directly via FastAPI static mounts without Node.js or `npm` build step vulnerabilities.

---

## Repository Structure

```
├── backend/
│   ├── app/
│   │   ├── models/            # SQLAlchemy ORM models (Monitor, CheckRun, AlertRule, Incident)
│   │   ├── routers/           # API endpoints (monitors, internal, metrics, rules, sse, health)
│   │   ├── schemas/           # Pydantic validation schemas with security filters
│   │   ├── services/          # Analytics, SLA calculator, alert dispatcher, probe runners
│   │   ├── config.py          # Environment settings with auto-fallback
│   │   ├── database.py        # Async engine & session lifecycle
│   │   └── main.py            # FastAPI application factory
│   ├── Dockerfile             # Backend container definition
│   ├── Dockerfile.mock        # Mock test target container definition
│   └── requirements.txt       # Python dependencies
├── db/
│   └── init.sql               # Production MySQL 8.0 schema & composite indexes
├── frontend/
│   ├── index.html             # Telemetry dark-mode dashboard
│   └── static/
│       ├── css/style.css      # Pulse animations and dark theme styles
│       └── js/
│           ├── app.js         # Dashboard controller & monitor grid manager
│           ├── charts.js      # Chart.js latency decomposition visualizer
│           └── sse_listener.js# EventSource real-time stream listener
├── probe-daemon/
│   ├── include/               # C++ header declarations (client, pool, queue, config)
│   ├── src/                   # C++ probe implementations
│   ├── CMakeLists.txt         # Modern C++20 build specification
│   └── Dockerfile             # Multi-stage C++ container build
├── tests/
│   ├── mock_target.py         # Fault injection server (/ok, /slow, /flaky, /down)
│   ├── test_e2e_benchmark.py  # Performance, batch ingestion & SLA benchmark
│   ├── test_phase1.py         # CRUD, database & probe execution tests
│   ├── test_phase2.py         # C++ / libcurl microsecond timing validation
│   ├── test_phase3.py         # Percentiles, rolling SLA & incident lifecycle tests
│   └── test_security_audit.py # SSRF, CRLF, and SQL injection security suite
├── docker-compose.yml         # Multi-container orchestration definition
└── README.md
```

---

## Quickstart

### Option 1: Docker Compose (Production Environment)

Clone the repository and launch the multi-service stack:

```bash
git clone https://github.com/arsh-tyagi/tracepulse.git
cd tracepulse
docker compose up --build
```

Services exposed:
- **Telemetry Dashboard**: [http://localhost:8000](http://localhost:8000)
- **API Documentation (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Mock Fault-Injection Target**: [http://localhost:8080](http://localhost:8080)
- **MySQL Database**: `localhost:3306`

---

### Option 2: Native Local Development

1. **Install Python Dependencies**:
   ```bash
   pip install -r backend/requirements.txt
   ```

2. **Start the Control Plane**:
   ```bash
   python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
   *Note: If a local MySQL server is not running on port 3306, TracePulse automatically initializes a local SQLite database (`tracepulse.db`), allowing immediate zero-configuration local execution.*

3. **Start the Probe Worker**:
   Run the high-concurrency synthetic probe worker in a separate terminal:
   ```bash
   python backend/app/services/probe_daemon.py
   ```
   Or compile and run the native C++ daemon:
   ```bash
   cd probe-daemon
   mkdir build && cd build
   cmake .. && cmake --build .
   ./probe_daemon http://127.0.0.1:8000
   ```

4. **Access the Dashboard**:
   Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

---

## API Reference

### Monitors API
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/monitors` | List all configured synthetic monitors with latest health status. |
| `POST` | `/api/v1/monitors` | Create a new monitor with interval, timeout, and expected status. |
| `GET` | `/api/v1/monitors/{id}` | Retrieve configuration and latest check run for a specific monitor. |
| `PUT` | `/api/v1/monitors/{id}` | Update monitor parameters (interval, headers, timeout). |
| `DELETE` | `/api/v1/monitors/{id}` | Delete a monitor and cascade delete its historical check runs. |
| `POST` | `/api/v1/monitors/{id}/test` | Trigger an immediate, synchronous probe execution and return metrics. |

### Analytics & Telemetry API
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/monitors/{id}/metrics` | Retrieve timeseries breakdown (DNS, TCP, TLS, TTFB) for Chart.js. |
| `GET` | `/api/v1/monitors/{id}/sla` | Retrieve rolling SLA uptime compliance for 24h, 7d, and 30d windows. |
| `GET` | `/api/v1/monitors/{id}/percentiles` | Compute latency percentiles (P50, P90, P95, P99) and average TTFB. |
| `GET` | `/api/v1/events/stream` | Server-Sent Events (SSE) stream broadcasting real-time probe telemetry. |

### Alerting & Internal Ingestion
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/internal/ingest` | High-throughput batch ingestion endpoint called by probe daemons. |
| `GET` | `/api/v1/alerts/rules` | List all configured threshold and consecutive failure alert rules. |
| `POST` | `/api/v1/alerts/rules` | Create a new alert rule linked to a webhook destination. |
| `GET` | `/api/v1/alerts/incidents` | List outage incidents filtered by status (`OPEN`, `RESOLVED`, `ALL`). |
| `GET` | `/api/v1/health` | Service health, memory footprint, and database connectivity check. |

---

## Configuration

Environment variables can be defined in a `.env` file in the project root:

```ini
# Application Mode
ENVIRONMENT=development
DEBUG=True

# Database Configuration
DATABASE_URL=mysql+asyncmy://root:root@127.0.0.1:3306/tracepulse
SQLITE_FALLBACK_URL=sqlite+aiosqlite:///./tracepulse.db

# Ingestion Security
INTERNAL_INGEST_KEY=tp-internal-probe-secret

# Daemon Polling Defaults
DEFAULT_CHECK_INTERVAL_SEC=10
DEFAULT_TIMEOUT_MS=5000
ALERT_DISPATCH_TIMEOUT_SEC=3.0
```

---

## Testing & Verification

Run the test suite covering unit operations, timing precision, alert lifecycles, benchmarks, and security:

```bash
pytest tests/
```

### Performance Benchmarks
- **Batch Ingestion**: Ingests and persists 100 probe records in **~71.4ms** (~0.71ms per record).
- **Analytical Query Latency**: Windowed SLA uptime calculations execute in **< 10ms** on indexed tables.
- **Latency Percentile Calculation**: Computes P50, P90, P95, and P99 percentiles in **~3.1ms**.
- **Incident Dispatch**: Asynchronous webhook notification fires within **< 2 seconds** of detected breach.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
