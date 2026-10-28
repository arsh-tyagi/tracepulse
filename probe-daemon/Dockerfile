# Multi-stage C++ Build for TracePulse High-Throughput Probe Daemon
FROM debian:bookworm-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libcurl4-openssl-dev \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY CMakeLists.txt .
COPY include/ include/
COPY src/ src/

RUN mkdir -p build && cd build \
    && cmake -DCMAKE_BUILD_TYPE=Release .. \
    && cmake --build . -j$(nproc)

# Minimal Runtime Stage
FROM debian:bookworm-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    libcurl4 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /app/build/probe_daemon /app/probe_daemon

ENV CONTROL_PLANE_URL=http://backend:8000
ENV INTERNAL_INGEST_KEY=tp-internal-probe-secret

ENTRYPOINT ["/app/probe_daemon"]
