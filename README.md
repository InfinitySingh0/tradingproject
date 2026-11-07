# WTI–Brent Crude Oil Spread Trading Using Mean Reversion

A small Python research project exploring whether the daily **Brent − WTI** crude oil price spread offers mean-reversion opportunities. Includes Yahoo Finance downloads, statistical tests, a transparent two-leg futures simulation, and a Streamlit dashboard.

**Exploratory analysis, not verified trading performance.** Yahoo continuous futures symbols are price proxies, not a history of executable, expiry-matched contracts. No profitability is assumed or promised.

## Current simplified version

Restored the original full-history workflow, with a configurable **default entry Z-score of ±1.5** and the original mean-reversion exit band of ±0.25 (including zero crossings). There is no Z-score stop, maximum holding limit, train/test split, threshold optimizer, slippage sweep, rolling-correlation chart, monthly P&L chart or additional completed-trade summary. A position remains open until mean reversion or final-sample liquidation.

The four original charts remain: prices, spread/trade markers, Z-score and cumulative P&L. The trade ledger includes WTI and Brent entry/exit prices, spreads, decision/execution dates, available decision Z-scores, directions, quantity, observed holding duration, leg-level P&L and separate fees. Holding duration is descriptive, not a limit. Displayed prices are execution-day Yahoo closes in USD/barrel; slippage is deducted separately as a cash cost, not also added to the prices. These are continuous-futures proxy prices, not verified executable fills.

Commissions, a configurable single slippage assumption, contract multipliers, lagged execution and rollover disclosures remain. All analysis is in-sample. Dated files in `results/` from other versions are archived evidence only, not current behavior. Old training/testing or threshold output files on disk are not read by this version; `python backtest.py` writes the full-sample files listed below.

Current verification: **16 tests pass**, including checks that positions can remain open beyond 15 observations and beyond |Z| = 3, while the mean-reversion exit still works. Actual-data dashboard checks confirm four charts, no removed controls, and both legs' nonmissing entry/exit prices.

The rerun uses the saved Yahoo dataset (2021-11-08 through 2026-11-05): net simulated P&L **$91,150.02**, Sharpe **1.5079**, and **71 completed trades**. These are in-sample proxy-data calculations, not verified trading profitability. [Full results](results/2026-11-07-simple-entry-1.5.json) and [detailed trade prices](results/2026-11-07-simple-entry-1.5-trades.csv).

## Quick start

