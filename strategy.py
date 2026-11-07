"""Simple, causal spread indicators and a stateful trading rule."""
import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller, coint


def add_indicators(prices: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    if window < 2:
        raise ValueError("Window must be at least 2 observations.")
    frame = prices.copy()
    frame["spread"] = frame["Brent"] - frame["WTI"]
    rolling = frame["spread"].rolling(window, min_periods=window)
    frame["rolling_mean"] = rolling.mean()
    frame["rolling_std"] = rolling.std(ddof=1)
    frame["zscore"] = (frame["spread"] - frame["rolling_mean"]) / frame[
        "rolling_std"
    ].replace(0, np.nan)
    return frame


def trading_signals(zscore: pd.Series, entry: float = 1.5,
                    exit_band: float = 0.25) -> pd.Series:
    """Desired position at each close: +1 long Brent/short WTI, -1 opposite.

    Exit near zero OR after crossing zero so an overshoot cannot miss the exit.
    Exit takes priority; there are no same-day reversals. Missing z-scores hold
    the current position; the initial rolling-window warm-up stays flat.
    """
    if not 0 <= exit_band < entry:
        raise ValueError("Require 0 <= exit band < entry threshold.")
    state = 0
    signals = []
    for z in zscore:
        if pd.notna(z):
            if state == 1 and z >= -exit_band:
                state = 0
            elif state == -1 and z <= exit_band:
                state = 0
            elif state == 0:
                if z > entry:
                    state = -1
                elif z < -entry:
                    state = 1
        signals.append(state)
    return pd.Series(signals, index=zscore.index, name="signal", dtype=int)


def statistical_summary(prices: pd.DataFrame) -> dict:
    """Full-sample descriptive tests; their results never select trading signals."""
    spread = prices["Brent"] - prices["WTI"]
    if len(spread) < 60:
        raise ValueError("Use at least 60 matched observations for statistical tests.")
    if spread.std() == 0 or prices.nunique().min() < 2:
        raise ValueError("Statistical tests need nonconstant prices and spread.")
    adf = adfuller(spread, regression="c", autolag="AIC")
    eg = coint(prices["Brent"], prices["WTI"], trend="c", autolag="aic")
    return {
        "observations": len(prices),
        "start": str(prices.index.min().date()),
        "end": str(prices.index.max().date()),
        "pearson_correlation": float(prices["WTI"].corr(prices["Brent"])),
        "spread_mean": float(spread.mean()),
        "spread_std": float(spread.std(ddof=1)),
        "adf_statistic": float(adf[0]), "adf_pvalue": float(adf[1]),
        "cointegration_statistic": float(eg[0]), "cointegration_pvalue": float(eg[1]),
    }


def explain_statistics(stats: dict) -> list[str]:
    adf_result = ("rejects the unit-root null; this is evidence of stationarity"
                  if stats["adf_pvalue"] < 0.05 else
                  "does not reject the unit-root null; stationarity is not established")
    eg_result = ("rejects the no-cointegration null; this supports a long-run relationship"
                 if stats["cointegration_pvalue"] < 0.05 else
                 "does not reject the no-cointegration null; cointegration is not established")
    return [
        f"Price correlation is {stats['pearson_correlation']:.3f}. Correlation measures "
        "co-movement, but does not establish mean reversion.",
        f"ADF p-value {stats['adf_pvalue']:.4f}: at the 5% level the test {adf_result}.",
        f"Engle–Granger p-value {stats['cointegration_pvalue']:.4f}: the test {eg_result}.",
        "Engle–Granger estimates its own hedge coefficient. A significant result "
        "does not prove that the equal-quantity Brent minus WTI spread is stationary.",
        "These full-sample tests describe this sample only. They do not guarantee "
        "future mean reversion or profitable trading, and do not filter the strategy.",
    ]
