from ib_insync import Option, Stock, Contract
from .ib_connection import get_ib

def fetch_chain_ib(ticker:str, expiry:str):
    ib = get_ib()

    # 1) Qualify underlying
    if ticker == 'SPX':
        underlying = Contract(symbol='SPX', secType='IND', exchange='CBOE', currency='USD')
    else:
        underlying = Stock(ticker, 'SMART', 'USD')
    underlying = ib.qualifyContracts(underlying)[0]

    # 2) Get strikes for chosen expiry
    params = ib.reqSecDefOptParams(underlying.symbol, '', underlying.secType, underlying.conId)
    chain = next(c for c in params if expiry in c.expirations)
    strikes = sorted(chain.strikes)

    # 3) Build Option contracts
    options = [
        Option(underlying.symbol, expiry, s, r, 'SMART')
        for s in strikes for r in ('C','P')
    ]
    details = ib.qualifyContracts(*options)

    # 4) Batch request snapshots with tick list 225 (OI, IV, greeks)
    tickers = ib.reqTickers(*details, tickList='225')

    # Wait briefly
    ib.sleep(max(1, len(tickers)/50))

    # 5) Aggregate per‐strike
    result = []
    last = ib.reqMktData(underlying, '', snapshot=True)
    ib.sleep(0.5)
    S = last.last or last.close

    for s in strikes:
        call = next(t for t in tickers if t.contract.strike==s and t.contract.right=='C')
        put  = next(t for t in tickers if t.contract.strike==s and t.contract.right=='P')
        gex = ( (call.gamma or 0)*(call.openInterest or 0)
                + (put.gamma  or 0)*(put.openInterest  or 0) ) * (S**2)*100
        result.append({
            'strike': s,
            'call_OI': call.openInterest or 0,
            'put_OI' : put.openInterest  or 0,
            'iv'     : ((call.impliedVol or 0)+(put.impliedVol or 0))/2,
            'GEX'    : gex
        })
    return result
