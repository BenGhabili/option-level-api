# helpers/last_trade_or_prev_close.py

from ib_insync import Stock, Contract
import math

def last_trade_or_prev_close(ib, ticker: str):
    """
    Returns (price, source) where source is "live" or "prevClose".
    Uses live snapshot when available; otherwise pulls 1-day historical bar.
    """
    # 1) Qualify underlying
    if ticker.upper() == "SPX":
        contract = Contract(symbol="SPX", secType="IND", exchange="CBOE", currency="USD")
    else:
        contract = Stock(ticker, "SMART", "USD")
    contract = ib.qualifyContracts(contract)[0]

    # 2) Try live snapshot
    live = ib.reqMktData(contract, "", snapshot=True)
    ib.sleep(1)
    if live.last is not None and not math.isnan(live.last):
        return live.last, "live"

    # 3) Fallback: previous close via daily bar
    bars = ib.reqHistoricalData(
        contract,
        endDateTime="",
        durationStr="2 D",
        barSizeSetting="1 day",
        whatToShow="TRADES",
        useRTH=True,
        formatDate=1,
        keepUpToDate=False,
        chartOptions=[]
    )
    if bars:
        return bars[-1].close, "prevClose"

    # 4) If still unavailable
    return None, "unavailable"