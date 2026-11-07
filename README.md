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
│   ├── test_project.py
│   └── test_improvements.py
└── outputs/            # Generated locally after a successful download; ignored by Git
```

Generated outputs in `outputs/`:

| File | Contents |
| --- | --- |
| `prices.csv` | Date, WTI, Brent; matched daily closes |
| `training_backtest.csv`, `testing_backtest.csv` | Separate daily positions, P&L, costs and drawdowns |
| `training_trades.csv`, `testing_trades.csv` | Completed trades, costs and holding days |
| `training_monthly.csv`, `testing_monthly.csv` | Monthly mark-to-market P&L |
| `threshold_comparison.csv` | Training metrics, eligibility and selection score for seven entry thresholds |
| `results.json` | Parameters, statistics, data fingerprint and separate segment metrics |
| `training_*.html`, `testing_*.html` | Six charts per segment: prices, spread, Z-score, P&L, correlation and monthly P&L |

The dashboard defaults to the test segment, with a selector for training. It shows both segments' performance separately, plus a training threshold table and Sharpe chart, executed trade markers, a completed-trade summary and CSV downloads. Generated HTML charts embed Plotly for offline viewing. Old unprefixed artifacts from the earlier version may still exist locally; current runs write the prefixed training/testing artifacts above.

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
| Flat and +E < Z-score < +3 | Short spread: sell Brent, buy WTI |
| Flat and −3 < Z-score < −E | Long spread: buy Brent, sell WTI |
| Long and Z-score ≥ −0.25 | Close; also catches a jump across zero |
| Short and Z-score ≤ +0.25 | Close; also catches a jump across zero |
| Long and Z-score ≤ −3, or short and Z-score ≥ +3 | Stop-loss exit at the next close |
| Position reaches the 15-trading-day holding limit | Time exit |
| Otherwise | Hold the existing position or remain flat |

`E` is the entry threshold selected on training (±1.5 in the recorded run below). Thresholds are strict for entry. New entries are blocked at or beyond the stop threshold. Exit takes priority; no immediate reversal on an exit day. Missing indicators hold an existing position unless its holding limit is reached; the warm-up starts flat. Stop threshold (default ±3) and holding limit (default 15) are configurable in the sidebar. Require `exit_band < entry < stop_z` and a positive integer holding limit.

**Timing matters:** a signal calculated at Monday's close executes at Tuesday's close (or the next matched observation). The first earned price change is Tuesday close to Wednesday close. Tuesday's close-to-close move is not credited to a position that only opens Tuesday evening.

In code, `signal` is the desired state, `position = signal.shift(1)` is the state after today's close, and `held_position = position.shift(1)` earns today's move. This is deliberately more conservative than treating a just-computed closing-price signal as executable at that same close. Slippage approximates imperfect fills; it does not establish that the closing prices were available in practice.

A stop uses a closing Z-score and executes at the **next** close, like every other signal. It is not an intraday stop order, a guaranteed fill, or a dollar-loss cap; Z-scores themselves change with rolling volatility. If an entry is signaled at observation `i`, it executes at `i+1`; a time exit is signaled at `i+15` and executes at `i+16`, giving 15 held close-to-close intervals. Days mean matched trading observations, not calendar days. Gaps caused by missing data can increase elapsed calendar time. After an exit, a fresh eligible signal may enter again on a later observation.

## Training-only entry selection

The dashboard and `python backtest.py` now compare **1.0, 1.25, 1.5, 1.75, 2.0, 2.25 and 2.5** using only the first 70% of observations. The entry input is replaced by the selected threshold. Stop-loss stays at ±3 by default, holding limit at 15 matched trading intervals, and the mean-reversion exit at ±0.25. Other sidebar settings remain configurable and apply equally to all candidates. To compare all seven entries, require exit band < 1 and stop threshold > 2.5.

The rule is specified before inspecting these candidate results:

1. Require **at least 10 completed training trades** and a finite Sharpe. Ten trades is a simple minimum screen, not proof of statistical reliability.
2. Among eligible candidates, rank Sharpe descending and maximum dollar drawdown ascending. Tied values receive the smallest shared rank (`method="min"`). The selection score is the average of those two ranks; lower is better.
3. Break score ties by higher Sharpe, then lower entry threshold. Net P&L and profit factor are shown for context, not optimized separately.
4. If none qualify, report no selection and skip the test backtest. Do not silently reduce the trade requirement or fall back to a profitable-looking candidate.

Rank weights and minimum count are deliberately simple and arbitrary research choices. The rule may select a negative-return candidate if all eligible candidates are poor; selection is not a profitability guarantee. Comparing multiple candidates can overfit training even without test leakage.

The selector accepts **only training prices**. After selection, the winning entry is frozen and tested once per analysis invocation at the specified costs. No test entry grid or test slippage sweep is calculated. The winner's training backtest is rerun only to build its detailed ledger. Streamlit reruns recompute the same deterministic analysis; they are not new independent evaluations. Repeatedly changing settings after viewing test results would compromise validation.

**Previously inspected holdout:** this dataset's last 30% was already viewed in earlier project runs. Code now excludes those prices from selection, but we cannot truthfully call this historical period untouched. A genuinely untouched experiment would require freezing these choices before obtaining new future observations.

## Detailed trade ledger

Each completed trade now records direction, contract quantity per leg, buy/sell side for Brent and WTI, executed entry/exit dates, decision dates and available decision Z-scores, both legs' entry/exit prices, entry/exit spreads, trading intervals held, leg-level gross dollar P&L, total gross/net P&L, separate commissions and slippage, and a final-liquidation flag. These fields appear in the dashboard and exported CSVs.

Prices are **execution-date Yahoo proxy closes in USD/barrel**, not demonstrated executable fills. Slippage is charged in dollars separately, so it is not also applied to the displayed prices. Entry and normal exit decision dates precede execution by one matched observation. Final forced liquidation has no decision date/Z-score. Missing Z-scores are blank, not fabricated. Leg-level P&L sums to gross P&L, and gross minus both costs reconciles to net. Contract multipliers and lagged execution are unchanged.

## Chronological validation and performance analysis

- Split once at `floor(0.70 × number_of_observations)`: the first 70% is training and the remainder testing. No shuffling or test-driven selection is performed. Only the seven specified entry thresholds are compared on training; the rule below selects one before testing.
- Use the training-selected entry and the same rolling window, exit threshold, stop threshold, holding limit, quantities and cost assumptions in both segments. Trailing test indicators may use earlier training prices and subsequently observed test prices; they never use future prices.
- Training ends with a charged liquidation; testing starts flat, with no carried position or pending signal. The first test signal executes on the second test close. Each segment starts its P&L and drawdown accounting at zero, and final liquidation costs are included.
- Both segments have independent metrics and trade ledgers. Changing sidebar settings applies the same settings to both; repeatedly choosing settings after viewing test performance would invalidate a clean holdout claim.
- **This is retrospective holdout validation:** the earlier project already inspected the full history. The chronological partition prevents computational leakage but cannot make previously viewed data genuinely unseen. There is no claim of a pristine out-of-sample experiment or live profitability.
- The earlier fixed-threshold workflow supports cost sensitivity at 1, 2, 3 and 5 slippage ticks per leg per execution. The current selection workflow does not sweep test costs or test entry thresholds; it evaluates only the winner at the configured costs. `slippage_sensitivity` remains available for separate training-only analysis. At one pair and $2.50 commission, total round-trip costs are $50, $90, $130 and $210 respectively.
- The 60-observation rolling Pearson correlation is between **price levels**, not returns. It is descriptive, uses only trailing data, and is not a signal filter. Initial unavailable values remain missing.
- Monthly bars sum daily net mark-to-market P&L and costs in their calendar month, including partial months at segment boundaries. This differs from allocating an entire trade to its exit month. Monthly totals reconcile to segment net P&L.
- Completed-trade summaries show wins/losses/break-even trades, average/best/worst net P&L, and average/maximum held trading intervals. Empty ledgers display undefined averages as N/A rather than invented values.

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

No margin calls, collateral interest, financing, liquidity, actual roll trades, or risk-based position sizing are modeled. The simulated equal quantity is an assumption, not an optimized hedge ratio. A fixed-parameter chronological holdout is reported separately from training; the previously inspected history limits its evidential strength. Repeated dashboard tuning creates overfitting risk.

## Verification status and results

The automated tests cover spread and sample-standard-deviation Z-scores, future-data independence, signal state transitions, next-close execution, both-leg contract P&L, costs, final liquidation, loss/win metrics, missing data, downloader behavior, and dashboard rendering. Tests use explicitly synthetic deterministic fixtures solely to verify software; those fixtures are never presented as market observations.

### Current training-selected run — November 7, 2026

Uses the same cached Yahoo observations (2021-11-08 through 2026-11-05): 879 training observations ending 2025-05-08 and 377 test observations beginning 2025-05-09. No data were fabricated or refreshed for this comparison. All other settings use the defaults documented above.

| Training entry | Net P&L | Sharpe | Profit factor | Max drawdown | Completed trades | Selection score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | $38,420.02 | 1.1687 | 4.1135 | $6,610.00 | 77 | 4.5 |
| 1.25 | $40,350.02 | 1.3082 | 5.4635 | $7,189.98 | 65 | 4.5 |
| 1.5 | $40,910.01 | 1.3659 | 6.8443 | $5,529.99 | 55 | 2 |
| 1.75 | $19,540.02 | 0.9089 | 3.4892 | $6,009.99 | 45 | 4.5 |
| 2 | $9,250.02 | 0.5795 | 2.2252 | $6,009.99 | 36 | 5.5 |
| 2.25 | $10,080.02 | 0.9115 | 5.0000 | $2,369.99 | 25 | 2.5 |
| 2.5 | $8,520.02 | 0.8447 | 6.3924 | $2,369.99 | 16 | 3.5 |

**Selected entry: ±1.5**, using training results only. At that threshold the single test evaluation reports $46,640.00 net P&L, Sharpe 1.7667, profit factor 14.9641, maximum drawdown $7,070.00 and 21 completed trades. This favorable simulation is not verified trading profitability: rollover effects, large proxy-price jumps, training selection bias and prior inspection of the holdout remain material limitations.

Evidence: [full results and selection rule](results/2026-11-07-threshold-selection.json), [training comparison CSV](results/2026-11-07-threshold-comparison.csv), [detailed selected training trades](results/2026-11-07-selected-training-trades.csv), and [detailed selected test trades](results/2026-11-07-selected-testing-trades.csv). The dashboard adds a training Sharpe-versus-entry chart with the chosen threshold marked. No candidate-level test performance table is generated.

**Validation:** all 29 tests pass. Tests perturb only test prices and verify unchanged training scores and selection; instrument backtest calls to require exactly one test evaluation; cover insufficient-trade behavior and ranking; and reconcile detailed leg prices, gross P&L and fees for both directions. The actual-data dashboard also renders the selected threshold and seven charts successfully. A headless system-Chromium check verified the selected-threshold message and detailed-trade tab. Existing pandas/NumPy month-end deprecation warnings remain non-fatal.

### Archived fixed-entry risk-managed validation — November 7, 2026

This snapshot used entry ±2 before training-only threshold selection was added. It is not the current selected-threshold result.

This run reuses the **same 1,256-row Yahoo dataset downloaded November 6, 2026**, ending November 5, 2026; it does not claim to include newer observations. Its SHA-256 matches the archived source snapshot. No synthetic prices, parameter search or test-based tuning were used. Defaults: 20-day Z-score, entry ±2, mean-reversion exit ±0.25, stop ±3, maximum 15 held trading intervals, one contract per leg, $2.50 commission and one tick slippage per leg per execution.

| Measure | Training (70%) | Testing (30%) |
| --- | ---: | ---: |
| Dates | 2021-11-08 – 2025-05-08 | 2025-05-09 – 2026-11-05 |
| Observations | 879 | 377 |
| Gross P&L | $11,050.02 | $44,820.01 |
| Estimated costs | $1,800.00 | $650.00 |
| Net P&L | $9,250.02 | $44,170.01 |
| Annualized P&L-based Sharpe | 0.5795 | 1.6919 |
| Profit factor | 2.2252 | 21.9337 |
| Win rate | 61.11% | 92.31% |
| Maximum drawdown | $6,009.99 | $7,070.00 |
| Completed trades | 36 | 13 |
| Winning / losing trades | 22 / 14 | 12 / 1 |
| Average net P&L per trade | $256.94 | $3,397.69 |
| Average holding intervals | 5.69 | 8.69 |
| Maximum holding intervals | 15 | 15 |

The test profit factor is based on **only one losing trade among 13 trades**. The test segment also contains the previously documented large continuous-series jumps. These favorable historical numbers do not establish a reliable or executable trading edge. Dollar P&L is not a return on actual margin; no capital or liquidity adequacy claim is made.

| Slippage ticks per leg per execution | Training net P&L | Testing net P&L |
| --- | ---: | ---: |
| 1 | $9,250.02 | $44,170.01 |
| 2 | $7,810.02 | $43,650.01 |
| 3 | $6,370.02 | $43,130.01 |
| 5 | $3,490.02 | $42,090.01 |

Evidence: [full-precision validation and sensitivity](results/2026-11-07-validation.json), [training trades](results/2026-11-07-training-trades.csv), [test trades](results/2026-11-07-testing-trades.csv), and [six charts per segment](results/2026-11-07-charts.html). Download the HTML to view it in a browser; it loads Plotly from a free CDN. Locally generated `outputs/training_*.html` and `outputs/testing_*.html` embed Plotly for offline use.

**Validation:** all 23 tests pass, retaining coverage of the original behavior and adding stop boundaries, executed holding periods, split isolation, correlation, cost sensitivity, monthly reconciliation and trade-summary tests. The original signal fixture now stays inside the new entry stop boundary, and the dashboard expectation increases from four to six charts. Actual-data dashboard checks verified both segment selections and their displayed metrics. Daily, monthly and trade-ledger net P&L reconcile. A dependency-level pandas/NumPy deprecation warning is emitted during month-end resampling; the aggregation and reconciliation checks pass.

### Archived baseline — November 6, 2026

The following baseline predates stop-loss, holding limits and the chronological split. It is retained for provenance and does **not** describe the current strategy.

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

**Baseline validation:** all 12 tests then present passed. A separate run of the actual dashboard against the downloaded CSV rendered all four charts and the expected metrics without application errors. Daily net P&L and costs reconcile to the closed-trade ledger; there are no missing prices or duplicate dates in the cleaned dataset. The Streamlit server started and its health endpoint returned `ok`. This statement describes the archived baseline run only.

## Three accurate résumé bullets

- Developed a Python research application for WTI–Brent futures spread analysis, implementing Yahoo Finance data ingestion, rolling Z-scores, ADF stationarity testing and Engle–Granger cointegration testing.
- Implemented a two-leg futures backtest with next-close signal execution, explicit contract multipliers, configurable commission and slippage, and trade-level P&L and drawdown reporting.
- Built an interactive Streamlit and Plotly dashboard and automated tests covering signal timing, transaction costs, data cleaning and dashboard behavior, with documented continuous-futures rollover limitations.

These bullets describe implemented and tested capabilities. If quoting the historical metrics, label them explicitly as an in-sample continuous-futures simulation and disclose the rollover limitations; do not present them as live returns.
