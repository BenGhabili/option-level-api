import asyncio
from ib_insync import IB, Stock

async def warmup (ib, data_type):
    ib.reqMarketDataType(data_type)  # 1 = live
    ib.reqMktData(Stock('SPY','SMART','USD'), '', snapshot=True)

###############################################################################
#  Connection helpers
###############################################################################
async def connect_ib(host: str = "127.0.0.1", port: int = 4001, client_id: int = 17) -> IB:
    """Return a connected & warmed‑up IB instance."""
    ib = IB()
    await ib.connectAsync(host, port, clientId=client_id)

    return ib


# async def fetch_stock_ticker(ib, ticker):
#     """Fetch the current stock price."""
#     contract = Stock(ticker, 'SMART', 'USD')
#     ticker_data = ib.reqMktData(contract, '233', snapshot=False)
# 
#     await asyncio.sleep(3)
#     
#     return ticker_data