Use Python 3.12 (tested). From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python data.py
python backtest.py
streamlit run app.py
```

`python data.py` downloads approximately five years of daily `CL=F` and `BZ=F` prices. `python backtest.py` uses the saved prices, or downloads them if missing. The dashboard also downloads automatically when no saved CSV exists; its refresh button requests a new download.

Run the tests with:

```bash
python -m pytest -q
```

No API key, paid data, database, or brokerage account is required. Yahoo may rate-limit or change its free endpoints. Keep TLS verification enabled. If download fails, check network access and retry later; the program never substitutes invented prices.

## Files

The existing repository is named `tradingproject`; it serves as the project root without an extra nested directory.

```text
tradingproject/
├── app.py              # Streamlit interface and Plotly charts
├── data.py             # Download, clean, align and save prices
├── strategy.py         # Indicators, statistical tests, stateful signals
├── backtest.py         # Execution, dollar P&L, costs and trade ledger
├── requirements.txt
├── README.md
├── tests/
│   ├── test_project.py
│   └── test_trade_details.py
└── outputs/            # Generated locally after a successful download; ignored by Git
```

Generated outputs:

| File | Contents |
| --- | --- |
| `prices.csv` | Date, WTI, Brent; matched daily closes |
| `backtest.csv` | Signals, positions, daily P&L, costs and drawdowns |
| `trades.csv` | Completed trades including entry/exit costs |
| `results.json` | Sample dates, statistical tests, assumptions and metrics |
| `prices.html`, `spread.html`, `zscore.html`, `pnl.html` | Standalone interactive Plotly charts |

The dashboard shows all four charts, executed long/short/exit markers, metrics, statistical explanations, a trade ledger, and CSV downloads. HTML charts embed Plotly and can be opened offline after generation.

## Data and cleaning

- Source: free `yfinance`, Yahoo tickers **CL=F** (WTI) and **BZ=F** (Brent).
- Uses raw daily `Close` with `auto_adjust=False`. This does **not** remove continuous-contract roll effects or make the series tradable.
- Requests five calendar years ending before the current UTC date to exclude potentially unfinished daily bars.
- Removes invalid/missing pairs, normalizes daily dates, sorts observations and removes duplicate dates. No forward-fill or interpolation.
- Negative prices are retained: futures prices can be negative.
- Rolling windows count matched observations, not calendar days. Date matching does not ensure simultaneous settlements or matching contract expiries.
- A failed refresh preserves an existing cleaned CSV. Refresh explicitly to update a cached dataset.

## Statistics in plain language

1. **Pearson correlation:** how closely price levels move together. High correlation does not imply a stationary spread or a profitable trade.
2. **Spread:** `Brent close − WTI close`, measured in USD per barrel. Report its sample mean and sample standard deviation.
3. **Augmented Dickey–Fuller (ADF):** tests the fixed 1:1 spread. The null hypothesis is a unit root. A p-value below 0.05 is evidence against that null, not proof that future prices will revert.
4. **Engle–Granger:** tests Brent and WTI price levels for cointegration, with an estimated coefficient and intercept. Its null is no cointegration. A significant result does not necessarily validate the fixed 1:1 spread. Cointegration interpretation also relies on the input series' integration properties; this simple project does not establish all those assumptions.
5. **Rolling Z-score:** `(spread − trailing mean) / trailing sample standard deviation`, initially over 20 observations. Only information available through that day's close is used. The initial window and zero-volatility windows have no valid Z-score.

Full-sample statistics are descriptive only and never filter trades. The dashboard explains the actual p-values conditionally; it does not presume stationarity or cointegration.

## Trading rules and execution timing

| State / condition | Desired action |
| --- | --- |
| Flat and Z-score > +1.5 | Short spread: sell Brent, buy WTI |
| Flat and Z-score < −1.5 | Long spread: buy Brent, sell WTI |
| Long and Z-score ≥ −0.25 | Close; also catches a jump across zero |
| Short and Z-score ≤ +0.25 | Close; also catches a jump across zero |
| Otherwise | Hold the existing position or remain flat |

Thresholds are strict for entry. Exit takes priority; no immediate reversal on an exit day. Missing indicators hold an existing position; the warm-up starts flat.

**Timing matters:** a signal calculated at Monday's close executes at Tuesday's close (or the next matched observation). The first earned price change is Tuesday close to Wednesday close. Tuesday's close-to-close move is not credited to a position that only opens Tuesday evening.

In code, `signal` is the desired state, `position = signal.shift(1)` is the state after today's close, and `held_position = position.shift(1)` earns today's move. This is deliberately more conservative than treating a just-computed closing-price signal as executable at that same close. Slippage approximates imperfect fills; it does not establish that the closing prices were available in practice.

## Contract sizing and dollar P&L

Use equal integer quantities, initially **one contract per leg**. The standard contract specifications used are:

| Instrument | CME code | Contract size | Minimum price tick | Tick value |
| --- | --- | --- | --- | --- |
| NYMEX WTI Light Sweet Crude Oil | CL | 1,000 barrels | $0.01/barrel | $10 |
| NYMEX Brent Crude Oil Last Day Financial | BZ | 1,000 barrels | $0.01/barrel | $10 |

Official specification references:

- [CME WTI contract specifications](https://www.cmegroup.com/markets/energy/crude-oil/light-sweet-crude.contractSpecs.html)
- [CME Brent Last Day Financial contract specifications](https://www.cmegroup.com/markets/energy/crude-oil/brent-crude-oil-last-day.contractSpecs.html)

BZ is the CME financial Brent contract reference; do not silently equate it to an expiry-matched ICE position. The multipliers and outright tick sizes were verified on November 6, 2026 against the CME specification data for [CL (product 425)](https://www.cmegroup.com/CmeWS/mvc/ContractSpecs/List/productId/425) and [BZ (product 424)](https://www.cmegroup.com/CmeWS/mvc/ContractSpecs/List/productId/424): both are 1,000 barrels with a $0.01/barrel ($10) outright tick. Yahoo symbol histories do not establish actual contracts held or roll executions.

For direction `s` (+1 long spread, −1 short spread) and quantity `q` on each leg:

```text
Daily gross P&L = held s × q × (1,000 × change in Brent − 1,000 × change in WTI)
```

A $1/barrel favorable change in the spread yields $1,000 gross per contract pair, not $1.

Default configurable costs per contract, per leg, per execution:

- Commission: **$2.50**.
- Slippage: **one tick = $10**.
- Opening one pair costs $25; closing it costs another $25. A round trip costs $50.

Costs apply to every executed position change and scale with quantity. Any open position is liquidated at the final observed close and charged exit costs; no new position opens on the last row. This bookkeeping convention is identified in the trade ledger. It can affect terminal results.

## Metric definitions

- **Gross / net P&L:** cumulative dollar changes before / after commissions and slippage.
- **Sharpe:** `sqrt(252) × mean(daily net P&L / reference capital) / sample std(...)`. Reference capital is a fixed $100,000, interest is zero, and flat days are included. This is a P&L-based risk summary, not a return on actual futures margin or a compounded equity return. Fixed scaling cancels in the ratio.
- **Profit factor:** sum of positive closed-trade net P&L divided by absolute sum of negative closed-trade net P&L. N/A when there are no losing trades, rather than a fabricated finite value.
- **Win rate:** fraction of completed trades with strictly positive net P&L; break-even trades are not wins. N/A when no trades closed.
- **Maximum drawdown:** largest dollar fall from a previous cumulative net P&L peak, including the starting zero balance.
- **Number of trades:** completed round trips, including final forced liquidation.

No margin calls, collateral interest, financing, liquidity, actual roll trades, or risk-based position sizing are modeled. The simulated equal quantity is an assumption, not an optimized hedge ratio. Default thresholds are a simple in-sample illustration; there is no out-of-sample validation. Repeated dashboard tuning creates overfitting risk.

## Verification status and results

The automated tests cover spread and sample-standard-deviation Z-scores, future-data independence, signal state transitions, next-close execution, both-leg contract P&L, costs, final liquidation, loss/win metrics, missing data, downloader behavior, and dashboard rendering. Tests use explicitly synthetic deterministic fixtures solely to verify software; those fixtures are never presented as market observations.

### Archived original run — November 6, 2026

This snapshot used entry ±2. It is retained as historical evidence, not the current ±1.5 simulation.

Continued from implementation commit `666b48c` without changing the strategy or tuning its parameters. Yahoo Finance downloads succeeded for both tickers. The request covered November 6, 2021 through November 6, 2026 (exclusive); cleaning produced **1,256 matched daily observations from November 8, 2021 through November 5, 2026**. Missing pairs were dropped without filling. Current-day data were excluded.

Default assumptions: 20-observation rolling window, entry beyond ±2, exit band ±0.25 (including zero crossings), one 1,000-barrel contract on each leg, $2.50 commission and one $10 slippage tick per leg per execution. Signals execute at the next close, and P&L begins after execution. Any remaining trade closes at the final observation.

| Statistical measure | Observed result |
| --- | ---: |
| Pearson price correlation | 0.989122 |
| Mean Brent − WTI spread | $4.441608/barrel |
| Sample spread standard deviation | $2.097708/barrel |
| ADF statistic | −3.261097 |
| ADF p-value | 0.016710 |
| Engle–Granger statistic | −3.500466 |
| Engle–Granger p-value | 0.032354 |

At the 5% level, the ADF test rejects its unit-root null for this spread, and Engle–Granger rejects its no-cointegration null. These are sample-specific findings, not proof of persistent mean reversion. Engle–Granger estimates a different hedge coefficient; its result alone does not validate the 1:1 trade. Full-sample tests did not influence any signals.

| Illustrative simulation metric | Result |
| --- | ---: |
| Gross P&L | $58,320.03 |
| Estimated commissions and slippage | $2,500.00 |
| **Net P&L** | **$55,820.03** |
| Annualized P&L-based Sharpe | 1.0744 |
| Profit factor, after costs | 6.9829 |
| Win rate, after costs | 70.0% |
| Maximum dollar drawdown | $7,070.00 |
| Completed trades | 50 |

**These are computed continuous-series simulation results, not verified executable profits.** In particular, the source spread changes by $15.93/barrel on April 1, 2026; other large daily changes include $7.14 on June 1, 2022 and $7.07 on March 31, 2026. Their causes are not established by these data. Roll transitions, different expiries and adjustments can create apparent gains that a real matched-contract portfolio could not earn. No observations were removed to improve results. The favorable metrics do not establish a tradable edge; contract-level and out-of-sample validation remain outside this beginner project.

### Saved evidence and reproduction

- [Full-precision results and provenance](results/2026-11-06.json): sample dates, parameters, versions, source references and SHA-256 of the cleaned CSV.
- [Closed-trade ledger](results/2026-11-06-trades.csv).
- [Four interactive charts](results/2026-11-06-charts.html): download and open this HTML file in a browser; it loads Plotly from its free CDN. GitHub displays the HTML source rather than rendering it.
- `outputs/` retains the cleaned CSV, daily backtest, summary, ledger and four standalone HTML charts with embedded Plotly for offline viewing. These generated files remain ignored by Git; the dated report above is committed.

Run `python data.py` then `python backtest.py` to refresh the analysis, and `streamlit run app.py` to explore it. Later downloads can change due to the moving five-year window and Yahoo revisions; the dated report is a fixed snapshot, not a promise of identical future results.

**Archived validation:** all 12 tests then present passed. A separate run of the actual dashboard against the downloaded CSV rendered all four charts and the expected metrics without application errors. Daily net P&L and costs reconcile to the closed-trade ledger; there are no missing prices or duplicate dates in the cleaned dataset. The Streamlit server started and its health endpoint returned `ok`. That validation describes the archived run only.

## Three accurate résumé bullets

- Developed a Python research application for WTI–Brent futures spread analysis, implementing Yahoo Finance data ingestion, rolling Z-scores, ADF stationarity testing and Engle–Granger cointegration testing.
- Implemented a two-leg futures backtest with next-close signal execution, explicit contract multipliers, configurable commission and slippage, and trade-level P&L and drawdown reporting.
- Built an interactive Streamlit and Plotly dashboard and automated tests covering signal timing, transaction costs, data cleaning and dashboard behavior, with documented continuous-futures rollover limitations.

These bullets describe implemented and tested capabilities. If quoting the historical metrics, label them explicitly as an in-sample continuous-futures simulation and disclose the rollover limitations; do not present them as live returns.
