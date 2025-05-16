

import asyncio, math
from ib_insync import IB, Option

GENERIC_TICKS = "100,101,104,105,106"
TIMEOUT_S     = 5          # max time we wait for *one* update
N_CONCURRENT_STRIKES = 10  # tune to stay under IB pacing limits

assetObject = {
    "SPY": {
        "contract_list": [565, 570,575, 576, 577, 578, 579, 580, 581, 582, 583, 584, 585],
        "asset_name": "SPY",
        "asset_price_ticker": "SPY",
        "exchange": "SMART"
    },
    "SPY_TEST": {
        "contract_list": [580],
        "asset_name": "SPY",
        "asset_price_ticker": "SPY",
        "exchange": "SMART"
    },
    "QQQ": {
        "contract_list": [490, 495, 496, 497, 498, 499, 500, 501, 505, 506, 507, 508, 509],
        "asset_name": "QQQ",
        "asset_price_ticker": "QQQ",
        "exchange": "SMART"
    },
    "GOOGL": {
        "contract_list": [150, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162],
        "asset_name": "GOOGL",
        "asset_price_ticker": "SPY",
        "exchange": "SMART"
    },
    "SPX": {
        "contract_list": [5800, 5810, 5820, 5830, 5840, 5850, 5860, 5870, 5880, 5890, 5900, 5910, 5920],
        "asset_name": "SPX",
        "asset_price_ticker": "SPX",
        "exchange": "CBOE"
    }
}

async def analyse_strike(ib: IB, ticker: str, strike: float, *,   # ← one strike
                         asset_obj, expiry_arg, ticker_exch,
                         use_predefined_contracts, strike_range):

    multiply = 10 if ticker == "SPX" else 1

    opt_call = Option(asset_obj[ticker]["asset_name"],
                      expiry_arg, strike * multiply, 'C', ticker_exch)
    opt_put  = Option(asset_obj[ticker]["asset_name"],
                      expiry_arg, strike * multiply, 'P', ticker_exch)

    # pick SMART vs native exchange exactly like in your original code
    if ticker_exch in ("SMART", "CBOE"):
        contract_call, contract_put = opt_call, opt_put
    else:
        cds_call, cds_put = await asyncio.gather(
            ib.reqContractDetailsAsync(opt_call),
            ib.reqContractDetailsAsync(opt_put)
        )
        contract_call = cds_call[0].contract
        contract_put  = cds_put[0].contract

    # request live market data for call+put *simultaneously*
    call_tkr, put_tkr = await asyncio.gather(
        asyncio.to_thread(ib.reqMktData, contract_call,
                          genericTickList=GENERIC_TICKS, snapshot=False),
        asyncio.to_thread(ib.reqMktData, contract_put,
                          genericTickList=GENERIC_TICKS, snapshot=False)
    )

    # wait for the first update on each
    await asyncio.gather(
        asyncio.wait_for(call_tkr.updateEvent.wait(), TIMEOUT_S),
        asyncio.wait_for(put_tkr.updateEvent.wait(),  TIMEOUT_S)
    )

    # ------------ YOUR ORIGINAL MATH, UNCHANGED ------------- #
    def norm(x): return x if x is not None else 0

    iv_call = (call_tkr.modelGreeks.impliedVol
               if call_tkr.modelGreeks and call_tkr.modelGreeks.impliedVol is not None
               else call_tkr.impliedVolatility)

    iv_put  = (put_tkr.modelGreeks.impliedVol
               if put_tkr.modelGreeks and put_tkr.modelGreeks.impliedVol is not None
               else put_tkr.impliedVolatility)

    call_gamma = call_tkr.modelGreeks.gamma if call_tkr.modelGreeks else 0
    put_gamma  = put_tkr.modelGreeks.gamma  if put_tkr.modelGreeks else 0

    total_call_gamma = call_gamma * 100 * (call_tkr.callOpenInterest or 0) \
                       * (strike * multiply)**2 * 0.01
    total_put_gamma  = put_gamma  * 100 * (put_tkr.putOpenInterest  or 0) \
                       * (strike * multiply)**2 * 0.01 * -1

    total_gamma = (total_call_gamma if not math.isnan(total_call_gamma) else 0) + \
                  (total_put_gamma  if not math.isnan(total_put_gamma)  else 0)
    # -------------------------------------------------------- #

    print("----------------------------------------")
    print("Strike           :", strike * multiply)
    print("Volume           :", norm(call_tkr.volume))
    print("Call OI          :", norm(call_tkr.callOpenInterest))
    print("Put  OI          :", norm(put_tkr.putOpenInterest))
    print("Call Γ (×1e6)    :", round(total_call_gamma / 1_000_000))
    print("Put  Γ (×1e6)    :", round(total_put_gamma  / 1_000_000))
    print("Total Γ          :", round(total_gamma))
    print("IV call          :", norm(iv_call))
    print("IV put           :", norm(iv_put))

    # tidy-up: close the live streams so they don’t hit the 100-stream limit
    ib.cancelMktData(call_tkr)
    ib.cancelMktData(put_tkr)

async def main():
    ib = IB()
    
    try:
        
        await ib.connectAsync("127.0.0.1", 4001, clientId=17)

        strikes = [575, 580, 585, 590]

        sem = asyncio.Semaphore(N_CONCURRENT_STRIKES)

        async def limited_analyse(strike):
            async with sem:
                await analyse_strike(ib, "SPY", strike,
                                     asset_obj=assetObject,
                                     expiry_arg="20250515",
                                     ticker_exch="SMART",
                                     use_predefined_contracts=False,
                                     strike_range=[575, 590])
    
        await asyncio.gather(*(limited_analyse(s) for s in strikes))
    finally:
        ib.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
