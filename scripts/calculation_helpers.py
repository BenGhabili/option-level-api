from math import sqrt

def calculate_gex(strike, call_oi, call_gamma, put_oi, put_gamma):
    """Calculate Gamma Exposure for a strike level"""
    if None in [call_oi, call_gamma, put_oi, put_gamma]:
        return None

    # GEX calculation (simplified)
    call_gex = call_oi * call_gamma * 100 * strike
    put_gex = -1 * put_oi * put_gamma * 100 * strike  # Put gamma is positive in IB

    net_gex = call_gex + put_gex
    return call_gex, put_gex, net_gex

def expected_move(spot: float, iv: float, days: int = 1, trading_days: int = 252) -> float:
    """
    Dollar move one expects over `days` trading days, given annualised IV.

    Parameters
    ----------
    spot : float
        Current underlying price.
    iv : float
        Annualised implied volatility (as a decimal, e.g. 0.24 for 24 %).
    days : int, default 1
        Number of forward days.
    trading_days : int, default 252
        Trading days used for annualisation. Use 365 for calendar-day IV.

    Returns
    -------
    float
        Expected price change (± one standard deviation) in dollars.
    """
    return spot * iv * sqrt(days / trading_days)