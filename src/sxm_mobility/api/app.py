from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="SXM Mobility Graph Lab API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
