# helpers/select_expiry_ib.py

from ib_insync import Stock, Contract
from .ib_connection import get_ib

def select_expiry_ib(ticker: str, which: str = "front") -> str:
    """
    Pick an option expiry for `ticker`.
      - which="front" or "today" -> first non-zero-OI expiry
      - which="next" or "tomorrow"-> second non-zero-OI expiry
      - otherwise must be an exact "YYYY-MM-DD"
    """
    ib = get_ib()

    # 1) Qualify underlying for reqSecDefOptParams
    if ticker.upper() == "SPX":
        underlying = Contract(symbol="SPX", secType="IND", exchange="CBOE", currency="USD")
    else:
        underlying = Stock(ticker, "SMART", "USD")
    underlying = ib.qualifyContracts(underlying)[0]

    # 2) Fetch all expiries
    params = ib.reqSecDefOptParams(underlying.symbol, "", underlying.secType, underlying.conId)
    # usually only one chain object matches symbol/secType
    expirations = sorted(params[0].expirations)

    # 3) If user passed an exact date, validate it
    if which not in ("front", "today", "next", "tomorrow"):
        if which in expirations:
            return which
        raise ValueError(f"Expiry '{which}' not in available expirations: {expirations}")

    # 4) Build candidate list: indices into `expirations`
    if which in ("front", "today"):
        idxs = [0, 1, 2]
    else:  # next/tomorrow
        idxs = [1, 2, 0]

    # 5) Pick first expiry whose total OI > 0
    for i in idxs:
        exp = expirations[i]
        chain = ib.reqSecDefOptParams(underlying.symbol, "", underlying.secType, underlying.conId)
        # get that specific expiration’s chain
        data = next(c for c in chain if c.expirations and c.expirations[0] == exp)
        total_oi = 0
        # sum OI across both calls and puts for that expiry
        for strike in data.strikes:
            # snapshot call & put each
            for right in ("C", "P"):
                opt = ib.qualifyContracts(
                    Option(underlying.symbol, exp, strike, right, "SMART")
                )[0]
                ticker_data = ib.reqMktData(opt, "", snapshot=True)
                ib.sleep(0.1)
                total_oi += (ticker_data.openInterest or 0)
                ib.cancelMktData(opt)
        if total_oi > 0:
            return exp

    # fallback
    return expirations[0]
