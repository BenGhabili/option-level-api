import asyncio
import argparse
from datetime import datetime
from zoneinfo import ZoneInfo

from ib_insync import Contract, Option

from ib_connection import connect_ib, warmup
from data_helpers import batch_data, fetch_stock_ticker, get_reliable_ticker
from calculation_helpers import calculate_gex
from csv_helpers import workable_oi_levels, append_oi_data, gex_data_save


###############################################################################
# 1.  Constants
###############################################################################

BATCH_SIZE = 5  # Process xx strikes at a time


###############################################################################
# 2.  Helpers
###############################################################################

def is_yes(flag: str) -> bool:
    return flag.strip().upper().startswith("Y")


def round_to_nearest(value: float, step: int) -> int:
    return int(round(value / step) * step)


async def fetch_spx_ticker(ib):
    """Fetch SPX index spot via CBOE index contract."""
    contract = Contract(symbol='SPX', secType='IND', exchange='CBOE', currency='USD')
    tk = ib.reqMktData(contract, '233', snapshot=False)
    await asyncio.sleep(3)
    return tk


async def process_strike_with_gex_spx(ib, strike, expiry, gex_calculated=False):
    """SPX option strike fetch using CBOE exchange and optional GEX calc."""
    call_contract = Option('SPX', expiry, strike, 'C', 'CBOE')
    put_contract = Option('SPX', expiry, strike, 'P', 'CBOE')

    call_ticker, put_ticker = await asyncio.gather(
        get_reliable_ticker(ib, call_contract, check_greeks=gex_calculated),
        get_reliable_ticker(ib, put_contract, check_greeks=gex_calculated)
    )

    call_data = None
    put_data = None

    if call_ticker:
        call_data = {
            'oi': call_ticker.callOpenInterest
        }
        if gex_calculated:
            call_data['gamma'] = getattr(call_ticker.modelGreeks, 'gamma', None) if call_ticker.modelGreeks else None
            call_data['iv'] = getattr(call_ticker.modelGreeks, 'impliedVol', None) if call_ticker.modelGreeks else None
    if put_ticker:
        put_data = {
            'oi': put_ticker.putOpenInterest
        }
        if gex_calculated:
            put_data['gamma'] = getattr(put_ticker.modelGreeks, 'gamma', None) if put_ticker.modelGreeks else None
            put_data['iv'] = getattr(put_ticker.modelGreeks, 'impliedVol', None) if put_ticker.modelGreeks else None

    # Defer GEX calculation to CSV helpers stage (same as option_async behavior)
    return_object = {
        'strike': strike,
        'call': call_data,
        'put': put_data
    }

    if gex_calculated and call_data and put_data:
        call_gex, put_gex, net_gex = calculate_gex(
            strike,
            call_data.get('oi') if call_data else None,
            call_data.get('gamma') if call_data else None,
            put_data.get('oi') if put_data else None,
            put_data.get('gamma') if put_data else None
        )
        return_object['call'] = return_object.get('call', {})
        return_object['put'] = return_object.get('put', {})
        return_object['call']['call_gex'] = call_gex
        return_object['put']['put_gex'] = put_gex
        return_object['net_gex'] = net_gex

    return return_object


async def batch_data_spx(ib, batch_size, expiry, centre_price, up_level, down_level, gex_calculated=False, step=10):
    strikes = list(range(centre_price - down_level * step, centre_price + up_level * step + step, step))
    results = []
    for i in range(0, len(strikes), batch_size):
        batch = strikes[i:i + batch_size]
        batch_results = await asyncio.gather(
            *[process_strike_with_gex_spx(ib, strike, expiry, gex_calculated) for strike in batch],
            return_exceptions=True
        )
        results.extend([r for r in batch_results if not isinstance(r, Exception)])
        await asyncio.sleep(1)
    return results


###############################################################################
# 3.  Main
###############################################################################

