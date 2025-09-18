#!/usr/bin/env python3
import argparse, asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from ib_insync import IB, Stock
from ib_connection import warmup, connect_ib
from data_helpers import batch_data, fetch_stock_ticker

from calculation_helpers import expected_move
from data_helpers        import fetch_atm_iv, fetch_option_data

async def main(ticker, expiry, data_type, quiet):
    try:
        ib = await connect_ib()
    except Exception as e:
        print(f"❌ Failed to connect to IB: {e}")
        # exit the coroutine (and thus the program)
        return

    try:
        await warmup(ib, data_type)
        if not quiet:
            print(
                "Warming up market data. Please wait..."
            )
        await asyncio.sleep(2)
        if not quiet:
            print(f"\nCollecting Option data for: {ticker} Expiry: {expiry}")

            
        # spot
        requested_ticker = await fetch_stock_ticker(ib, ticker)
    
        spot = requested_ticker.last

        if not quiet:
            print(f"{ticker} spot price: {spot}")

    

        # atm iv
        iv = await fetch_atm_iv(ib, ticker, ticker, spot)

         # test = await fetch_option_data(ib, ticker)
        # 
        # em = expected_move(centre_price, iv)
        # pct = em / centre_price
        # 
        # if quiet:
        #     print(f"{em:.2f}")
        # else:
        #     print(f"{ticker} spot: {spot:.2f}")
        #     print(f"ATM IV     : {iv:.2%}")
        #     print(f"Expected ±1σ move today: ${em:.2f}  ({pct:.2%})")         

    
    except Exception as e:
        print(f"❌ Something wrong happened: {e}")
        # exit the coroutine (and thus the program)
        return
    finally:
        ib.disconnect()

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--ticker", default="SPY")
    p.add_argument("--expiry", default=datetime.now(ZoneInfo("UTC")).strftime("%Y%m%d"))
    p.add_argument("--data",   type=int, default=1)
    p.add_argument("--quiet",  action="store_true")
    a = p.parse_args()
    asyncio.run(main(a.ticker.upper(), a.expiry, a.data, a.quiet))
