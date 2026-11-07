"""Regression checks for simple entries and detailed trade prices."""
import numpy as np
import pandas as pd
import pytest
from backtest import BacktestConfig, run_backtest
from strategy import add_indicators, trading_signals


def market(n=150):
    rng = np.random.default_rng(15)
    wti = 70 + rng.normal(0, 1, n).cumsum()
    return pd.DataFrame({"WTI": wti, "Brent": wti + 4 + rng.normal(0, 2, n)},
                        index=pd.bdate_range("2024-01-01", periods=n))


@pytest.mark.parametrize('direction', [1, -1])
def test_detailed_ledger_prices_legs_costs_and_signal_dates(direction):
    p = add_indicators(market(8), window=2)
    signals = pd.Series([direction, direction, 0, 0, 0, 0, 0, 0], index=p.index)
    config = BacktestConfig(contracts=2, commission=3, slippage_ticks=2)
    daily, trades, _ = run_backtest(p, signals, config)
    trade = trades.iloc[0]
    assert trade.entry_wti_price == p.WTI.iloc[1]
    assert trade.exit_brent_price == p.Brent.iloc[3]
    assert trade.entry_signal_date == p.index[0]
    assert trade.exit_signal_date == p.index[2]
    assert trade.entry_spread == pytest.approx(p.spread.iloc[1])
    assert trade.exit_signal_zscore == p.zscore.iloc[2]
    assert trade.brent_gross_pnl == pytest.approx(direction * 2 * 1000 * (p.Brent.iloc[3]-p.Brent.iloc[1]))
    assert trade.brent_gross_pnl + trade.wti_gross_pnl == pytest.approx(trade.gross_pnl)
    assert trade.commission == 24
    assert trade.slippage == 160
    assert trade.net_pnl == pytest.approx(trade.gross_pnl - trade.commission - trade.slippage)
    assert trade.net_pnl == pytest.approx(daily.net_pnl.sum())


def test_default_entry_is_one_point_five():
    assert trading_signals(pd.Series([1.5, 1.6, 0, -1.5, -1.6, 0])).tolist() == [0, -1, 0, 0, 1, 0]


def test_no_stop_or_holding_limit_and_mean_exit_preserved():
    z = pd.Series([-1.6] + [-4.0] * 20 + [0.1])
    assert trading_signals(z).tolist() == [1] * 21 + [0]
    assert trading_signals(pd.Series([4, 3, 0])).tolist() == [-1, -1, 0]
