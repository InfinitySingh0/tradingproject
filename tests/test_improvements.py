"""Risk timing, holdout isolation and cost-accounting regression tests."""
import numpy as np
import pandas as pd
import pytest

from backtest import (BacktestConfig, run_backtest, evaluate_split, monthly_pnl,
                      completed_trade_summary, slippage_sensitivity)
from strategy import add_indicators, trading_signals


def market(n=150):
    rng = np.random.default_rng(15)
    wti = 70 + rng.normal(0, 1, n).cumsum()
    return pd.DataFrame({"WTI": wti, "Brent": wti + 4 + rng.normal(0, 2, n)},
                        index=pd.bdate_range("2024-01-01", periods=n))


@pytest.mark.parametrize("direction", [1, -1])
def test_stop_boundary_is_directional_and_executes_next_close(direction):
    p = market(7)
    z = pd.Series(np.array([-2.5, -2.8, -3, -3.5, -2.5, 0, 0]) * direction, index=p.index)
    signals = trading_signals(z)
    assert signals.tolist() == [direction, direction, 0, 0, direction, 0, 0]
    daily, trades, _ = run_backtest(p, signals)
    assert daily.position.iloc[2] == direction  # Stop observed, not executed yet.
    assert daily.position.iloc[3] == 0
    assert trades.iloc[0].exit_date == p.index[3]
    assert trades.iloc[0].holding_days == 2
    assert daily.costs.iloc[3] == 25


def test_no_new_entry_at_or_beyond_stop():
    assert trading_signals(pd.Series([-4, -3, 3, 4])).tolist() == [0, 0, 0, 0]


@pytest.mark.parametrize("limit", [1, 3, 15])
def test_holding_limit_counts_executed_intervals_even_with_missing_z(limit):
    p = market(22)
    z = pd.Series([-2.5] + [np.nan] * 21, index=p.index)
    signals = trading_signals(z, max_holding=limit)
    daily, trades, _ = run_backtest(p, signals)
    assert signals.iloc[limit] == 0
    assert trades.iloc[0].entry_date == p.index[1]
    assert trades.iloc[0].exit_date == p.index[limit + 1]
    assert trades.iloc[0].holding_days == limit
    assert trades.net_pnl.sum() == pytest.approx(daily.net_pnl.sum())


def test_mean_exit_preempts_time_stop_and_parameters_validate():
    assert trading_signals(pd.Series([-2.5, -0.1, 2.5, -1])).tolist() == [1, 0, -1, 0]
    for args in [dict(stop_z=2), dict(max_holding=0), dict(max_holding=1.5)]:
        with pytest.raises(ValueError):
            trading_signals(pd.Series([0]), **args)


def test_rolling_correlation_matches_trailing_window_and_no_future_leakage():
    p = market()
    result = add_indicators(p)
    assert result.rolling_correlation.iloc[:59].isna().all()
    assert result.rolling_correlation.iloc[59] == pytest.approx(p.WTI.iloc[:60].corr(p.Brent.iloc[:60]))
    changed = p.copy()
    changed.iloc[80:, changed.columns.get_loc("Brent")] += 100
    pd.testing.assert_frame_equal(add_indicators(changed).iloc[:80], result.iloc[:80])


def test_holdout_is_separate_and_training_ignores_test_prices():
    p = market()
    original = evaluate_split(p)
    training, testing = original["Training"], original["Testing"]
    assert len(training["daily"]) == 105
    assert len(testing["daily"]) == 45
    assert training["daily"].index[-1] < testing["daily"].index[0]
    assert training["daily"].position.iloc[-1] == 0
    assert testing["daily"].position.iloc[0] == 0
    assert testing["daily"].gross_pnl.iloc[0] == 0
    assert pd.notna(testing["indicators"].zscore.iloc[0])  # Training prices warm up test.
    expected_signals = trading_signals(add_indicators(p).zscore.iloc[105:])
    pd.testing.assert_series_equal(testing["daily"].signal, expected_signals)
    changed = p.copy()
    changed.iloc[105:, changed.columns.get_loc("Brent")] += 100
    pd.testing.assert_frame_equal(evaluate_split(changed)["Training"]["daily"], training["daily"])
    for segment in original.values():
        assert segment["trades"].holding_days.max() <= 15
        assert segment["monthly"].net_pnl.sum() == pytest.approx(segment["metrics"]["net_pnl"])


