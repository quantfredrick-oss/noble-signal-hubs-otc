"""Read-only OTCharts proxy for Noble Signal Hubs.
The OTCharts key is supplied per request by the browser and is never persisted here.
"""
import os
from typing import Optional
import httpx
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Noble Signal Hubs OTC API", version="1.0.0")
allowed_origins = [x.strip() for x in os.getenv("ALLOWED_ORIGINS", "*").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)
BASE = "https://otcharts.com"
VALID_TFS = {5, 15, 30, 60, 120, 180, 300, 600, 900, 1800, 3600, 14400}

async def otcharts_get(path: str, key: Optional[str], params: dict | None = None):
    if not key or not key.strip():
        raise HTTPException(status_code=401, detail="Enter your OTCharts API key.")
    headers = {"Authorization": "Bearer " + key.strip(), "Accept": "application/json", "User-Agent": "NobleSignalHubs/1.0"}
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=False) as client:
            response = await client.get(BASE + path, headers=headers, params=params)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach OTCharts: {exc.__class__.__name__}.")
    try:
        data = response.json()
    except ValueError:
        data = {"error": response.text[:300] or "OTCharts returned a non-JSON response."}
    if response.status_code >= 400:
        detail = data.get("error") or data.get("detail") or f"OTCharts returned HTTP {response.status_code}."
        raise HTTPException(status_code=response.status_code, detail=detail)
    return data

@app.get("/")
def home():
    return FileResponse(Path(__file__).with_name("Noble_Signal_Hubs_OTC.html"))

@app.get("/health")
def health():
    return {"status": "ok", "service": "Noble Signal Hubs OTC proxy", "read_only": True}

@app.get("/api/otc/symbols")
async def symbols(x_otcharts_key: Optional[str] = Header(default=None, alias="X-OTCharts-Key")):
    data = await otcharts_get("/v1/symbols", x_otcharts_key, {"venue": "otc"})
    return data

@app.get("/api/otc/candles")
async def candles(
    symbol: str = Query(..., min_length=3, max_length=40),
    tf: int = Query(60),
    limit: int = Query(600, ge=30, le=1500),
    x_otcharts_key: Optional[str] = Header(default=None, alias="X-OTCharts-Key"),
):
    if not symbol.endswith("_otc"):
        raise HTTPException(status_code=400, detail="Only Pocket Option OTC symbols ending in _otc are accepted.")
    if tf not in VALID_TFS:
        raise HTTPException(status_code=400, detail=f"Unsupported Pocket Option OTC candle timeframe. Allowed seconds: {sorted(VALID_TFS)}")
    data = await otcharts_get("/v1/candles", x_otcharts_key, {"venue": "otc", "symbol": symbol, "tf": tf, "limit": limit})
    if not isinstance(data.get("candles"), list):
        raise HTTPException(status_code=502, detail="OTCharts response did not include a candles list.")
    return data
