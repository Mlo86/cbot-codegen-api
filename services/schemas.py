from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field


class StrategySpec(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    instrument: str | None = None
    timeframe: str | None = None
    entry: dict[str, Any] = Field(default_factory=dict)
    exit: dict[str, Any] = Field(default_factory=dict)
    risk: dict[str, Any] = Field(default_factory=dict)
    filters: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}



class GenerateRequest(BaseModel):
    name: str
    spec: StrategySpec



class GenerateResponse(BaseModel):
    code: str
    filename: str
    warnings: list[str] = []


class ValidateRequest(BaseModel):
    code: str
    filename: str = "cbot.py"
    checks: list[Literal["ruff", "mypy"]] = ["ruff", "mypy"]


class ValidationIssue(BaseModel):
    tool: str
    severity: Literal["error", "warning", "info"]
    line: int | None = None
    column: int | None = None
    code: str | None = None
    message: str


class ValidateResponse(BaseModel):
    ok: bool
    issues: list[ValidationIssue]
    summary: dict[str, int]


class BacktestRequest(BaseModel):
    name: str
    spec: StrategySpec
    symbol: str = "EUR/USD"

    interval: str = "1h"          # Twelve Data intervals: 1min, 5min, 15min, 1h, 4h, 1day
    outputsize: int = Field(default=500, ge=50, le=5000)
    initial_balance: float = 10_000.0


class Trade(BaseModel):
    side: Literal["buy", "sell"]
    entry_time: str
    entry_price: float
    exit_time: str
    exit_price: float
    pnl: float
    reason: Literal["tp", "sl", "signal", "end"]


class BacktestMetrics(BaseModel):
    trades: int
    wins: int
    losses: int
    win_rate: float
    total_pnl: float
    return_pct: float
    max_drawdown_pct: float
    sharpe: float
    final_balance: float


class BacktestResponse(BaseModel):
    symbol: str
    interval: str
    bars: int
    metrics: BacktestMetrics
    trades: list[Trade]
    equity_curve: list[float]
    warnings: list[str] = []


class BacktestSmokeResponse(BaseModel):
    ok: bool
    message: str
    twelvedata_configured: bool
