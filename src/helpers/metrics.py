import numpy as np
import pandas as pd
from datetime import datetime
import math

def norm_pdf(x):
    return math.exp(-0.5*x*x) / math.sqrt(2*math.pi)

def filter_strikes(df: pd.DataFrame, center: float, width: float) -> pd.DataFrame:
    low, high = center - width, center + width
    return df[df["strike"].between(low, high)]

def bs_gamma(S, K, T, r, sigma, q=0):
    if T <= 0 or sigma <= 0 or np.isnan(S) or np.isnan(K) or np.isnan(T) or np.isnan(sigma):
        return 0.0
    d1 = (np.log(S/K) + (r - q + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
    return math.exp(-q*T) * norm_pdf(d1) / (S * sigma * math.sqrt(T))

def aggregate_oi(df: pd.DataFrame, include_greeks: bool=False, allow_negative_T=False):
    # print(f"[DEBUG] pre‑drop rows={len(df)}  missing OI={df['openInterest'].isna().sum()}")
    df = df.dropna(subset=["openInterest", "strike"])
    df["expiration"] = pd.to_datetime(df["expiration"])
    now = datetime.utcnow()
    df["T"] = (df["expiration"] - now).dt.total_seconds()/(365*24*3600)

    if not allow_negative_T:
        df = df[df["T"]>=0]
        df = df[df["impliedVolatility"] > 0]

    results = []
    for strike, group in df.groupby("strike"):
        # print("HERE!!")
        calls = group[group["contractSymbol"].str.contains("C")]
        puts  = group[group["contractSymbol"].str.contains("P")]
        call_oi = int(calls["openInterest"].sum())
        put_oi  = int(puts["openInterest"].sum())

        entry = {"strike": float(strike), "call_OI": call_oi, "put_OI": put_oi}
        if include_greeks:
            iv = float(group["impliedVolatility"].mean())
            S  = group["underlyingPrice"].iloc[0]
            r  = 0.01
            total_gamma = sum(
                # bs_gamma(S, strike, row.T, r, row.impliedVolatility)
                bs_gamma(S, strike, row["T"], r, row["impliedVolatility"])
                for _, row in group.iterrows()
            )
            entry.update({"iv": iv, "GEX": total_gamma * (S**2) * 100})
        # print(f"[DBG] {strike}  callOI={call_oi}  putOI={put_oi}")
        results.append(entry)
    return sorted(results, key=lambda x: x["strike"])
