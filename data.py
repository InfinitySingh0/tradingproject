"""Download and align daily Yahoo futures proxies; never fill missing prices."""
from pathlib import Path
import argparse

import numpy as np
import pandas as pd
import yfinance as yf

DATA_PATH = Path(__file__).parent / "outputs" / "prices.csv"


def clean_prices(prices: pd.DataFrame) -> pd.DataFrame:
    """Keep finite, matched daily observations without forward-filling holidays."""
    result = prices.loc[:, ["WTI", "Brent"]].copy()
    result.index = pd.to_datetime(result.index)
    if result.index.tz is not None:
        result.index = result.index.tz_localize(None)
    result.index = result.index.normalize()
    result = result.apply(pd.to_numeric, errors="coerce")
    result = result.replace([np.inf, -np.inf], np.nan).dropna()
    result = result.loc[~result.index.duplicated(keep="last")].sort_index()
    result.index.name = "Date"
    if result.empty:
        raise ValueError("No matched WTI and Brent prices were available.")
    return result


def download_prices(path: Path = DATA_PATH) -> pd.DataFrame:
    """Fetch roughly five years, excluding today's potentially unfinished bar."""
    end = pd.Timestamp.now(tz="UTC").normalize().tz_localize(None)
    start = end - pd.DateOffset(years=5)
    series = []
    for label, ticker in [("WTI", "CL=F"), ("Brent", "BZ=F")]:
        raw = yf.download(
            ticker, start=start.date(), end=end.date(), interval="1d",
            auto_adjust=False, progress=False, threads=False,
        )
        if raw.empty:
            raise RuntimeError(
                f"Yahoo returned no data for {ticker}. Check network access or "
                "Yahoo rate limits, then retry. No synthetic data is substituted."
            )
        close = raw["Close"]
        if isinstance(close, pd.DataFrame):
            close = close[ticker] if ticker in close else close.iloc[:, 0]
        series.append(close.rename(label))
    prices = clean_prices(pd.concat(series, axis=1))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Replace the cache only after both symbols downloaded and cleaned successfully.
    temporary = path.with_suffix(".tmp")
    prices.to_csv(temporary)
    temporary.replace(path)
    return prices


def load_prices(path: Path = DATA_PATH) -> pd.DataFrame:
    return clean_prices(pd.read_csv(path, index_col="Date", parse_dates=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DATA_PATH)
    args = parser.parse_args()
    frame = download_prices(args.output)
    print(f"Saved {len(frame)} aligned observations: {frame.index.min().date()} "
          f"to {frame.index.max().date()} in {args.output}")
