from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from ib_insync import IB, Stock, Option, Contract
import math
import argparse

import pprint

###############################################################################
# 1.  Connection helpers
###############################################################################

def connect_ib(market_data_type = 1, host: str = "127.0.0.1", port: int = 4001, client_id: int = 17) -> IB:
    """Return a connected & warmed‑up IB instance."""
    ib = IB()
    ib.connect(host, port, clientId=client_id)
    ib.reqMarketDataType(market_data_type)  # 1 = live

    ib.reqMktData(Stock('SPY','SMART','USD'), '', snapshot=True)
    ib.sleep(0.5)
    
    return ib

def norm(x):
    return "–" if x is None or (isinstance(x, float) and math.isnan(x)) else x

contract_date = "20250513"
exchange = "SMART"
asset = "SPX"
use_predefined_contracts = False

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

def main(ticker: str, expiry_arg: str | None, width: int, data: int):
    ib = connect_ib(data)
    
    asset_data = None
    # ticker = assetObject[asset]["asset_price_ticker"]
    ticker_exchange = assetObject[ticker]["exchange"]
    
    # warm‑up
    if ticker == "SPX":
        targeted_stock = Contract(symbol=ticker, secType='IND', exchange=ticker_exchange, currency='USD')
        asset_data = ib.reqMktData(targeted_stock, '233', snapshot=False)
    else:
        targeted_stock = Stock(ticker,ticker_exchange,'USD')
        asset_data = ib.reqMktData(targeted_stock, '233', snapshot=False)
    
    strike_range = None  
    
    ib.sleep(1)
    
    if asset_data:
        divide_value = 10 if ticker == "SPX" else 1
        rounded_price = round(asset_data.last / divide_value)
        strike_range = range(rounded_price - width, rounded_price + width)  
    
    print("\n── TICKER __dict__ ───────────────────────────────────")
    print(f"Centre Price: { asset_data.last}")
    print(f"Using ticker {ticker}  |  exchange {ticker_exchange} |  Expiry {expiry_arg}" )
    # pprint.pprint(asset_data.__dict__)  # shows you the raw dict of attributes
    
    ib.sleep(1)  
    
    
    for i in (assetObject[asset]["contract_list"] if not strike_range or use_predefined_contracts else strike_range):
        multiply_value = 10 if ticker == "SPX" else 1
        opt_call = Option(assetObject[ticker]["asset_name"], expiry_arg, i * multiply_value, 'C', ticker_exchange)
        opt_put = Option(assetObject[ticker]["asset_name"], expiry_arg, i * multiply_value, 'P', ticker_exchange)
    
        if ticker_exchange in ("SMART", "CBOE"):
            contract_call = opt_call
            contract_put = opt_put
        else:
            cds_call = ib.reqContractDetails(opt_call)
            cds_put = ib.reqContractDetails(opt_put)
            contract_call = cds_call[0].contract # or pick SMART as above
            contract_put = cds_put[0].contract
        
        
        md_call = ib.reqMktData(contract_call, genericTickList="100,101,104,105,106", snapshot=False)
        ib.sleep(1)
        md_put = ib.reqMktData(contract_put, genericTickList="100,101,104,105,106", snapshot=False)
        ib.sleep(1)

        print("----------------------------------------")
        print("Strike    :", i * multiply_value)
        print("Volume     :", norm(md_call.volume))
        print("Call OI    :", norm(md_call.callOpenInterest))
        print("Put  OI    :", norm(md_put.putOpenInterest))
        
        # print(md_call.__dict__)
        
        iv_call = (
            md_call.modelGreeks.impliedVol if md_call.modelGreeks and md_call.modelGreeks.impliedVol is not None
            else md_call.impliedVolatility if md_call.impliedVolatility is not None
            else None
        )
    
        iv_put = (
            md_put.modelGreeks.impliedVol if md_put.modelGreeks and md_put.modelGreeks.impliedVol is not None
            else md_put.impliedVolatility if md_put.impliedVolatility is not None
            else None
        )
        
        call_gamma = 0
        put_gamma = 0

        if md_call.modelGreeks and md_call.modelGreeks.gamma is not None:
            call_gamma = md_call.modelGreeks.gamma

        if md_put.modelGreeks and md_put.modelGreeks.gamma is not None:
            put_gamma = md_put.modelGreeks.gamma

        total_call_gamma = call_gamma * 100 * (md_call.callOpenInterest or 0) * (i * multiply_value) ** 2 * 0.01
        if math.isnan(total_call_gamma):
            total_call_gamma = 0

        total_put_gamma = put_gamma * 100 * (md_put.putOpenInterest or 0) * (i * multiply_value) ** 2 * 0.01 * -1
        if math.isnan(total_put_gamma):
            total_put_gamma = 0

        total_gamma = total_call_gamma + total_put_gamma

        print("Call Gamma     :", round(total_call_gamma / 1000000 if total_call_gamma else 0), "M")
        print("Put Gamma     :", round(total_put_gamma / 1000000 if total_put_gamma else 0), "M")
        print("Total Gamma for strike    :", round(total_gamma))
        print("ImpliedVol_call:", norm(iv_call))
        print("ImpliedVol_put:", norm(iv_put))
    
        # print("\n── TICKER __dict__ ───────────────────────────────────")
        # pprint.pprint(md_call.__dict__)  # shows you the raw dict of attributes
        
        ib.cancelMktData(contract_call)
        ib.cancelMktData(contract_put)
    
    ib.disconnect()

###############################################################################
# 6.  CLI entry‑point
###############################################################################

if __name__ == "__main__":
    datetime.now(ZoneInfo("America/New_York"))
    parser = argparse.ArgumentParser(description="Minimal IB option‑chain snapshot")
    parser.add_argument("--ticker", default="SPY", help="Underlying symbol (default SPY)")
    parser.add_argument("--expiry", default=datetime.today().strftime('%Y%m%d'),
                        help="YYYYMMDD; omit for first available")
    parser.add_argument("--width", type=int, default=5, help="Half‑width in strike units (default 5)")
    parser.add_argument("--data", type=int, default=1, help="type of market data to request")
    args = parser.parse_args()

    main(args.ticker.upper(), args.expiry, args.width, args.data)