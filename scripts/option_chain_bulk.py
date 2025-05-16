from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from ib_insync import IB, Stock, Option, Contract, Index, util
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

def main(ticker_name: str, expiry_arg: str | None, width: int, data: int):
    ib = connect_ib(data)

    # spx = Index('SPX', 'CBOE', 'USD')
    # spy = Stock('SPY', 'SMART', 'USD')
    if ticker_name == "SPX":
        ticker_to_fetch = Contract(symbol='SPX', secType='IND', exchange='CBOE', currency='USD')
        trading_class = "SPXW"
        trading_exchange = "CBOE"
        price_step = 5
    else:
        ticker_to_fetch = Stock(ticker_name, 'SMART', 'USD')
        trading_exchange = "SMART"
        trading_class = ticker_name
        price_step = 1
        
        
    # spx = Contract(symbol='SPX', secType='IND', exchange='CBOE', currency='USD')
    ib.qualifyContracts(ticker_to_fetch)
    # ib.qualifyContracts(spy)
    
    # asset = ib.reqMktData(spx, '233', snapshot=False)
    [ticker] = ib.reqTickers(ticker_to_fetch)
    # [ticker] = ib.reqTickers(spy)
    
    ib.sleep(1)
    
    
    asset_value = ticker.marketPrice()
    # spyValue = ticker.marketPrice()
    
    # print(f"SPY value: {spyValue}")
    print(f"{ticker_name} last: {asset_value}")
    
    chains = ib.reqSecDefOptParams(ticker_to_fetch.symbol, '', ticker_to_fetch.secType, ticker_to_fetch.conId)
    # chains = ib.reqSecDefOptParams(spy.symbol, '', spy.secType, spy.conId)
    
    # util.df(chains)
    # print(df.to_string())     
        
    chain = next(c for c in chains if c.tradingClass == trading_class and c.exchange == trading_exchange)
    # chain = next(c for c in chains if c.tradingClass == "SPY" and c.exchange == "SMART")
    
    # util.df(chain)
    
    # print(f"Chain: {chain}")
    
    strikes = [strike for strike in chain.strikes
               if strike %price_step == 0
               and asset_value - width < strike < asset_value + width
               ]
    # strikes = [strike for strike in chain.strikes if strike %1 == 0 and spyValue - 10 < strike < spyValue + 10]
    # print(f"Strikes: {strikes}")
    
    expirations = sorted(exp for exp in chain.expirations)[:3]
    
    # print(f"Expirations: {expirations}")
    
    rights = ['C', 'P']
    
    contracts = [Option(ticker_name, expiration, strike, right, trading_exchange, tradingClass=trading_class)
                 for expiration in expirations
                 for strike in strikes
                 for right in rights]
    # contracts = [Option("SPY", expiration, strike, right, 'SMART', tradingClass="SPY")
    #              for expiration in expirations
    #              for strike in strikes
    #              for right in rights]
    
    contracts = ib.qualifyContracts(*contracts)
    
    # test = ib.reqMktData(*contracts, '', False)
    # ib.reqMktData(contract_call, genericTickList="100,101,104,105,106", snapshot=False)
    
    ib.sleep(1)
    
    # print(contracts[0])
    
    tickers = ib.reqTickers(*contracts)
    filtered_data = []

    for ticker in tickers:
        contract = ticker.contract
        
        print(f"ticker: {ticker}")
        
        if contract.right == "C":
            open_interest = ticker.callOpenInterest
        else:
            open_interest = ticker.putOpenInterest
        
        greeks = ticker.modelGreeks
        
        # print(f"Open interest: {open_interest}")
        
        data_point = {
            'strike': contract.strike,
            'expiry': contract.lastTradeDateOrContractMonth,
            'multiplier': contract.multiplier,
            'right': contract.right,
            'delta': greeks.delta if greeks else None,
            'impliedVol': greeks.impliedVol if greeks else None,
            'gamma': greeks.gamma if greeks else None,
            'theta': greeks.theta if greeks else None
        }

        filtered_data.append(data_point)

    # filtered_df = util.df(filtered_data)
    # filtered_df.to_csv(f"./data/filtered_option_chain_SPX.csv", index=False)
    
    # print(f"Strikes: {strikes}")
    # expirations = sorted(chain[0].expirations)
    # 
    # print(f"Expirations: {expirations}")
    # 
    # if expiry_arg not in expirations:
    #     print(f"No expirations found for {ticker.symbol} on {expiry_arg}")


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