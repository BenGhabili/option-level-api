import yfinance as yf
import pandas as pd
from fastapi import HTTPException

def get_latest_close(ticker: str) -> float:
    tk = yf.Ticker(ticker)
    hist = tk.history(period="1d")
    if hist.empty:
        raise HTTPException(status_code=404, detail=f"No price data for {ticker}")
    return float(hist["Close"].iloc[-1])

def select_expiry(ticker: str, expiry_param: str) -> str:
    tk = yf.Ticker(ticker)
    options = tk.options

    # print(f"[DEBUG] Available expiries for {ticker}: {options[:5]}")
    if not options:
        raise HTTPException(status_code=404, detail=f"No expiries for {ticker}")
    if expiry_param in ("today", "front"):
        return options[0]
    if expiry_param in ("next", "tomorrow"):
        return options[1]
    if expiry_param in options:
        return expiry_param
    raise HTTPException(status_code=400, detail="Invalid expiry")


def fetch_chain(ticker: str, expiry: str) -> pd.DataFrame:
    """
    Fetch calls+puts and add ‘expiration’ and ‘underlyingPrice’ columns
    so downstream code can compute time-to-expiry and GEX.
    """
    tk = yf.Ticker(ticker)

    # Get the underlying price once
    hist = tk.history(period="1d")
    if hist.empty:
        raise HTTPException(status_code=404, detail=f"No price data for {ticker}")
    underlying = float(hist["Close"].iloc[-1])

    # Fetch the option chain
    chain = tk.option_chain(expiry)
    calls = chain.calls.copy()
    puts  = chain.puts.copy()

    # print(f"[DEBUG] Fetching chain for {ticker} @ expiry {expiry}")
    # print(f"[DEBUG]   calls: {len(calls)}, puts: {len(puts)}")

    # Tag each DataFrame with the expiry and underlying price
    for df in (calls, puts):
        df["expiration"]      = expiry
        df["underlyingPrice"] = underlying

    return pd.concat([calls, puts], ignore_index=True)
