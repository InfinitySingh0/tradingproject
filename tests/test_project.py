"""Small deterministic fixtures validate arithmetic, not investment performance."""
import numpy as np
import pandas as pd
import pytest

from backtest import BacktestConfig, run_backtest
from data import clean_prices
from strategy import add_indicators, trading_signals


def prices(spreads):
    index = pd.date_range("2024-01-01", periods=len(spreads))
    return pd.DataFrame({"WTI": 70.0, "Brent": 70.0 + np.array(spreads)}, index=index)


def test_spread_and_sample_zscore():
    result = add_indicators(prices([1, 2, 3, 4]), window=3)
    assert result.spread.tolist() == [1, 2, 3, 4]
    assert result.zscore.iloc[:2].isna().all()
    assert result.rolling_mean.iloc[2] == 2
    assert result.rolling_std.iloc[2] == 1
    assert result.zscore.iloc[2] == 1
    assert add_indicators(prices([2, 2, 2]), 2).zscore.isna().all()


def test_indicators_and_signals_do_not_use_future_prices():
    original = prices([1, 2, 3, 2, 4, 1, 2, 3])
    changed = original.copy()
    changed.iloc[5:, changed.columns.get_loc("Brent")] += 100
    for frame in [original, changed]:
        frame["zscore"] = add_indicators(frame, 3).zscore
    pd.testing.assert_series_equal(original.zscore.iloc[:5], changed.zscore.iloc[:5])
    pd.testing.assert_series_equal(trading_signals(original.zscore).iloc[:5],
                                   trading_signals(changed.zscore).iloc[:5])


def test_stateful_signals_hold_exit_and_zero_crossing():
    z = pd.Series([np.nan, 2, 2.1, 1.4, 0.2, -2, -2.1, -1, 0.8, 3, -0.9])
    assert trading_signals(z, entry=2.0).tolist() == [0, 0, -1, -1, 0, 0, 1, 1, 0, -1, 0]
    assert trading_signals(pd.Series([-3, np.nan, -1])).tolist() == [1, 1, 1]
    with pytest.raises(ValueError):
        trading_signals(z, entry=1, exit_band=1)


def test_next_close_execution_and_first_pnl_after_execution():
    p = prices([0, 10, 12, 13, 13])
    signals = pd.Series([1, 1, 0, 0, 0], index=p.index)
    daily, ledger, metrics = run_backtest(p, signals, BacktestConfig(commission=0, slippage_ticks=0))
    assert daily.position.tolist() == [0, 1, 1, 0, 0]
    # The $10 jump into the entry close is NOT earned.
    assert daily.gross_pnl.tolist() == [0, 0, 2000, 1000, 0]
    assert ledger.iloc[0].entry_date == p.index[1]
    assert ledger.iloc[0].exit_date == p.index[3]
    assert metrics["gross_pnl"] == 3000


def test_contract_multipliers_both_legs_costs_and_forced_exit():
    p = prices([0, 1, 3, 4])
    p["WTI"] += [0, 2, 5, 8]
    p["Brent"] += [0, 2, 5, 8]  # Shared moves cancel; spread still [0,1,3,4].
    signals = pd.Series([1, 1, 1, 1], index=p.index)
    daily, ledger, metrics = run_backtest(p, signals, BacktestConfig(contracts=2))
    assert daily.gross_pnl.tolist() == [0, 0, 4000, 2000]
    assert daily.commission.sum() == 20  # 2 contracts * 2 legs * 2 sides * $2.50
    assert daily.slippage.sum() == 80  # 2 * 2 * 2 * $10
    assert metrics["net_pnl"] == 5900
    assert metrics["number_of_trades"] == 1
    assert ledger.iloc[0].forced_exit
    assert ledger.net_pnl.sum() == daily.net_pnl.sum()
    assert daily.position.iloc[-1] == 0
    assert metrics["max_drawdown_usd"] == 50


def test_short_trade_loss_and_profit_factor():
    p = prices([0, 0, 2, 2, 2, 4, 4])
    signal = pd.Series([-1, 0, 0, 1, 0, 0, 0], index=p.index)
    daily, ledger, metrics = run_backtest(p, signal)
    assert ledger.net_pnl.tolist() == [-2050, 1950]
    assert metrics["win_rate"] == 0.5
    assert metrics["profit_factor"] == pytest.approx(1950 / 2050)
    assert metrics["max_drawdown_usd"] == 2075  # Includes the next trade's entry fee.
    assert daily.net_pnl.sum() == ledger.net_pnl.sum()


