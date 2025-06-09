

def calculate_gex(strike, call_oi, call_gamma, put_oi, put_gamma):
    """Calculate Gamma Exposure for a strike level"""
    if None in [call_oi, call_gamma, put_oi, put_gamma]:
        return None

    # GEX calculation (simplified)
    call_gex = call_oi * call_gamma * 100 * strike
    put_gex = -1 * put_oi * put_gamma * 100 * strike  # Put gamma is positive in IB

    net_gex = call_gex + put_gex
    return call_gex, put_gex, net_gex