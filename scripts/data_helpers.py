from ib_insync import IB, Option, Stock
import asyncio
import numpy as np
from typing import Dict
from calculation_helpers import calculate_gex

GENERIC_TICKS = "100,101,104,105,106"


def generate_strike_range(center_value, range_up, range_down):
    return list(range(center_value - range_down, center_value + range_up + 1))


async def get_reliable_ticker(ib, contract, check_greeks=False, timeout=10, max_attempts=3):
    """Enhanced version that ensures no NaN values"""
    ticker = ib.reqMktData(contract, genericTickList=GENERIC_TICKS, snapshot=False)

    for attempt in range(max_attempts):
        try:
            await asyncio.wait_for(ticker.updateEvent, timeout)

            if check_greeks:
                if (ticker.modelGreeks and
                        not np.isnan(ticker.modelGreeks.gamma) and
                        not np.isnan(ticker.modelGreeks.impliedVol) and
                        (not np.isnan(ticker.callOpenInterest) if contract.right == 'C' else
                        not np.isnan(ticker.putOpenInterest))):
                    return ticker
            else:
                if not np.isnan(ticker.callOpenInterest) if contract.right == 'C' else not np.isnan(
                        ticker.putOpenInterest):
                    return ticker

            await asyncio.sleep(0.5)
        except (asyncio.TimeoutError, AttributeError):
            continue

    print(f"Warning: Incomplete data for {contract.localSymbol}")
    return ticker


async def process_strike_with_gex(ib, strike, expiry, ticker, gex_calculated=False):
    """Process one strike price with both call and put"""
    call_contract = Option(ticker, expiry, strike, 'C', "SMART")
    put_contract = Option(ticker, expiry, strike, 'P', "SMART")

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
            call_data['gamma'] = call_ticker.modelGreeks.gamma
            call_data['iv'] = call_ticker.modelGreeks.impliedVol
    if put_ticker:
        put_data = {
            'oi': put_ticker.putOpenInterest
        }

        if gex_calculated:
            put_data['gamma'] = put_ticker.modelGreeks.gamma
            put_data['iv'] = put_ticker.modelGreeks.impliedVol

    call_gex = None
    put_gex = None
    net_gex = None

    if gex_calculated:
        call_gex, put_gex, net_gex = calculate_gex(
            strike,
            call_data['oi'] if call_data else None,
            call_data['gamma'] if call_data else None,
            put_data['oi'] if put_data else None,
            put_data['gamma'] if put_data else None
        )

    return_object = {
        'strike': strike,
        'call': call_data,
        'put': put_data
    }

    if gex_calculated:
        return_object['call']['call_gex'] = call_gex
        return_object['put']['put_gex'] = put_gex
        return_object['net_gex'] = net_gex
    
    return return_object


# This function is not being used
async def ensure_critical_fields(ticker, timeout=15, max_attempts=4):
    """Wait specifically for modelGreeks and open interest data"""
    for attempt in range(max_attempts):
        try:
            # Wait for any update
            await asyncio.wait_for(ticker.updateEvent, timeout)

            if ticker.callOpenInterest is not None or ticker.putOpenInterest is not None:
                return True

            # Short delay between checks
            await asyncio.sleep(0.5)

        except asyncio.TimeoutError:
            print(f"Attempt {attempt + 1} timed out for {ticker.contract.localSymbol}")

    print(f"Warning: Missing critical data for {ticker.contract.localSymbol}")
    return False


async def fetch_option_data(ib: IB, contract) -> Dict:
    """Fetch data for a single option contract"""
    ticker = ib.reqMktData(contract, genericTickList=GENERIC_TICKS, snapshot=False)
    await ensure_critical_fields(ticker)  # Reuse our previous validation function
    return {
        'contract': contract,
        'iv': ticker.modelGreeks.impliedVol,
        'oi': ticker.callOpenInterest if contract.right == 'C' else ticker.putOpenInterest,
        'bid': ticker.bid,
        'ask': ticker.ask
    }


async def batch_data(ib: IB, batch_size, expiry, ticker, centre_price, up_level, down_level, gex_calculated=False):
    strike_range = generate_strike_range(centre_price, up_level, down_level)

    results = []

    for i in range(0, len(strike_range), batch_size):
        batch = strike_range[i:i + batch_size]
        batch_results = await asyncio.gather(
            *[process_strike_with_gex(ib, strike, expiry, ticker, gex_calculated) for strike in batch],
            return_exceptions=True
        )
        results.extend([r for r in batch_results if not isinstance(r, Exception)])
        await asyncio.sleep(1)  # Brief pause between batches

    return results


async def fetch_stock_ticker(ib, ticker):
    """Fetch the current stock price."""
    contract = Stock(ticker, 'SMART', 'USD')
    ticker_data = ib.reqMktData(contract, '233', snapshot=False)

    await asyncio.sleep(3)

    return ticker_data
