#!/usr/bin/env python3
"""
option_chain_poc.py  –  **minimal, one‑file proof‑of‑concept** for pulling an
option chain from Interactive Brokers and printing a tiny table.

Now tries multiple exchanges (SMART, blank, CBOE) to qualify contracts if
SMART routing is unavailable.

Usage examples
--------------
$ python scripts/option_chain_poc.py                     # SPY, nearest expiry, ±5 strikes
$ python scripts/option_chain_poc.py --ticker QQQ        # choose underlying
$ python scripts/option_chain_poc.py --expiry 20250516   # explicit expiry
$ python scripts/option_chain_poc.py --width 10          # widen the strike band
"""

import argparse
import logging
import math
from typing import List

from ib_insync import IB, Stock, Contract, Option, Ticker

# List of exchanges to try in order
EXCHANGES = ["SMART", "", "CBOE", "ARCA", ]

###############################################################################
# 1.  Connection helpers
###############################################################################

def connect_ib(host: str = "127.0.0.1", port: int = 4001, client_id: int = 17) -> IB:
    """Return a connected & warmed‑up IB instance."""
    ib = IB()
    ib.connect(host, port, clientId=client_id)
    ib.reqMarketDataType(1)  # 1 = live
    return ib


def qualify_underlying(ib: IB, ticker: str) -> Contract:
    """Return a fully qualified underlying contract (Stock or SPX index)."""
    ticker = ticker.upper()
    if ticker == "SPX":
        base = Contract(symbol="SPX", secType="IND", exchange="CBOE", currency="USD")
    else:
        base = Stock(ticker, "SMART", "USD")

    q = ib.qualifyContracts(base)
    if not q:
        print("not qualified - BEN!")
        raise RuntimeError(f"Could not qualify underlying {ticker}")
    return q[0]


def latest_price(ib: IB, underlying: Contract) -> float:
    """Return a snapshot last price (falls back to previous close)."""
    snap = ib.reqMktData(underlying, "", snapshot=True)
    ib.sleep(1)
    if snap.last is not None and not math.isnan(snap.last):
        return snap.last

    bars = ib.reqHistoricalData(
        underlying,
        endDateTime="",
        durationStr="2 D",
        barSizeSetting="1 day",
        whatToShow="TRADES",
        useRTH=True,
        formatDate=1,
        keepUpToDate=False,
    )
    if bars:
        return bars[-1].close
    raise RuntimeError("Unable to get underlying price (live or prev close)")

###############################################################################
# 2.  Expiry & strike helpers
###############################################################################

def first_expiry(ib: IB, underlying: Contract) -> str:
    """Return the first expiration date IB lists (YYYYMMDD)."""
    params = ib.reqSecDefOptParams(
        underlying.symbol, "", underlying.secType, underlying.conId
    )
    if not params or not params[0].expirations:
        raise RuntimeError("No expirations returned by IB")
    return sorted(params[0].expirations)[0]


def strikes_near_price(
        ib: IB, underlying: Contract, expiry: str, center: float, width: int
) -> List[float]:
    """Return all strikes within ± `width` of `center`."""
    # ------------------------- - --------------------- ---------------
    print(f"strikes near {center:.2f} in {width} units")
    
    params = ib.reqSecDefOptParams(
        underlying.symbol, "", underlying.secType, underlying.conId
    )
    # ------------------------- - --------------------- ---------------
    print(f"IB returned {len(params)} expirations")

    matching = None
    for p in params or []:
        # p.expirations lists available expiries
        if hasattr(p, "expirations") and expiry in p.expirations:
            matching = p
            break
        # Some param objects use contractMonth
        if hasattr(p, "contractMonth") and p.contractMonth == expiry:
            matching = p
            break

    if not matching:
        print(f"[DEBUG] no matching Option parameters for expiry {expiry}")
        return []
    
    strikes = params[0].strikes if params else []
    return [s for s in strikes if abs(s - center) <= width]

###############################################################################
# 3.  Option chain fetch (with multiple exchanges)
###############################################################################

def fetch_chain(
        ib: IB, underlying: Contract, expiry: str, strikes: List[float]
) -> List[Ticker]:
    """Qualify Call & Put at each strike and request a snapshot ticker."""
    qualified = []
    tickers = []

    for ex in EXCHANGES:
        # Build contracts for this exchange
        contracts = [
            Option(underlying.symbol, expiry, strike, right, ex)
            for strike in strikes
            for right in ("C", "P")
        ]
        print(f"Trying exchange '{ex}' → {len(contracts)} contracts")
        
        q = ib.qualifyContracts(*contracts)
        print(f"  → qualified {len(q)}/{len(contracts)} contracts")
        logging.debug(f"Tried exchange '{ex or '<blank>'}' → qualified {len(q)}/{len(contracts)} contracts")
        if not q:
            continue
        qualified = q
        break

    if not qualified:
        raise RuntimeError(f"Could not qualify any option contracts on any exchange for expiry {expiry}")

    # Fetch snapshot data
    tickers = ib.reqTickers(*qualified)
    return tickers

###############################################################################
# 4.  Pretty printer
###############################################################################

def print_table(tickers: List[Ticker]):
    print("\nstrike  right   last     bid      ask    vol   OI    IV")
    print("―――――――  ――――  ―――――  ――――――  ――――――  ――――  ―――  ――――")

    for tk in sorted(tickers, key=lambda t: (t.contract.strike, t.contract.right)):
        strike = tk.contract.strike
        right  = tk.contract.right
        last   = tk.last or 0.0
        bid    = tk.bid or 0.0
        ask    = tk.ask or 0.0
        vol    = 0 if tk.volume is None or math.isnan(tk.volume) else int(tk.volume)
        oi     = 0 if tk.openInterest is None or math.isnan(tk.openInterest) else int(tk.openInterest)
        iv     = 0 if tk.impliedVol is None else tk.impliedVol

        print(f"{strike:6.0f}   {right}  {last:7.2f}  {bid:7.2f}  {ask:7.2f}  "
              f"{vol:4d}  {oi:4d}  {iv:5.2f}")

###############################################################################
# 5.  Main driver
###############################################################################

def main(ticker: str, expiry_arg: str | None, width: int):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)5s [option_poc] %(message)s",
        datefmt="%H:%M:%S",
    )

    ib = connect_ib()
    try:
        underlying = qualify_underlying(ib, ticker)
        expiry = expiry_arg or first_expiry(ib, underlying)
        px = latest_price(ib, underlying)

        logging.info(f"Using expiry {expiry}  |  underlying last = {px:.2f}")

        strikes = strikes_near_price(ib, underlying, expiry, px, width)
        if not strikes:
            raise RuntimeError("No strikes within requested width – try a larger width")

        tickers = fetch_chain(ib, underlying, expiry, strikes)
        print_table(tickers)

    finally:
        ib.disconnect()

###############################################################################
# 6.  CLI entry‑point
###############################################################################

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Minimal IB option‑chain snapshot")
    parser.add_argument("--ticker", default="SPY", help="Underlying symbol (default SPY)")
    parser.add_argument("--expiry", help="YYYYMMDD; omit for first available")
    parser.add_argument("--width", type=int, default=5, help="Half‑width in strike units (default 5)")
    args = parser.parse_args()

    main(args.ticker.upper(), args.expiry, args.width)
