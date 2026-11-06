"""Illustrative daily-close futures P&L, with explicit execution timing and costs."""
from dataclasses import dataclass, asdict
from pathlib import Path
import json

import numpy as np
import pandas as pd

# CME CL and BZ contracts: 1,000 barrels; $0.01/barrel tick = $10/contract.
# Source links and continuous-series limitations are documented in README.md.
WTI_MULTIPLIER = 1000
BRENT_MULTIPLIER = 1000
TICK_SIZE = 0.01


@dataclass(frozen=True)
class BacktestConfig:
    contracts: int = 1  # Equal integer quantity on each leg.
    commission: float = 2.50  # USD per contract, per leg, per execution.
    slippage_ticks: float = 1.0  # Per leg, per execution.
    reference_capital: float = 100_000.0  # Scaling convention, not margin required.

    def __post_init__(self):
        if self.contracts < 1 or int(self.contracts) != self.contracts:
            raise ValueError("Contracts must be a positive integer.")
        values = [self.commission, self.slippage_ticks, self.reference_capital]
        if not all(np.isfinite(v) for v in values):
            raise ValueError("Configuration values must be finite.")
        if self.commission < 0 or self.slippage_ticks < 0 or self.reference_capital <= 0:
            raise ValueError("Costs must be nonnegative and reference capital positive.")


def run_backtest(prices: pd.DataFrame, signals: pd.Series,
                 config: BacktestConfig = BacktestConfig()):
    """Signal at close t -> execution at close t+1 -> first P&L at close t+2.

    position is held AFTER today's close; held_position earns today's price move.
    Liquidate any remaining position at the final close and charge exit costs.
    """
    if len(prices) < 2 or not prices.index.equals(signals.index):
        raise ValueError("Prices and signals need matching indexes and at least two rows.")
    if not prices.index.is_monotonic_increasing or prices.index.has_duplicates:
        raise ValueError("Prices must have unique, increasing dates.")
    if not np.isfinite(prices[["WTI", "Brent"]].to_numpy()).all():
        raise ValueError("Prices must be finite.")
    if not signals.isin([-1, 0, 1]).all():
        raise ValueError("Signals must be -1, 0, or 1.")
    frame = prices[["WTI", "Brent"]].copy()
    frame["signal"] = signals
    frame["position"] = signals.shift(1, fill_value=0).astype(int)
    frame.loc[frame.index[-1], "position"] = 0
    frame["held_position"] = frame["position"].shift(1, fill_value=0)
    frame["turnover"] = frame["position"].diff().fillna(0).abs()
    unit_move = (BRENT_MULTIPLIER * frame["Brent"].diff()
                 - WTI_MULTIPLIER * frame["WTI"].diff()).fillna(0)
    frame["gross_pnl"] = frame["held_position"] * config.contracts * unit_move
    frame["commission"] = frame["turnover"] * config.contracts * 2 * config.commission
    frame["slippage"] = (frame["turnover"] * config.contracts * config.slippage_ticks
                          * TICK_SIZE * (WTI_MULTIPLIER + BRENT_MULTIPLIER))
    frame["costs"] = frame["commission"] + frame["slippage"]
    frame["net_pnl"] = frame["gross_pnl"] - frame["costs"]
    frame["cumulative_gross"] = frame["gross_pnl"].cumsum()
    frame["cumulative_net"] = frame["net_pnl"].cumsum()
    # Include starting equity: a loss on the first trade is a drawdown too.
    frame["drawdown"] = frame["cumulative_net"] - frame["cumulative_net"].cummax().clip(lower=0)

    # Closed-trade ledger includes all entry/exit costs and final liquidation.
    trades = []
    active = None
    side_cost = config.contracts * (
        2 * config.commission + config.slippage_ticks * TICK_SIZE
        * (WTI_MULTIPLIER + BRENT_MULTIPLIER))
    for date, row in frame.iterrows():
        old, new = int(row["held_position"]), int(row["position"])
        if active is not None:
            active["gross_pnl"] += row["gross_pnl"]
        if old != new:
            if old:
                active["exit_date"] = date
                active["costs"] += side_cost
                active["net_pnl"] = active["gross_pnl"] - active["costs"]
                active["forced_exit"] = date == frame.index[-1]
                trades.append(active)
                active = None
            if new:
                active = dict(entry_date=date, direction="Long spread" if new == 1 else "Short spread",
                              gross_pnl=0.0, costs=side_cost)
    ledger = pd.DataFrame(trades, columns=["entry_date", "exit_date", "direction",
                                          "gross_pnl", "costs", "net_pnl", "forced_exit"])
    daily_scaled_pnl = frame["net_pnl"] / config.reference_capital
    volatility = daily_scaled_pnl.std(ddof=1)
    wins = ledger.loc[ledger["net_pnl"] > 0, "net_pnl"].sum()
    losses = -ledger.loc[ledger["net_pnl"] < 0, "net_pnl"].sum()
    metrics = {
        "gross_pnl": float(frame["gross_pnl"].sum()),
        "transaction_costs": float(frame["costs"].sum()),
        "net_pnl": float(frame["net_pnl"].sum()),
        "sharpe_ratio": float(np.sqrt(252) * daily_scaled_pnl.mean() / volatility)
        if volatility > 0 else None,
        "profit_factor": float(wins / losses) if losses > 0 else None,
        "win_rate": float((ledger["net_pnl"] > 0).mean()) if len(ledger) else None,
        "max_drawdown_usd": float(-frame["drawdown"].min()),
        "number_of_trades": len(ledger),
    }
    return frame, ledger, metrics


if __name__ == "__main__":
    from data import DATA_PATH, download_prices, load_prices
    from strategy import add_indicators, trading_signals, statistical_summary, explain_statistics
    prices = load_prices() if DATA_PATH.exists() else download_prices()
    indicators = add_indicators(prices)
    config = BacktestConfig()
    daily, trades, metrics = run_backtest(prices, trading_signals(indicators["zscore"]), config)
    stats = statistical_summary(prices)
    output = Path(__file__).parent / "outputs"
    output.mkdir(exist_ok=True)
    daily.to_csv(output / "backtest.csv")
    trades.to_csv(output / "trades.csv", index=False)
    report = dict(label="Exploratory continuous-futures research simulation", statistics=stats,
                  assumptions=asdict(config), metrics=metrics, explanation=explain_statistics(stats))
    (output / "results.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    from app import make_charts
    for name, figure in make_charts(indicators, daily).items():
        figure.write_html(output / f"{name}.html", include_plotlyjs=True)
    print(json.dumps(report, indent=2, allow_nan=False))
    print(f"Saved results, trade ledger, daily P&L and four interactive charts to {output}")
