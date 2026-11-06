# WTI–Brent Crude Oil Spread Trading Using Mean Reversion

A small Python research project exploring whether the daily **Brent − WTI** crude oil price spread offers mean-reversion opportunities. Includes Yahoo Finance downloads, statistical tests, a transparent two-leg futures simulation, and a Streamlit dashboard.

**Exploratory analysis, not verified trading performance.** Yahoo continuous futures symbols are price proxies, not a history of executable, expiry-matched contracts. No profitability is assumed or promised.

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
│   └── test_project.py
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
| Flat and Z-score > +2 | Short spread: sell Brent, buy WTI |
| Flat and Z-score < −2 | Long spread: buy Brent, sell WTI |
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

BZ is the CME financial Brent contract reference; do not silently equate it to an expiry-matched ICE position. These specification values are encoded explicitly, but **live source verification was blocked by the build environment's network policy**. Recheck the official references before relying on results. Yahoo symbol histories do not establish actual contracts held or roll executions.

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

**Historical performance is not reported yet.** The build environment denied Yahoo Finance and CME connections with HTTP 403 at its outbound proxy. Consequently, a real historical dataset, actual test statistics, historical charts and profitability results could not be generated or verified here. The dashboard reports this failure instead of showing invented results.

The environment draft contains requests to allow `query1.finance.yahoo.com`, `query2.finance.yahoo.com`, `fc.yahoo.com`, `guce.yahoo.com`, `consent.yahoo.com`, and `www.cmegroup.com`. These are domain settings, not credentials. After network settings are applied, run `python data.py` followed by `python backtest.py` to generate the real results, and verify the contract specification references. No network restrictions or TLS checks are bypassed by this project.

## Three accurate résumé bullets

- Developed a Python research application for WTI–Brent futures spread analysis, implementing Yahoo Finance data ingestion, rolling Z-scores, ADF stationarity testing and Engle–Granger cointegration testing.
- Implemented a two-leg futures backtest with next-close signal execution, explicit contract multipliers, configurable commission and slippage, and trade-level P&L and drawdown reporting.
- Built an interactive Streamlit and Plotly dashboard and automated tests covering signal timing, transaction costs, data cleaning and dashboard behavior, with documented continuous-futures rollover limitations.

These describe implemented capabilities, not achieved trading performance. Do not claim a Sharpe ratio, return or profitable strategy until real-data runs have been completed and reviewed.
