import asyncio
import time
import os
import sys
import logging
from typing import Dict, List, Any
import httpx

# Add root path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from backend.app.services.probe_service import execute_probe_sync
from backend.app.schemas.check_run import CheckRunCreate, BatchIngestRequest

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [PythonProbeWorker]: %(message)s")
logger = logging.getLogger("probe_worker")

class AsyncProbeDaemon:
    def __init__(self, control_plane_url: str = "http://127.0.0.1:8000", ingest_key: str = "tp-internal-probe-secret"):
        self.control_plane_url = control_plane_url
        self.ingest_key = ingest_key
        self.running = True
        self.batch_queue: List[Dict[str, Any]] = []
        self.queue_lock = asyncio.Lock()
        self.targets: List[Dict[str, Any]] = []
        self.next_check: Dict[int, float] = {}

    async def fetch_targets(self, client: httpx.AsyncClient):
        try:
            resp = await client.get(f"{self.control_plane_url}/api/v1/monitors/active/targets", timeout=5.0)
            if resp.status_code == 200:
                self.targets = resp.json()
                logger.info(f"Synchronized {len(self.targets)} active targets from control plane.")
        except Exception as e:
            logger.warning(f"Failed to fetch targets from control plane: {e}")

    async def probe_target(self, target: Dict[str, Any]):
        loop = asyncio.get_running_loop()
        # Execute probe in executor to prevent blocking async event loop
        result = await loop.run_in_executor(
            None,
            execute_probe_sync,
            target["url"],
            target.get("method", "GET"),
            target.get("headers_json"),
            target.get("body"),
            target.get("timeout_ms", 5000),
            target.get("expected_status", 200)
        )

        metric = {
            "monitor_id": target["id"],
            "status_code": result.status_code,
            "is_success": result.is_success,
            "dns_lookup_us": result.dns_lookup_us,
            "tcp_connect_us": result.tcp_connect_us,
            "tls_handshake_us": result.tls_handshake_us,
            "ttfb_us": result.ttfb_us,
            "total_duration_us": result.total_duration_us,
            "response_bytes": result.response_bytes,
            "error_message": result.error_message
        }
        
        logger.info(
            f"Probed ID {target['id']} ({target['url']}) -> Status: {metric['status_code']} "
            f"| Total: {round(metric['total_duration_us'] / 1000.0, 2)}ms (TTFB: {round(metric['ttfb_us'] / 1000.0, 2)}ms)"
        )

        async with self.queue_lock:
            self.batch_queue.append(metric)

    async def flusher_loop(self, client: httpx.AsyncClient):
        while self.running:
            await asyncio.sleep(0.5)
            batch = []
            async with self.queue_lock:
                if self.batch_queue:
                    batch = self.batch_queue[:50]
                    self.batch_queue = self.batch_queue[50:]

            if batch:
                payload = {"checks": batch}
                headers = {"x-probe-key": self.ingest_key}
                try:
                    resp = await client.post(
                        f"{self.control_plane_url}/api/v1/internal/ingest",
                        json=payload,
                        headers=headers,
                        timeout=5.0
                    )
                    if resp.status_code == 201:
                        logger.info(f"Flushed batch of {len(batch)} probe results.")
                    else:
                        logger.warning(f"Batch ingest rejected: {resp.status_code} - {resp.text}")
                except Exception as ex:
                    logger.warning(f"Failed to flush batch metrics: {ex}")
                    # Re-queue batch on transient failure
                    async with self.queue_lock:
                        self.batch_queue = batch + self.batch_queue

    async def run(self):
        logger.info(f"Starting Python Async Probe Daemon against {self.control_plane_url}")
        async with httpx.AsyncClient() as client:
            flusher_task = asyncio.create_task(self.flusher_loop(client))
            last_target_sync = 0.0

            try:
                while self.running:
                    now = time.monotonic()
                    if now - last_target_sync > 10.0:
                        await self.fetch_targets(client)
                        last_target_sync = now

                    for target in self.targets:
                        target_id = target["id"]
                        interval = target.get("interval_sec", 10)
                        if target_id not in self.next_check or now >= self.next_check[target_id]:
                            self.next_check[target_id] = now + interval
                            asyncio.create_task(self.probe_target(target))

                    await asyncio.sleep(0.2)
            except (asyncio.CancelledError, KeyboardInterrupt):
                logger.info("Daemon received stop signal.")
            finally:
                self.running = False
                await flusher_task

if __name__ == "__main__":
    url = os.getenv("CONTROL_PLANE_URL", "http://127.0.0.1:8000")
    daemon = AsyncProbeDaemon(control_plane_url=url)
    try:
        asyncio.run(daemon.run())
    except KeyboardInterrupt:
        print("\nShutdown complete.")