async def run_for_symbol(ib, ticker, expiry, up_level, down_level, csv_update, check_gex, quiet, spx_step):
    calculate_gex = is_yes(check_gex)

    if ticker == 'SPX':
        requested_ticker = await fetch_spx_ticker(ib)
        spot_price = requested_ticker.last
        if not quiet:
            print(f"{ticker} spot price: {spot_price}")
        centre_price = round_to_nearest(spot_price, spx_step)
        results = await batch_data_spx(ib, BATCH_SIZE, expiry, centre_price, up_level, down_level, calculate_gex, step=spx_step)
    else:
        requested_ticker = await fetch_stock_ticker(ib, ticker)
        spot_price = requested_ticker.last
        if not quiet:
            print(f"{ticker} spot price: {spot_price}")
        centre_price = round(spot_price)
        results = await batch_data(ib, BATCH_SIZE, expiry, ticker, centre_price, up_level, down_level, calculate_gex)

    if not quiet:
        print(f"\n{ticker} Spot Price: {spot_price:.2f}")
        # Print detailed per-strike rows
        if calculate_gex:
            print("\nStrike | Call_GEX | Put_GEX | Net_GEX")
            print("-----------------------------")
            for r in results:
                strike = r['strike']
                call_gex = (r['call'].get('call_gex') or 0) / 1e6 if r.get('call') else 0
                put_gex  = (r['put'].get('put_gex')  or 0) / 1e6 if r.get('put')  else 0
                net_gex  = (r.get('net_gex') or 0) / 1e6
                print(f"{strike:6} |   {call_gex:.1f}M   | {put_gex:.1f}M | {net_gex:.1f}M")
        else:
            print("\nStrike | Call_OI | Put_OI")
            print("-----------------------------")
            for r in results:
                strike  = r['strike']
                call_oi = r['call']['oi'] if r.get('call') else 0
                put_oi  = r['put']['oi']  if r.get('put')  else 0
                print(f"{strike:6} | {int(call_oi) if call_oi else 0:7} | {int(put_oi) if put_oi else 0:6}")

    if is_yes(csv_update) and not calculate_gex:
        rounded_spot = int(round(spot_price)) if spot_price is not None else None
        append_oi_data(results, ticker=ticker, expiry=expiry, spot=rounded_spot)
        workable_oi_levels(results, ticker=ticker, spot_price=spot_price, expiry=expiry)
    if is_yes(csv_update) and calculate_gex:
        rounded_spot = int(round(spot_price)) if spot_price is not None else None
        gex_data_save(results, ticker, spot=rounded_spot)

    return results, spot_price


async def main(expiry, data_type=1, up_level=7, down_level=7, csv_update='N', check_gex='N', quiet=False, spx_step=10):
    try:
        ib = await connect_ib()
    except Exception as e:
        print(f"❌ Failed to connect to IB: {e}")
        return

    try:
        await warmup(ib, data_type)
        if not quiet:
            print("Warming up market data. Please wait...")
        await asyncio.sleep(2)
        
        tickers = ['SPY', 'QQQ', 'SPX']
        
        for t in tickers:
            if not quiet:
                print(f"\nCollecting Option data for: {t} Expiry: {expiry}")
            await run_for_symbol(ib, t, expiry, up_level, down_level, csv_update, check_gex, quiet, spx_step)

    except Exception as e:
        print(f"❌ Something wrong happened: {e}")
        return
    finally:
        ib.disconnect()


if __name__ == "__main__":
    datetime.now(ZoneInfo("America/New_York"))
    parser = argparse.ArgumentParser(description="Multi‑ticker IB option‑chain snapshot (SPY, QQQ, SPX)")
    parser.add_argument("--expiry", default=datetime.today().strftime('%Y%m%d'), help="YYYYMMDD; omit for first available")
    parser.add_argument("--data", type=int, default=1, help="type of market data to request")
    parser.add_argument("--up_level", type=int, default=7, help="Half‑width in strike units (default 7)")
    parser.add_argument("--down_level", type=int, default=7, help="Half‑width in strike units (default 7)")
    parser.add_argument("--csv", default='N', help="Write CSV outputs (Y/N)")
    parser.add_argument("--gex", default='N', help="Calculate and append GEX CSV (Y/N)")
    parser.add_argument("--quiet", action="store_true", help="Suppress per‑strike console output")
    parser.add_argument("--spx_step", type=int, default=10, help="SPX strike step size (default 10)")
    args = parser.parse_args()

    asyncio.run(main(args.expiry, args.data, args.up_level, args.down_level, args.csv, args.gex, args.quiet, args.spx_step))


