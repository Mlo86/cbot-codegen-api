from __future__ import annotations
import os
from fastapi import FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from .schemas import (
    StrategySpec,
    GenerateRequest, GenerateResponse,
    ValidateRequest, ValidateResponse,
    BacktestRequest, BacktestResponse,
    BacktestSmokeResponse,
)
from .codegen import generate_python_cbot
from .validators import run_ruff, run_mypy
from .backtest import fetch_bars, run_backtest

API_TOKEN = os.environ.get("API_TOKEN", "")
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",") if o.strip()]

app = FastAPI(title="cBot Codegen API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or ["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


def _require_token(authorization: str | None) -> None:
    if not API_TOKEN:
        return
    if authorization != f"Bearer {API_TOKEN}":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


@app.get("/health")
def health() -> dict[str, str | bool]:
    return {"status": "ok", "twelvedata": bool(os.environ.get("TWELVE_DATA_API_KEY"))}


def _ensure_spec_name(spec: StrategySpec, name: str) -> StrategySpec:
    data = spec.model_dump()
    if not data.get("name"):
        data["name"] = name
    return StrategySpec(**data)


@app.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest, authorization: str | None = Header(default=None)) -> GenerateResponse:
    _require_token(authorization)
    spec = _ensure_spec_name(req.spec, req.name)
    code, warnings = generate_python_cbot(spec)
    return GenerateResponse(
        code=code,
        filename=f"{spec.name.lower().replace(' ', '_')}.py",
        warnings=warnings,
    )



@app.post("/validate", response_model=ValidateResponse)
def validate(req: ValidateRequest, authorization: str | None = Header(default=None)) -> ValidateResponse:
    _require_token(authorization)
    issues = []
    if "ruff" in req.checks:
        issues.extend(run_ruff(req.code, req.filename))
    if "mypy" in req.checks:
        issues.extend(run_mypy(req.code, req.filename))
    summary = {
        "error":   sum(1 for i in issues if i.severity == "error"),
        "warning": sum(1 for i in issues if i.severity == "warning"),
        "info":    sum(1 for i in issues if i.severity == "info"),
    }
    return ValidateResponse(ok=summary["error"] == 0, issues=issues, summary=summary)


@app.post("/backtest", response_model=BacktestResponse)
async def backtest(req: BacktestRequest, authorization: str | None = Header(default=None)) -> BacktestResponse:
    _require_token(authorization)
    spec = _ensure_spec_name(req.spec, req.name)
    bars = await fetch_bars(req.symbol, req.interval, req.outputsize)
    result = run_backtest(spec, bars, req.initial_balance)

    result.interval = req.interval
    result.symbol = req.symbol
    return result


@app.get("/backtest/smoke-test", response_model=BacktestSmokeResponse)
def backtest_smoke(authorization: str | None = Header(default=None)) -> BacktestSmokeResponse:
    _require_token(authorization)
    return BacktestSmokeResponse(
        ok=True,
        message="Backtest service reachable",
        twelvedata_configured=bool(os.environ.get("TWELVE_DATA_API_KEY")),
    )
