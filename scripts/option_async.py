import asyncio
import pandas as pd
import argparse
from datetime import datetime
from zoneinfo import ZoneInfo
from csv_helpers import workable_oi_levels, append_oi_data
from ib_connection import warmup, connect_ib
from data_helpers import batch_data, fetch_stock_ticker

###############################################################################
# 1.  Constants
###############################################################################

BATCH_SIZE = 5  # Process xx strikes at a time
    
###############################################################################
# 4.  Main
###############################################################################
async def main(ticker, expiry, data_type = 1, up_level= 7, down_level = 7, csv_update = 'N', check_gex = 'N'):
    
    try:
     ib = await connect_ib()
    except Exception as e:
        print(f"❌ Failed to connect to IB: {e}")
        # exit the coroutine (and thus the program)
        return
    
    try:
        await warmup(ib, data_type)
        print(
            "Warming up market data. Please wait..."
        )
        await asyncio.sleep(2)

        print(f"\nCollecting Option data for: {ticker} Expiry: {expiry}")

        requested_ticker = await fetch_stock_ticker(ib, ticker)
        
        spot_price = requested_ticker.last
        print(f"{ticker} spot price: {spot_price}")
        
        centre_price = round(spot_price)

        ###########################
        # Batched solution
        ###########################
        
        calculate_gex = True if check_gex == 'Y' or check_gex == 'YES' else False
        
        results = await batch_data(ib, BATCH_SIZE, expiry, ticker, centre_price, up_level, down_level, calculate_gex)


        ###########################
        # Printing results
        ###########################
        print(f"\n{ticker} Spot Price: {spot_price:.2f}")
        
        if calculate_gex:
            print("\nStrike | Call_GEX | Put_GEX | Net_GEX")
            print("-----------------------------")
            for result in results:
                strike  = result['strike']
                call_gex = result['call']['call_gex']/1e6
                put_gex  = result['put']['put_gex']/1e6
                # adjust spacing as needed for alignment
                print(f"{strike:6} |   {call_gex:.1f}M   | {put_gex:.1f}M | {result['net_gex']/1e6:.1f}M")    
                
        else:
            print("\nStrike | Call_OI | Put_OI")
            print("-----------------------------")
            
            # Print each row with both values
            for result in results:
                strike  = result['strike']
                call_oi = result['call']['oi']
                put_oi  = result['put']['oi']
                # adjust spacing as needed for alignment
                print(f"{strike:6} | {call_oi:7} | {put_oi:6}")
            
        ###################################
        # Writing to CSV (raw figures on daily basis
        ####################################
        
        if csv_update == 'Y' or csv_update == 'YES':
            append_oi_data(results, ticker=ticker, expiry=expiry)
            workable_oi_levels(results,
                       ticker=ticker,
                       spot_price=spot_price,
                       expiry=expiry)
    except Exception as e:
        print(f"❌ Something wrong happened: {e}")
        # exit the coroutine (and thus the program)
        return      
    finally:
        ib.disconnect()

if __name__ == "__main__":
    datetime.now(ZoneInfo("America/New_York"))
    parser = argparse.ArgumentParser(description="Minimal IB option‑chain snapshot")
    parser.add_argument("--ticker", default="SPY", help="Underlying symbol (default SPY)")
    parser.add_argument("--csv", default="N", help="Underlying symbol (default No)")
    parser.add_argument("--gex", default="N", help="Underlying symbol (default No)")
    parser.add_argument("--up_level", type=int, default=7, help="Half‑width in strike units (default 7)")
    parser.add_argument("--down_level", type=int, default=7, help="Half‑width in strike units (default 7)")
    parser.add_argument("--expiry", default=datetime.today().strftime('%Y%m%d'),
                        help="YYYYMMDD; omit for first available")
    parser.add_argument("--data", type=int, default=1, help="type of market data to request")
    args = parser.parse_args()
    asyncio.run(main(args.ticker.upper(), args.expiry, args.data, args.up_level, args.down_level, args.csv, args.gex))