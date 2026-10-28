import asyncio
import random
from fastapi import FastAPI, Response, status
import uvicorn

app = FastAPI(title="TracePulse Mock Target & Fault Injector", version="1.0.0")

@app.get("/ok")
async def target_ok():
    """Returns 200 OK fast."""
    return {"status": "ok", "latency": "fast"}

@app.get("/slow")
async def target_slow():
    """Simulates high Time to First Byte (TTFB) delay (500ms)."""
    await asyncio.sleep(0.5)
    return {"status": "delayed", "latency": "500ms"}

@app.get("/flaky")
async def target_flaky(response: Response):
    """Fails 35% of the time with HTTP 500 to simulate flaky upstream microservices."""
    if random.random() < 0.35:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"error": "Internal upstream service fault"}
    return {"status": "ok", "flaky": False}

@app.get("/down")
async def target_down(response: Response):
    """Simulates a hard outage returning HTTP 503."""
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"error": "Service Temporarily Unavailable"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="warning")
