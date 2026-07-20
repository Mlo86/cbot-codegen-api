from __future__ import annotations
import os
import httpx
import numpy as np
from fastapi import HTTPException
from .schemas import (
    StrategySpec, BacktestRequest, BacktestResponse,
    BacktestMetrics, Trade,
)

TD_URL = "https://api.twelvedata.com/time_series"


async def fetch_bars(symbol: str, interval: str, outputsize: int) -> list[dict]:
    key = os.environ.get("TWELVE_DATA_API_KEY")
    if not key:
        raise HTTPException(500, "TWELVE_DATA_API_KEY not configured on the server")
    params = {
        "symbol": symbol, "interval": interval,
        "outputsize": outputsize, "apikey": key, "order": "ASC",
    }
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(TD_URL, params=params)
    if r.status_code != 200:
        raise HTTPException(502, f"Twelve Data error {r.status_code}: {r.text[:200]}")
    data = r.json()
    if data.get("status") == "error":
        raise HTTPException(502, f"Twelve Data: {data.get('message', 'unknown')}")
    values = data.get("values") or []
    return [
        {
            "t": v["datetime"],
            "o": float(v["open"]), "h": float(v["high"]),
            "l": float(v["low"]),  "c": float(v["close"]),
        }
        for v in values
    ]


def _sma(arr: list[float], n: int) -> list[float | None]:
    out: list[float | None] = [None] * len(arr)
    if n <= 0 or n > len(arr):
        return out
    s = sum(arr[:n]); out[n - 1] = s / n
    for i in range(n, len(arr)):
        s += arr[i] - arr[i - n]
        out[i] = s / n
    return out


def run_backtest(spec: StrategySpec, bars: list[dict], initial_balance: float) -> BacktestResponse:
    """Simple SMA-cross runner driven by spec.entry / spec.risk.
    Defaults: fast=20, slow=50, sl=20 pips, tp=40 pips, volume=1000."""
    warnings: list[str] = []
    if len(bars) < 60:
        raise HTTPException(400, "Not enough bars for a meaningful backtest (need >= 60).")

    entry = spec.entry or {}
    risk = spec.risk or {}
    fast_n = int(entry.get("fast_ma", 20))
    slow_n = int(entry.get("slow_ma", 50))
    sl_pips = float(risk.get("stop_loss_pips", 20))
    tp_pips = float(risk.get("take_profit_pips", 40))
    volume  = float(risk.get("volume", 1000))
    pip = 0.0001 if "JPY" not in (spec.instrument or "") else 0.01

    if not entry:
        warnings.append("No entry rules; using SMA(20/50) crossover default.")
    if not risk:
        warnings.append("No risk rules; using SL=20p, TP=40p, vol=1000.")

    closes = [b["c"] for b in bars]
    fast = _sma(closes, fast_n)
    slow = _sma(closes, slow_n)

    balance = initial_balance
    equity: list[float] = []
    trades: list[Trade] = []
    peak = balance; max_dd = 0.0

    pos: dict | None = None
    for i, bar in enumerate(bars):
        # exit checks first
        if pos is not None:
            side = pos["side"]
            hit_sl = (bar["l"] <= pos["sl"]) if side == "buy" else (bar["h"] >= pos["sl"])
            hit_tp = (bar["h"] >= pos["tp"]) if side == "buy" else (bar["l"] <= pos["tp"])
            exit_price = None; reason = None
            if hit_sl and hit_tp:
                exit_price, reason = pos["sl"], "sl"  # conservative
            elif hit_sl:
                exit_price, reason = pos["sl"], "sl"
            elif hit_tp:
                exit_price, reason = pos["tp"], "tp"
            if exit_price is not None:
                pnl = (exit_price - pos["entry"]) * (1 if side == "buy" else -1) * volume
                balance += pnl
                trades.append(Trade(
                    side=side, entry_time=pos["t"], entry_price=pos["entry"],
                    exit_time=bar["t"], exit_price=exit_price, pnl=pnl, reason=reason,
                ))
                pos = None

        # entry check (only when flat and both MAs available)
        if pos is None and fast[i] is not None and slow[i] is not None and i > 0 and fast[i - 1] is not None and slow[i - 1] is not None:
            cross_up   = fast[i - 1] <= slow[i - 1] and fast[i] > slow[i]
            cross_down = fast[i - 1] >= slow[i - 1] and fast[i] < slow[i]
            if cross_up or cross_down:
                side = "buy" if cross_up else "sell"
                entry_price = bar["c"]
                sl = entry_price - sl_pips * pip if side == "buy" else entry_price + sl_pips * pip
                tp = entry_price + tp_pips * pip if side == "buy" else entry_price - tp_pips * pip
                pos = {"side": side, "entry": entry_price, "sl": sl, "tp": tp, "t": bar["t"]}

        equity.append(balance)
        if balance > peak: peak = balance
        dd = (peak - balance) / peak * 100 if peak > 0 else 0
        if dd > max_dd: max_dd = dd

    # close open position at last bar
    if pos is not None:
        last = bars[-1]
        pnl = (last["c"] - pos["entry"]) * (1 if pos["side"] == "buy" else -1) * volume
        balance += pnl
        trades.append(Trade(
            side=pos["side"], entry_time=pos["t"], entry_price=pos["entry"],
            exit_time=last["t"], exit_price=last["c"], pnl=pnl, reason="end",
        ))
        equity[-1] = balance

    wins = sum(1 for t in trades if t.pnl > 0)
    losses = sum(1 for t in trades if t.pnl <= 0)
    total_pnl = balance - initial_balance
    returns = np.diff(equity) / np.array(equity[:-1]) if len(equity) > 1 else np.array([0.0])
    sharpe = float(np.mean(returns) / np.std(returns) * np.sqrt(252)) if returns.std() > 0 else 0.0

    metrics = BacktestMetrics(
        trades=len(trades), wins=wins, losses=losses,
        win_rate=(wins / len(trades) * 100) if trades else 0.0,
        total_pnl=total_pnl,
        return_pct=(total_pnl / initial_balance * 100),
        max_drawdown_pct=max_dd, sharpe=sharpe,
        final_balance=balance,
    )
    return BacktestResponse(
        symbol=spec.instrument or "unknown",
        interval="", bars=len(bars),
        metrics=metrics, trades=trades, equity_curve=equity,
        warnings=warnings,
    )
