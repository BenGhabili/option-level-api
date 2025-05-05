from typing import Dict
from helpers.data_fetcher import get_latest_close, select_expiry, fetch_chain
from helpers.metrics      import filter_strikes, aggregate_oi

def build_option_levels(
        ticker: str,
        expiry_param: str,
        center: float,
        width: int,
        include_greeks: bool
) -> Dict:
    exp = select_expiry(ticker, expiry_param)
    cp  = center or get_latest_close(ticker)
    df  = fetch_chain(ticker, exp)
    dfw = filter_strikes(df, cp, width)

    if dfw.empty:
        return {}
    allow_negative = expiry_param in ("front", "today")
    strikes = aggregate_oi(dfw, include_greeks, allow_negative)
    strikes = sorted(
        strikes,
        key=lambda x: x["strike"]
    )
    return {
        "ticker": ticker,
        "expiry": exp,
        "center_price": cp,
        "width": width,
        "strikes": strikes
    }
