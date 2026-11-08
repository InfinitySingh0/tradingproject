# WTI–Brent Crude Oil Spread Trading Using Mean Reversion

This project looks at the price difference between Brent and WTI crude oil futures. It uses a rolling Z-score to find potential mean-reversion trades, then backtests them with commissions and slippage. The Streamlit dashboard shows the prices, signals, individual trades and P&L.

The backtest uses Yahoo continuous futures data. Contract rolls can affect both signals and P&L, so the results should be read as a research simulation, not a record of actual trades.

## Overview

- Downloads about five years of daily WTI (`CL=F`) and Brent (`BZ=F`) prices using `yfinance`.
- Aligns and cleans prices, calculates correlation, and runs ADF and Engle–Granger tests.
- Generates entries at **Z-scores beyond ±1.5** and exits near zero (±0.25), using a 20-observation rolling window.
- Uses next-close execution, explicit futures contract multipliers, commissions and slippage.
- Displays four charts: price history, spread with executed trades, Z-score, and cumulative P&L.
- Exports cleaned prices, daily P&L and detailed trades with both legs' entry and exit prices.

The strategy runs on the full dataset, with no train/test split or automatic parameter selection. There is no stop-loss or holding limit: trades stay open until the exit condition is met, or until the dataset ends.

## Run on Windows (PowerShell)

Install Git and **Python 3.12**, which was used to test this project.

### First installation

Clone only if you do not already have the repository folder:

```powershell
git clone https://github.com/InfinitySingh0/tradingproject.git
cd tradingproject
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open **http://localhost:8501** in your browser. The app downloads prices if there is no saved CSV. You do not need to activate the virtual environment when using these commands.

### Update an existing installation

Stop the running dashboard with **Ctrl+C**, open your existing project folder, and pull the latest code:

```powershell
cd C:\Users\MAA\tradingproject
git pull origin main
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Change the folder path to wherever you cloned the repository. If `.venv` is missing, create it with `py -3.12 -m venv .venv`. Resolve any local Git conflicts before updating.

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

No API key or paid data subscription is needed. If a Yahoo download fails, check your connection or retry later. Use the refresh button in the dashboard to update saved prices.

## Strategy

The spread is `Brent price − WTI price`, in dollars per barrel. A Z-score describes how far today's spread is from its recent average:

```text
Z-score = (spread − trailing 20-observation mean) / trailing sample standard deviation
```

The calculation uses only prices available at that day’s close. Z-scores are left blank until there are enough observations, or when the rolling standard deviation is zero.

| Condition | Decision |
| --- | --- |
| Flat and Z > +1.5 | Short spread: sell Brent and buy WTI |
| Flat and Z < −1.5 | Long spread: buy Brent and sell WTI |
| Long and Z ≥ −0.25 | Close both legs |
| Short and Z ≤ +0.25 | Close both legs |
| Otherwise | Hold the position or remain flat |

A trade opens only after the Z-score moves beyond the entry threshold. An exit also triggers if it jumps across zero. The strategy does not reverse direction on the same signal day, and a missing Z-score leaves an existing position open. Settings can be changed in the sidebar.

The ±1.5 entry threshold was chosen after exploring this historical data. It is a default setting, not a value proven to work best. The current version does not test it on unseen data.

### Execution timing

For example, a signal at Monday’s close opens a position at Tuesday’s close, assuming both dates are available. P&L starts with the move from Tuesday’s close to Wednesday’s close.

In the code, `position = signal.shift(1)` describes holdings after today's close; `held_position = position.shift(1)` earns today's close-to-close move. Any remaining position closes at the final observation with exit costs.

## Futures P&L and costs

By default, each trade uses one contract on each leg:

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

### Example trade

This example comes from the [saved backtest ledger](results/2026-11-07-simple-entry-1.5-trades.csv). The entry signal appeared on **January 12, 2022**, with a Z-score of approximately **−2.4428**. The strategy opened a long spread on **January 13**. An exit signal appeared on **January 21** (Z ≈ 0.4849), and the position closed on **January 24**, the next available trading observation.

| Leg | Entry action | Entry price | Exit price | Gross P&L |
| --- | --- | ---: | ---: | ---: |
| Brent | Buy one contract | $84.47 | $86.27 | +$1,800.00 |
| WTI | Sell one contract | $82.12 | $83.31 | −$1,189.99 |

Using the original, unrounded prices:

- **Gross P&L:** approximately **$610.00**
- **Commission:** $10
- **Slippage:** $40
- **Net P&L:** approximately **$560.00**

Both prices rose, but Brent rose more than WTI. The spread widened from approximately **$2.35 to $2.96 per barrel**, benefiting the long-spread position. With a 1,000-barrel multiplier, that $0.61 change produced roughly $610 before costs.

The displayed amounts are rounded; the backtest calculates P&L from the original prices. This is one winning trade from the simulation, not a typical outcome or a live trade.

## Statistics and performance metrics

- **Correlation:** measures co-movement of price levels; it does not establish a mean-reverting spread.
- **ADF:** tests the fixed Brent − WTI spread against a unit-root null. A small p-value is evidence against that null within this sample.
- **Engle–Granger:** tests for cointegration with an estimated coefficient and intercept. A significant result does not by itself validate the equal-quantity spread. Interpretation also relies on integration assumptions that this simple project does not fully establish.
- **Sharpe:** annualized mean daily net P&L divided by its sample standard deviation, using 252 observations/year, zero interest and fixed $100,000 reference capital. Fixed scaling cancels in the ratio. This is not a compounded return or return on actual margin.
- **Profit factor:** positive closed-trade net P&L divided by absolute negative closed-trade net P&L. Undefined denominators display as N/A.
- **Win rate:** proportion of closed trades with positive net P&L; break-even trades are not wins.
- **Maximum drawdown:** largest dollar decline from a prior cumulative net P&L peak, including the starting zero balance.

Full-sample statistical tests describe the data; they do not filter trading signals. The trade count includes final forced liquidation, if needed.

## Results

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

### Limitations

The dataset includes an absolute spread jump of $15.93 per barrel on April 1, 2026. Its cause has not been established. Contract rolls, price adjustments and different expiries can create apparent profits that would not be available in an actual trade. Using `auto_adjust=False` does not resolve these issues. The observations were kept as downloaded after cleaning missing or invalid pairs.

The same history was used to explore the settings and report performance. That limits what these results tell us about future trades. The backtest also leaves out margin requirements, financing, liquidity and actual roll transactions. It does not establish that the strategy would be profitable in live trading.

Results may change when prices are refreshed: the five-year window moves, and Yahoo may revise its data. Other dated files in `results/` are records of earlier versions.

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

Trades closed at the end of the dataset have no exit signal date or Z-score. Those fields are left blank. Dashboard results use the settings in the sidebar; command-line reports use the defaults. Files from older training/testing versions are not used by the current app.

## Testing

The project includes 16 automated tests covering data cleaning, trading signals, execution timing, futures P&L, transaction costs, and dashboard behavior.

Run them with:

```bash
python -m pytest -q
```

**Author:** Ankit Kumar

M.Sc. Mathematics and Computing, IIT (ISM) Dhanbad

[GitHub](https://github.com/InfinitySingh0)