def test_flat_strategy_has_no_trades_or_undefined_ratio_fabrication():
    p = prices([1, 2, 3])
    daily, ledger, metrics = run_backtest(p, pd.Series(0, index=p.index))
    assert ledger.empty
    assert metrics["net_pnl"] == 0
    assert metrics["sharpe_ratio"] is None
    assert metrics["profit_factor"] is None
    assert metrics["win_rate"] is None


def test_clean_prices_aligns_drops_missing_and_keeps_negative_prices():
    p = pd.DataFrame({"WTI": [1, np.nan, -2, 4], "Brent": [2, 3, 0, np.inf]},
                     index=pd.to_datetime(["2024-01-03", "2024-01-02", "2024-01-01", "2024-01-04"]))
    result = clean_prices(p)
    assert result.WTI.tolist() == [-2, 1]
    assert result.index.is_monotonic_increasing


def test_yahoo_download_cleans_multilevel_close_and_writes_csv(monkeypatch, tmp_path):
    import data
    calls = []

    def fake_download(ticker, **kwargs):
        calls.append((ticker, kwargs))
        values = [70, np.nan, 72] if ticker == "CL=F" else [74, 75, 76]
        columns = pd.MultiIndex.from_tuples([("Close", ticker)])
        return pd.DataFrame(values, index=pd.date_range("2024-01-01", periods=3), columns=columns)

    monkeypatch.setattr(data.yf, "download", fake_download)
    path = tmp_path / "test_prices.csv"
    result = data.download_prices(path)
    assert result.shape == (2, 2)
    assert result.Brent.sub(result.WTI).tolist() == [4, 4]
    assert path.exists()
    assert [call[0] for call in calls] == ["CL=F", "BZ=F"]
    assert calls[0][1]["auto_adjust"] is False
    assert calls[0][1]["end"] > calls[0][1]["start"]


def test_download_failure_preserves_existing_csv(monkeypatch, tmp_path):
    import data
    path = tmp_path / "existing.csv"
    path.write_text("existing user data\n")
    monkeypatch.setattr(data.yf, "download", lambda *args, **kwargs: pd.DataFrame())
    with pytest.raises(RuntimeError, match="No synthetic data"):
        data.download_prices(path)
    assert path.read_text() == "existing user data\n"


def dashboard_entrypoint():
    from app import main
    main()


def test_dashboard_renders_analysis_and_reacts_to_settings(monkeypatch, tmp_path):
    """Only a synthetic test fixture; never saved as historical prices or results."""
    import app
    from streamlit.testing.v1 import AppTest
    from strategy import statistical_summary
    rng = np.random.default_rng(42)
    wti = 70 + rng.normal(0, 1, 150).cumsum()
    fixture = pd.DataFrame({"WTI": wti, "Brent": wti + 4 + rng.normal(0, 1, 150)},
                           index=pd.date_range("2024-01-01", periods=150))
    path = tmp_path / "cache-marker"
    path.touch()
    monkeypatch.setattr(app, "DATA_PATH", path)
    monkeypatch.setattr(app, "load_prices", lambda: fixture)
    stats = statistical_summary(fixture)
    assert 0 <= stats["adf_pvalue"] <= 1
    assert 0 <= stats["cointegration_pvalue"] <= 1
    at = AppTest.from_function(dashboard_entrypoint).run(timeout=30)
    assert not at.exception
    assert not at.error
    assert next(w.value for w in at.number_input if w.label == "Entry Z-score") == 1.5
    assert len(at.metric) == 10
    assert not at.radio
    assert len(at.tabs) == 3
    assert len(at.get("plotly_chart")) == 4
    at.number_input[0].set_value(30).run(timeout=30)
    assert not at.exception
    assert not at.error


def test_dashboard_shows_download_error_without_fake_results(monkeypatch, tmp_path):
    import app
    from streamlit.testing.v1 import AppTest
    monkeypatch.setattr(app, "DATA_PATH", tmp_path / "missing.csv")

    def unavailable():
        raise RuntimeError("Network unavailable")

    monkeypatch.setattr(app, "download_prices", unavailable)
    at = AppTest.from_function(dashboard_entrypoint).run(timeout=30)
    assert not at.exception
    assert "Network unavailable" in at.error[0].value
    assert len(at.metric) == 0
