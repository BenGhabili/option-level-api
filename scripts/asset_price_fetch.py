"""
index_ratios.py  ·  save daily index / futures ratios to CSV
------------------------------------------------------------
"""
import pandas as pd
import asyncio
import argparse
from pathlib import Path
from datetime import datetime, timezone
from ib_insync import Stock, IB, Future, Contract


TARGET_FOLDER = r"D:\TradingData"

# ───────────────────────────────────────────────────────────

###############################################################################
# 2.  Connection helpers
###############################################################################

async def connect_ib(host: str = "127.0.0.1", port: int = 4001, client_id: int = 17) -> IB:
    """Return a connected & warmed‑up IB instance."""
    ib = IB()
    await ib.connectAsync(host, port, clientId=client_id)

    return ib

async def warmup (ib, data_type):
    ib.reqMarketDataType(data_type)  # 1 = live
    ib.reqMktData(Stock('SPY','SMART','USD'), '', snapshot=True)

###############################################################################
# 3.  Helper functions
###############################################################################

async def main(data_type = 1):
    ib = await connect_ib()

    try:
        await warmup(ib, data_type)
        print(
            "Warming up market data. Please wait..."
        )
        await asyncio.sleep(2)
        
        print(f"\nCollecting option data for SPY, ES, SPX, NQ, QQQ")

        spy_ticker = ib.reqMktData(Stock('SPY', 'SMART', 'USD'), '233', snapshot=False)
        qqq_ticker = ib.reqMktData(Stock('QQQ', 'SMART', 'USD'), '233', snapshot=False)
        spx_ticker = Contract(symbol='SPX', secType='IND', exchange='CBOE', currency='USD')
        es = Future(symbol='ES', lastTradeDateOrContractMonth='202512', exchange='CME', currency='USD')
        nq = Future(symbol='NQ', lastTradeDateOrContractMonth='202512', exchange='CME', currency='USD')

        ticker_es = ib.reqMktData(es, '', False, False)
        ticker_nq = ib.reqMktData(nq, '', False, False)
        
        ticker_spx = ib.reqMktData(spx_ticker, '', False, False)

        await asyncio.sleep(3)

        spy_price = spy_ticker.last
        qqq_price = qqq_ticker.last
        es_price = ticker_es.last
        nq_price = ticker_nq.last
        spx_price = ticker_spx.last

        if not spy_price:
            print("No SPY price found")
            return
        
        if not qqq_price:
            print("No QQQ price found")
            return
        
        if not es_price:
            print("No ES price found")
            return 
        
        if not nq_price:
            print("No NQ price found")
            return 
        if not spx_price:
            print("No SPX price found")
            return 
            
            
        print(f"SPY price: {spy_price}")
        print(f"QQQ price: {qqq_price}")
        print(f"ES price: {es_price}")
        print(f"NQ price: {nq_price}")
        print(f"SPX price: {spx_price}")
        
        # ❷  CALCULATE RATIOS
        spy_es  = es_price  / spy_price
        spx_es  = es_price  / spx_price
        qqq_nq  = nq_price  / qqq_price
        
        row = {
            "date"   : datetime.now(timezone.utc).strftime("%Y%m%d"),  # or a fixed expiry string
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "spy_es" : round(spy_es, 6),
            "spx_es" : round(spx_es, 6),
            "qqq_nq" : round(qqq_nq, 6),
            "es"     : es_price,
            "spy"    : spy_price,
            "spx"    : spx_price,
            "nq"     : nq_price,
            "qqq"    : qqq_price,
        }
        
        # ❸  APPEND / CREATE CSV
        now = datetime.now()
        yyyymm     = now.strftime('%Y%m')         # e.g. 202507
        base_dir = Path(TARGET_FOLDER) / "ratio-collections"
        base_dir.mkdir(parents=True, exist_ok=True)

        csv_path = base_dir / f"{yyyymm}_ratios.csv"
        # csv_path = Path("./data/ratio-collections.csv")
        
        if csv_path.exists():
            # load to keep column order consistent
            df = pd.read_csv(csv_path)
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        else:
            df = pd.DataFrame([row])
        
        df.to_csv(csv_path, index=False)
        print(f"✅  Added row for {row['date']} → {csv_path}")
        
        # define the daily‐only columns
        daily_cols = ['date','spy_es','spx_es','qqq_nq','es','spy', 'spx','nq','qqq']
        
        # build a one‐row DataFrame without timestamp
        daily_df = pd.DataFrame([{k: row[k] for k in daily_cols}])
        
        daily_path = Path(r"D:\TradingData\ratios.csv")
        daily_df.to_csv(daily_path, index=False)
        
        print(f"✅  Updated the csv file: {daily_path}")
        
    finally:
        ib.disconnect()    

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Minimal IB option‑chain snapshot")
    parser.add_argument("--data", type=int, default=1, help="type of market data to request")
    args = parser.parse_args()
    asyncio.run(main(args.data))        
        