def test_slippage_costs_change_without_changing_trades_or_gross():
    p = market(8)
    signals = pd.Series([1, 1, 0, 0, -1, 0, 0, 0], index=p.index)
    scenarios = slippage_sensitivity(p, signals, BacktestConfig(contracts=2))
    assert scenarios.slippage_ticks.tolist() == [1, 2, 3, 5]
    assert scenarios.number_of_trades.tolist() == [2, 2, 2, 2]
    assert scenarios.gross_pnl.nunique() == 1
    # Two trades * two contracts * two legs * entry/exit * $10 per tick.
    assert scenarios.net_pnl.iloc[0] - scenarios.net_pnl.iloc[1] == pytest.approx(160)
    assert scenarios.net_pnl.iloc[0] - scenarios.net_pnl.iloc[3] == pytest.approx(640)


def test_monthly_pnl_marks_to_market_and_trade_summary_handles_empty():
    p = market(5)
    p.index = pd.to_datetime(["2024-01-30", "2024-01-31", "2024-02-01", "2024-02-02", "2024-02-05"])
    daily, trades, _ = run_backtest(p, pd.Series([1, 1, 0, 0, 0], index=p.index))
    monthly = monthly_pnl(daily)
    assert monthly.net_pnl.iloc[0] == -25  # January entry fee, despite February exit.
    assert monthly.net_pnl.sum() == pytest.approx(daily.net_pnl.sum())
    summary = completed_trade_summary(trades)
    assert summary['completed_trades'] == 1
    assert summary['average_holding_days'] == 2
    assert summary['average_net_pnl'] == pytest.approx(trades.net_pnl.iloc[0])
    empty = completed_trade_summary(trades.iloc[:0])
    assert empty['completed_trades'] == 0 and empty['average_net_pnl'] is None


def test_test_prices_cannot_change_threshold_selection():
    from backtest import evaluate_thresholds, ENTRY_THRESHOLDS
    p = market(400)
    table, entry, segments = evaluate_thresholds(p)
    assert table.entry_threshold.tolist() == list(ENTRY_THRESHOLDS)
    assert entry is not None
    changed = p.copy()
    changed.iloc[280:, changed.columns.get_loc("Brent")] += np.arange(120) * 20
    other, chosen, changed_segments = evaluate_thresholds(changed)
    pd.testing.assert_frame_equal(table, other)
    assert chosen == entry
    pd.testing.assert_frame_equal(segments['Training']['daily'], changed_segments['Training']['daily'])


def test_selected_threshold_is_only_test_backtest(monkeypatch):
    import backtest
    p = market(400)
    original = backtest.run_backtest
    test_calls = []

    def record(prices, signals, config):
        if prices.index[0] == p.index[280]:
            test_calls.append(signals.copy())
        return original(prices, signals, config)

    monkeypatch.setattr(backtest, 'run_backtest', record)
    _, entry, result = backtest.evaluate_thresholds(p)
    assert len(test_calls) == 1
    expected = trading_signals(add_indicators(p).zscore.iloc[280:], entry=entry)
    pd.testing.assert_series_equal(test_calls[0], expected)
    assert result['Testing']['sensitivity'].empty


def test_no_eligible_threshold_skips_testing(monkeypatch):
    import backtest
    p = market(100)
    p['Brent'] = p['WTI'] + 4
    table, entry, result = backtest.evaluate_thresholds(p)
    assert not table.eligible.any()
    assert entry is None and result == {}


def test_selection_balances_drawdown_and_sharpe_with_trade_count(monkeypatch):
    import backtest
    # Candidate 1 has the best Sharpe but too few trades. Eligible rank ties
    # select the better combined rank; lower entry resolves the exact 1.5/1.75 tie.
    values = iter([(9, 1, 2), (2, 100, 20), (1, 50, 20),
                   (1, 50, 20), (0, 200, 20), (-1, 300, 20), (-2, 400, 20)])

    def fake_backtest(*args):
        sharpe, drawdown, trades = next(values)
        return None, None, dict(sharpe_ratio=sharpe, max_drawdown_usd=drawdown,
                               number_of_trades=trades)

    monkeypatch.setattr(backtest, 'run_backtest', fake_backtest)
    table, chosen = backtest.select_entry_threshold(market())
    assert not table.eligible.iloc[0]
    assert chosen == 1.5


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
