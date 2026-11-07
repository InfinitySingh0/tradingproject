# WTI–Brent Crude Oil Spread Trading Using Mean Reversion

A beginner-friendly Python research project that studies the **Brent − WTI** crude oil price spread, generates mean-reversion signals, and simulates two-leg futures P&L after transaction costs. Explore the results in a Streamlit dashboard built with Plotly.

**Exploratory research only.** Yahoo continuous futures are price proxies. Rollover effects can distort signals and simulated profits; these results are not verified executable or live-trading performance.

## What the project does

- Downloads approximately five years of daily WTI (`CL=F`) and Brent (`BZ=F`) prices with free `yfinance` access.
- Aligns and cleans prices, calculates correlation, and runs ADF and Engle–Granger tests.
- Trades a 20-observation rolling spread Z-score with **default entry ±1.5** and mean-reversion exit near zero (±0.25).
- Uses next-close execution, explicit futures contract multipliers, commissions and slippage.
- Displays four charts: price history, spread with executed trades, Z-score, and cumulative P&L.
- Exports cleaned prices, daily P&L and detailed trades with both legs' entry and exit prices.

The current version uses the entire sample. It has **no train/test split, stop-loss, maximum holding period or automatic threshold selection**. A position stays open until the mean-reversion exit or final-sample liquidation. Holding duration in the ledger is descriptive, not a limit. There are no monthly P&L, rolling-correlation or slippage-comparison features in the current app.

## Run on Windows (PowerShell)

Install Git and **Python 3.12** (the tested Python version).

### First installation

Clone only if you do not already have the repository folder:

```powershell
git clone https://github.com/InfinitySingh0/tradingproject.git
cd tradingproject
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open **http://localhost:8501**. The app downloads prices automatically if its local CSV is missing. These commands use the virtual environment directly, so PowerShell script activation is unnecessary.

### Update an existing installation

Stop the running dashboard with **Ctrl+C**, open your existing project folder, and pull the latest code:

```powershell
cd C:\Users\MAA\tradingproject
git pull origin main
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Replace the folder path if you cloned elsewhere. If `.venv` does not exist, run `py -3.12 -m venv .venv` before installing dependencies. If Git reports conflicting local changes, preserve and resolve them before pulling; do not delete the folder or discard your work blindly.

To refresh prices and generate CSV/HTML reports outside the dashboard:

```powershell
.\.venv\Scripts\python.exe data.py
.\.venv\Scripts\python.exe backtest.py
```

To run the tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Run on macOS, Linux or the cloud workspace

From the repository root (`/workspace/tradingproject` in the prepared cloud environment):

```bash
python3.12 -m venv .venv   # First setup only; reuse an existing environment
source .venv/bin/activate
python -m pip install -r requirements.txt
python data.py
python backtest.py
streamlit run app.py
```

If the environment already has dependencies installed, activate `.venv` and run `streamlit run app.py`. Run tests with `python -m pytest -q`.

No API key, paid dataset or brokerage account is needed. Yahoo can rate-limit requests or change its endpoints. A failed download produces an error rather than invented prices. Retry later or check network access; keep TLS verification enabled. Use the dashboard's refresh button to update a cached CSV.

## Strategy in plain language

The spread is `Brent price − WTI price`, in dollars per barrel. A Z-score describes how far today's spread is from its recent average:

```text
Z-score = (spread − trailing 20-observation mean) / trailing sample standard deviation
```

Only data available through that close enter the rolling calculation. The warm-up and zero-volatility windows have no valid Z-score.

| Condition | Decision |
| --- | --- |
| Flat and Z > +1.5 | Short spread: sell Brent and buy WTI |
| Flat and Z < −1.5 | Long spread: buy Brent and sell WTI |
| Long and Z ≥ −0.25 | Close both legs |
| Short and Z ≤ +0.25 | Close both legs |
| Otherwise | Hold the position or remain flat |

Entry comparisons are strict. Exit rules also catch a jump across zero. There is no immediate reversal on an exit day. Missing Z-scores hold an existing position. Entry, exit band, rolling window, quantities and costs can be changed in the sidebar.

