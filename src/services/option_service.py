from typing import Dict
from helpers.select_expiry_ib import select_expiry_ib
from helpers.last_trade_or_prev_close import last_trade_or_prev_close
from helpers.ib_option_fetcher import fetch_chain_ib
from helpers.ib_connection import get_ib

def build_option_levels(
        ticker: str,
        expiry_param: str,
        center: float,
        width: int
) -> Dict:
    exp = select_expiry_ib(ticker, expiry_param)
    ib  = get_ib()
    cp, _ = last_trade_or_prev_close(ib, ticker)
    center_price = center or cp
    raw = fetch_chain_ib(ticker, exp)
    strikes = [s for s in raw if abs(s["strike"] - center_price) <= width]
    strikes.sort(key=lambda x: x["strike"])
    return {
        "ticker": ticker,
        "expiry": exp,
        "center_price": center_price,
        "width": width,
        "strikes": strikes,
    }
    # exp = select_expiry(ticker, expiry_param)
    # cp  = center or get_latest_close(ticker)
    # df  = fetch_chain(ticker, exp)
    # dfw = filter_strikes(df, cp, width)
    # 
    # if dfw.empty:
    #     return {}
    # allow_negative = expiry_param in ("front", "today")
    # strikes = aggregate_oi(dfw, include_greeks, allow_negative)
    # strikes = sorted(
    #     strikes,
    #     key=lambda x: x["strike"]
    # )
    # return {
    #     "ticker": ticker,
    #     "expiry": exp,
    #     "center_price": cp,
    #     "width": width,
    #     "strikes": strikes
    # }
