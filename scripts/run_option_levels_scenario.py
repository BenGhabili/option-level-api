#!/usr/bin/env python3
"""
run_option_levels_scenario.py

Simulates:
  1) The scheduled fetcher Lambda (build & “store” today’s levels)
  2) An API retrieval of one ticker’s data

Run:
  python run_option_levels_scenario.py
"""

import json
from datetime import datetime, timedelta
from types import SimpleNamespace

from services.option_service import build_option_levels

def run_scenario_oi():
    tickers = ["SPY", "QQQ", "^SPX"]

    today = SimpleNamespace(
        date=datetime.utcnow().strftime("%Y-%m-%d"),
        expiry="front"
    )

    tomorrow = SimpleNamespace(
        date=(datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d"),
        expiry="next"
    )

    day_of_retrival = tomorrow

    # 1) “Scheduled fetch” step
    print(f"=== Fetcher run for {day_of_retrival.date} ===")
    all_data = {}
    for t in tickers:
        data = build_option_levels(
            ticker=t,
            expiry_param=day_of_retrival.expiry,
            center=None,
            width=20,
            # include_greeks=False
            include_greeks=True
        )
        all_data[t] = data or {"error": "no data"}
    print(json.dumps(all_data, indent=2))

    # 2) “API call” step (e.g. retrieving SPY levels)
    print(f"\n=== API returns for SPY on {day_of_retrival.date} ===")
    print(json.dumps(all_data["SPY"], indent=2))

def run_scenario_gex():
    # 1) “Scheduled fetch” step
    print(f"=== Fetcher run for today ===")
    data = build_option_levels(
        ticker="SPY",
        expiry_param="next",
        center=None,
        width=20,
        include_greeks=True   # ← now includes IV & GEX
    )
    print(data["strikes"][:3])

if __name__ == "__main__":
    run_scenario_gex()