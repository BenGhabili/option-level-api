from ib_insync import IB, Stock
import threading

_ib = None
_lock = threading.Lock()

def get_ib():
    global _ib
    with _lock:
        if _ib is None or not _ib.isConnected():
            _ib = IB()
            _ib.connect('127.0.0.1', 4001, clientId=11)   # one dedicated ID
            _ib.reqMarketDataType(1)                     # live first
            # warm‑up
            _ib.reqMktData(Stock('SPY','SMART','USD'), '', snapshot=True)
            _ib.sleep(0.5)
        return _ib
