import asyncio
import numpy as np
from ib_insync import IB, Stock, Option
from typing import List, Dict

###############################################################################
# 1.  Constants
###############################################################################

GENERIC_TICKS = "100,101,104,105,106"
strike_range = [588, 589, 590, 591, 592, 593]
TIMEOUT_S     = 10
BATCH_SIZE = 3  # Process xx strikes at a time

###############################################################################
# 2.  Connection helpers
###############################################################################

async def connect_ib(market_data_type = 1, host: str = "127.0.0.1", port: int = 4001, client_id: int = 17) -> IB:
    """Return a connected & warmed‑up IB instance."""
    ib = IB()
    await ib.connectAsync(host, port, clientId=client_id)
    
    return ib

###############################################################################
# 3.  Helper functions
###############################################################################

async def ensure_critical_fields(ticker, timeout=15, max_attempts=4):
    """Wait specifically for modelGreeks and open interest data"""
    for attempt in range(max_attempts):
        try:
            # Wait for any update
            await asyncio.wait_for(ticker.updateEvent, timeout)

            # Check specifically for our required fields
            if (ticker.modelGreeks is not None and
                    ticker.modelGreeks.impliedVol is not None and
                    (ticker.callOpenInterest is not None or ticker.putOpenInterest is not None)):
                return True

            # Short delay between checks
            await asyncio.sleep(0.5)

        except asyncio.TimeoutError:
            print(f"Attempt {attempt+1} timed out for {ticker.contract.localSymbol}")

    print(f"Warning: Missing critical data for {ticker.contract.localSymbol}")
    return False
async def fetch_option_data(ib: IB, contract) -> Dict:
    """Fetch data for a single option contract"""
    ticker = ib.reqMktData(contract, genericTickList=GENERIC_TICKS, snapshot=False)
    await ensure_critical_fields(ticker)  # Reuse our previous validation function
    return {
        'contract': contract,
        'delta': ticker.modelGreeks.delta,
        'iv': ticker.modelGreeks.impliedVol,
        'oi': ticker.callOpenInterest if contract.right == 'C' else ticker.putOpenInterest,
        'bid': ticker.bid,
        'ask': ticker.ask
    }

async def get_reliable_ticker(ib, contract, timeout=10, max_attempts=3):
    """Enhanced version that ensures no NaN values"""
    ticker = ib.reqMktData(contract, genericTickList=GENERIC_TICKS, snapshot=False)

    for attempt in range(max_attempts):
        try:
            await asyncio.wait_for(ticker.updateEvent, timeout)

            # Check for NaN values in critical fields
            if (ticker.modelGreeks and
                    not np.isnan(ticker.modelGreeks.gamma) and
                    not np.isnan(ticker.modelGreeks.impliedVol) and
                    not np.isnan(ticker.modelGreeks.delta) and
                    (not np.isnan(ticker.callOpenInterest) if contract.right == 'C' else
                    not np.isnan(ticker.putOpenInterest))):
                return ticker

            await asyncio.sleep(0.5)
        except (asyncio.TimeoutError, AttributeError):
            continue

    print(f"Warning: Incomplete data for {contract.localSymbol}")
    return ticker

########################################
########################################

async def process_strike(ib, strike, spot_price):
    """Process one strike price with both call and put"""
    call_contract = Option("SPY", "20250516", strike, 'C', "SMART")
    put_contract = Option("SPY", "20250516", strike, 'P', "SMART")

    call_ticker, put_ticker = await asyncio.gather(
        get_reliable_ticker(ib, call_contract),
        get_reliable_ticker(ib, put_contract)
    )

    call_data = {
        'delta': call_ticker.modelGreeks.delta,
        'gamma': call_ticker.modelGreeks.gamma,
        'iv': call_ticker.modelGreeks.impliedVol,
        'oi': call_ticker.callOpenInterest
    } if call_ticker else None

    put_data = {
        'delta': put_ticker.modelGreeks.delta,
        'gamma': put_ticker.modelGreeks.gamma,
        'iv': put_ticker.modelGreeks.impliedVol,
        'oi': put_ticker.putOpenInterest
    } if put_ticker else None

    call_gex, put_gex, net_gex = calculate_gex(
        strike,
        call_data['oi'] if call_data else None,
        call_data['gamma'] if call_data else None,
        put_data['oi'] if put_data else None,
        put_data['gamma'] if put_data else None,
        spot_price
    )

    return {
        'strike': strike,
        'call': call_data,
        'put': put_data,
        'call_gex': call_gex,
        'put_gex': put_gex,
        'net_gex': net_gex
    }

def calculate_gex(strike, call_oi, call_gamma, put_oi, put_gamma, spot_price):
    """Calculate Gamma Exposure for a strike level"""
    if None in [call_oi, call_gamma, put_oi, put_gamma]:
        return None

    # GEX calculation (simplified)
    call_gex = call_oi * call_gamma * 100 * spot_price
    put_gex = -1 * put_oi * put_gamma * 100 * spot_price  # Put gamma is positive in IB
    
    net_gex = call_gex + put_gex
    return call_gex, put_gex, net_gex


async def warmup (ib):
    ib.reqMarketDataType(1)  # 1 = live
    ib.reqMktData(Stock('SPY','SMART','USD'), '', snapshot=True)
    
###############################################################################
# 4.  Main
###############################################################################
async def main():
    ib = await connect_ib()
    
    try:
        await warmup(ib)
        await asyncio.sleep(2)

        spy_ticker = ib.reqMktData(Stock('SPY', 'SMART', 'USD'), '233', snapshot=False)

        await asyncio.sleep(2)
        # await spy_ticker.updateEvent
        spot_price = spy_ticker.last
        print(f"SPY spot price: {spot_price}")

        ###########################
        # Batched solution
        ###########################
        results = []
        

        for i in range(0, len(strike_range), BATCH_SIZE):
            batch = strike_range[i:i+BATCH_SIZE]
            batch_results = await asyncio.gather(
                *[process_strike(ib, strike, spot_price) for strike in batch],
                return_exceptions=True
            )
            results.extend([r for r in batch_results if not isinstance(r, Exception)])
            await asyncio.sleep(1)  # Brief pause between batches

        ###########################
        # Printing results
        ###########################
        print(f"\nSPY Spot Price: {spot_price:.2f}")
        print("\nStrike | Type | Δ     | Γ      | IV (%) | OI    | GEX Contribution")
        print("------------------------------------------------------")
        for result in results:
            for option_type in ['call', 'put']:
                data = result[option_type]
                if data:
                    gex_value = result[f'{option_type}_gex']/1e6 if result[f'{option_type}_gex'] else 'N/A'
                    print(f"{result['strike']:6} | {option_type[0].upper():4} | "
                          f"{data['delta']:.2f} | {data['gamma']:.4f} | "
                          f"{data['iv']:.1%}  | {data['oi']:5} | "
                          f"{gex_value:.1f}M" if isinstance(gex_value, float) else gex_value)
        
            # Print net GEX for strike
            if result['net_gex'] is not None:
                print(f"  → NET GEX for {result['strike']}: {result['net_gex']/1e6:.1f}M")
          
    finally:
        ib.disconnect()
    
asyncio.run(main())