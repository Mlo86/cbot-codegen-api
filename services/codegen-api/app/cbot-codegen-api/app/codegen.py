from __future__ import annotations
import re
from .schemas import StrategySpec


def _safe_class_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", " ", name).title().replace(" ", "")
    if not cleaned:
        cleaned = "GeneratedBot"
    if not cleaned[0].isalpha():
        cleaned = "Bot" + cleaned
    return cleaned


def generate_python_cbot(spec: StrategySpec) -> tuple[str, list[str]]:
    """Render a cTrader-style Python cBot skeleton from the spec."""
    warnings: list[str] = []
    class_name = _safe_class_name(spec.name)
    instrument = spec.instrument or "EURUSD"
    timeframe = spec.timeframe or "H1"

    if not spec.entry:
        warnings.append("No entry rules provided; using placeholder logic.")
    if not spec.exit and not spec.risk:
        warnings.append("No exit or risk rules provided; using default SL/TP.")

    sl_pips = spec.risk.get("stop_loss_pips", 20) if isinstance(spec.risk, dict) else 20
    tp_pips = spec.risk.get("take_profit_pips", 40) if isinstance(spec.risk, dict) else 40
    volume = spec.risk.get("volume", 1000) if isinstance(spec.risk, dict) else 1000

    code = f'''"""
Auto-generated cBot: {spec.name}
Instrument: {instrument}  Timeframe: {timeframe}

{spec.description or "No description provided."}
"""
from ctrader import Robot, TradeType, TimeFrame


class {class_name}(Robot):
    symbol_name = "{instrument}"
    timeframe = TimeFrame.{timeframe}

    stop_loss_pips = {sl_pips}
    take_profit_pips = {tp_pips}
    volume = {volume}

    def on_start(self) -> None:
        self.print(f"{{self.__class__.__name__}} started on {{self.symbol_name}}")

    def on_bar(self) -> None:
        if self._entry_signal():
            self._open_position(TradeType.BUY)

    def _entry_signal(self) -> bool:
        # TODO: entry rules derived from spec
        return False

    def _open_position(self, side: TradeType) -> None:
        self.execute_market_order(
            side,
            self.symbol_name,
            self.volume,
            label=self.__class__.__name__,
            stop_loss_pips=self.stop_loss_pips,
            take_profit_pips=self.take_profit_pips,
        )

    def on_stop(self) -> None:
        self.print("Stopped.")
'''
    filename = f"{class_name.lower()}.py"
    return code, warnings