**Why ±1.5?** It is the current chosen default, not a theoretically optimal threshold or a guarantee of profits. It was chosen after earlier exploration of this history. The current program does not optimize it or validate it on unseen data.

### Execution timing

A signal from Monday's close executes at Tuesday's close (or the next matched observation). Its first earned move is Tuesday close to Wednesday close. It does not earn the price move before its entry.

In the code, `position = signal.shift(1)` describes holdings after today's close; `held_position = position.shift(1)` earns today's close-to-close move. Any remaining position closes at the final observation with exit costs.

## Futures P&L and costs

Assume equal integer contract quantities, initially one per leg:

| Contract reference | Code | Multiplier | Outright tick size | Dollar tick value |
| --- | --- | ---: | ---: | ---: |
| NYMEX WTI Light Sweet Crude Oil | CL | 1,000 barrels | $0.01/barrel | $10 |
| NYMEX Brent Last Day Financial | BZ | 1,000 barrels | $0.01/barrel | $10 |

These values were checked against CME specifications on November 6, 2026: [WTI](https://www.cmegroup.com/markets/energy/crude-oil/light-sweet-crude.contractSpecs.html) and [Brent](https://www.cmegroup.com/markets/energy/crude-oil/brent-crude-oil-last-day.contractSpecs.html). BZ is the CME financial Brent reference; Yahoo histories do not establish which executable, expiry-matched contracts were held.

```text
Daily gross P&L = held direction × quantity × (1,000 × Brent change − 1,000 × WTI change)
```

Direction is +1 for a long spread and −1 for a short spread. A favorable $1/barrel spread change gives $1,000 gross per pair, not $1.

Defaults are **$2.50 commission plus one $10 slippage tick per contract, per leg, per execution**. One pair costs $25 to open and $25 to close: **$50 per round trip**. Slippage is deducted as cash; it is not also applied to the displayed entry/exit prices.

### A worked trade from the saved ledger

The first trade in the [current saved ledger](results/2026-11-07-simple-entry-1.5-trades.csv) was a long spread. Its entry signal was December 22, 2021 (Z ≈ −1.5422), executed December 23. The exit signal was January 4, 2022 (Z ≈ 0.1190), executed January 5.

| Leg | Entry action | Entry close | Exit close | Gross P&L |
| --- | --- | ---: | ---: | ---: |
| Brent | Buy one contract | $76.85 | $80.80 | +$3,950.00 |
| WTI | Sell one contract | $73.79 | $77.85 | −$4,060.00 |

Total gross P&L was approximately **−$109.99**. Subtract $10 commission and $40 slippage for **−$159.99 net P&L**. Values in the table are rounded; calculations use full-precision downloaded prices.

This is a useful example of why a Z-score exit near zero does **not** guarantee profit: rolling mean and volatility change, execution is delayed, and costs must be paid.

## Statistics and performance metrics

- **Correlation:** measures co-movement of price levels; it does not establish a mean-reverting spread.
- **ADF:** tests the fixed Brent − WTI spread against a unit-root null. A small p-value is evidence against that null within this sample.
- **Engle–Granger:** tests for cointegration with an estimated coefficient and intercept. A significant result does not by itself validate the equal-quantity spread. Interpretation also relies on integration assumptions that this simple project does not fully establish.
- **Sharpe:** annualized mean daily net P&L divided by its sample standard deviation, using 252 observations/year, zero interest and fixed $100,000 reference capital. Fixed scaling cancels in the ratio. This is not a compounded return or return on actual margin.
- **Profit factor:** positive closed-trade net P&L divided by absolute negative closed-trade net P&L. Undefined denominators display as N/A.
- **Win rate:** proportion of closed trades with positive net P&L; break-even trades are not wins.
- **Maximum drawdown:** largest dollar decline from a prior cumulative net P&L peak, including the starting zero balance.

Full-sample statistical tests describe the data; they do not filter trading signals. The trade count includes final forced liquidation, if needed.

## Recorded results and limitations

The saved November 7, 2026 run used **1,256 matched observations from November 8, 2021 to November 5, 2026**, downloaded on November 6. Settings: 20-observation window, entry ±1.5, exit ±0.25, one pair, and the costs above.

| Measure | Recorded simulation |
| --- | ---: |
| Gross P&L | $94,700.02 |
| Commissions and slippage | $3,550.00 |
| Net P&L | $91,150.02 |
| Sharpe | 1.5079 |
| Profit factor | 13.8743 |
| Win rate | 83.10% |
| Maximum drawdown | $7,070.00 |
| Completed trades | 71 |
| Price correlation | 0.9891 |
| ADF p-value | 0.0167 |
| Engle–Granger p-value | 0.0324 |

[Full-precision results and dataset hash](results/2026-11-07-simple-entry-1.5.json) · [Detailed trades](results/2026-11-07-simple-entry-1.5-trades.csv)

At the 5% level, both tests reject their respective null hypotheses in this sample. This does not prove persistent mean reversion or an executable trading edge.

**The favorable P&L needs particular caution.** The source includes a $15.93/barrel absolute spread jump on April 1, 2026. Its cause is not established. Continuous-series rolls, adjustments and mismatched expiries can create apparent gains that a real portfolio could not earn. `auto_adjust=False` does not remove these issues. No observations were removed to improve results.

The analysis is entirely in-sample and parameters have been explored on this history. It provides no independent evidence of future performance. There is no margin, financing, liquidity or actual roll-transaction model, and no stop-loss or holding limit. The research conclusion is that the data support further investigation—not that a profitable live strategy has been demonstrated.

New downloads may change the sample and results because the five-year window moves and Yahoo can revise history. Other dated files in `results/` are archived experiments, not current application behavior.

## Project files and outputs

```text
tradingproject/
├── app.py                      # Streamlit dashboard and Plotly charts
├── data.py                     # Yahoo downloads, cleaning and CSV cache
├── strategy.py                 # Indicators, statistical tests and trading rules
├── backtest.py                 # Execution, dollar P&L, costs and trade ledger
├── requirements.txt
├── README.md
├── tests/
│   ├── test_project.py
│   └── test_trade_details.py
├── results/                    # Dated research snapshots
└── outputs/                    # Generated locally; ignored by Git
```

Data cleaning sorts and deduplicates dates, removes invalid/missing pairs without forward-filling, and retains negative prices. Current-day bars are excluded. Matching dates does not guarantee simultaneous settlements or matching expiries.

`python backtest.py` reads the cached prices (or downloads if missing) and writes:

| Output | Contents |
| --- | --- |
| `prices.csv` | Cleaned WTI and Brent closes; created by the downloader |
| `backtest.csv` | Daily signals, positions, P&L, fees and drawdowns |
| `trades.csv` | Both legs' entry/exit prices, spreads, decision dates/Z-scores, sides, quantity, holding duration, P&L and fees |
| `results.json` | Statistics, assumptions, parameters, metrics and dataset hash |
| `prices.html`, `spread.html`, `zscore.html`, `pnl.html` | Interactive charts with Plotly embedded for offline viewing |

Final liquidations have no exit decision date or decision Z-score. Missing values remain blank. The dashboard provides CSV downloads and recalculates its displays when settings change; CLI reports use the default parameters. Old training/testing or threshold files are not read by the current app.

## Validation and résumé use

The current implementation passed **16 automated tests**, plus actual-data Streamlit and Chromium checks. Tests cover spread/Z-score arithmetic, future-data independence, mean-reversion signals, lagged execution, multipliers, costs, final liquidation, data cleaning, downloader failures, detailed trade accounting and dashboard rendering. Synthetic fixtures are used only for software tests, never as historical results. This README update does not change strategy code.

Accurate résumé bullets:

- Developed a Python research application for WTI–Brent futures spreads with Yahoo Finance ingestion, rolling Z-scores, ADF testing and Engle–Granger cointegration analysis.
- Implemented a two-leg futures simulation with lagged execution, explicit contract multipliers, commissions, slippage and detailed trade-level accounting.
- Built an interactive Streamlit/Plotly dashboard and automated tests, documenting continuous-futures rollover effects and in-sample validation limitations.

Describe the project as exploratory research. If quoting any metric, state its sample, assumptions and limitations; do not present it as live performance.
