#!/usr/bin/env python3
# scripts/simple_option_poc.py

from ib_insync import IB, Option
import math

def main():
    ib = IB()
    print("☞ Connecting to IB Gateway…")
    ib.connect('127.0.0.1', 4001, clientId=100)
    ib.reqMarketDataType(2)  # live first
    print("✔ Connected")

    # ← Tweak these as you like:
    SYMBOL   = "SPY"
    EXPIRY   = "20250512"    # YYYYMMDD
    STRIKE   = 565.0
    RIGHT    = "C"           # 'C' or 'P'
    EXCHANGE = "SMART"       # try "CBOE" or "" if SMART fails

    opt = Option(SYMBOL, EXPIRY, STRIKE, RIGHT, EXCHANGE)
    print(f"☞ Qualifying {SYMBOL} {EXPIRY} {STRIKE}{RIGHT} @ {EXCHANGE or '<blank>'}…")
    # q = ib.qualifyContracts(opt)
    # 
    # if not q:
    #     print("⚠ No contracts on SMART – retrying with blank exchange…")
    #     opt.exchange = ""
    #     q = ib.qualifyContracts(opt)
    # 
    # if not q:
    #     print("❌ Still no contract. Exiting.")
    #     ib.disconnect()
    #     return

    cds = ib.reqContractDetails(opt)

    if not cds:
        print("❌ No matching Option contractDefinitions returned. Exiting.")
        ib.disconnect()
        return

    # Try to pick the SMART one first
    sm = [d.contract for d in cds if d.contract.exchange == "SMART"]
    if sm:
        contract = sm[0]
        print("✔ Picked SMART contract")
    else:
        contract = cds[0].contract
        print(f"⚠ SMART not found; using {contract.exchange} contract")

    print(f"→ Using contract: {contract}\n")
    # contract = q[0]

    print("☞ Requesting market data snapshot…")
    md = ib.reqMktData(contract, "", snapshot=True)
    ib.sleep(1)  # give IB a moment

    print("\n── Market Data ─────────────────────────────────────────")
    print(f" Last        : {md.last}")
    print(f" Bid / Ask   : {md.bid} / {md.ask}")
    print(f" Volume      : {md.volume}")
    print(f" OpenInterest: {getattr(md, 'openInterest', None)}")
    print(f" ImpliedVol  : {getattr(md, 'impliedVol', None)}")

    print("\n☞ Disconnecting…")
    ib.disconnect()

if __name__ == "__main__":
    main()
