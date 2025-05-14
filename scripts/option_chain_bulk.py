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

def main(ticker: str, expiry_arg: str | None, width: int, data: int):
    ib = connect_ib(data)

    # spx = Index('SPX', 'CBOE', 'USD')
    # spy = Stock('SPY', 'SMART', 'USD')
    spx = Contract(symbol='SPX', secType='IND', exchange='CBOE', currency='USD')
    ib.qualifyContracts(spx)
    # ib.qualifyContracts(spy)
    
    # asset = ib.reqMktData(spx, '233', snapshot=False)
    [ticker] = ib.reqTickers(spx)
    # [ticker] = ib.reqTickers(spy)
    
    ib.sleep(1)
    
    
    spxValue = ticker.marketPrice()
    # spyValue = ticker.marketPrice()
    
    # print(f"SPY value: {spyValue}")
    print(f"SPX last: {spxValue}")
    
    chains = ib.reqSecDefOptParams(spx.symbol, '', spx.secType, spx.conId)
    # chains = ib.reqSecDefOptParams(spy.symbol, '', spy.secType, spy.conId)
    
    # util.df(chains)
    # print(df.to_string())
    chain = next(c for c in chains if c.tradingClass == "SPXW" and c.exchange == "CBOE")
    # chain = next(c for c in chains if c.tradingClass == "SPY" and c.exchange == "SMART")
    
    # util.df(chain)
    
    # print(f"Chain: {chain}")
    
    strikes = [strike for strike in chain.strikes if strike %5 == 0 and spxValue - 20 < strike < spxValue + 20]
    # strikes = [strike for strike in chain.strikes if strike %1 == 0 and spyValue - 10 < strike < spyValue + 10]
    # print(f"Strikes: {strikes}")
    
    expirations = sorted(exp for exp in chain.expirations)[:3]
    
    # print(f"Expirations: {expirations}")
    
    rights = ['C', 'P']
    
    contracts = [Option("SPX", expiration, strike, right, 'CBOE', tradingClass="SPXW")
                 for expiration in expirations
                 for strike in strikes
                 for right in rights]
    # contracts = [Option("SPY", expiration, strike, right, 'SMART', tradingClass="SPY")
    #              for expiration in expirations
    #              for strike in strikes
    #              for right in rights]
    
    contracts = ib.qualifyContracts(*contracts)
    
    ib.sleep(1)
    
    # print(contracts[0])
    
    tickers = ib.reqTickers(*contracts)
    filtered_data = []

    for ticker in tickers:
        contract = ticker.contract
        
        greeks = ticker.modelGreeks
        
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

    filtered_df = util.df(filtered_data)
    filtered_df.to_csv(f"./data/filtered_option_chain_SPX.csv", index=False)
    
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