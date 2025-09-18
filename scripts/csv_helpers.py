# ---------------------------------------------------------
#  workable_oi_levels
#  -------------------
#  • Builds the “12-level” file your indicator needs.
#  • Rules implemented are the same ones we’ve been using:
#      – ±4 % strike-band
#      – 6 biggest call walls  ∪  6 biggest put walls
#      – fill to 12 by combined OI
#      – weaker side set to 0 if ≥5 × imbalance
# ---------------------------------------------------------
from pathlib import Path
import pandas as pd
from datetime import datetime

BAND_PCT = 0.4
N_CALL = 6
N_PUT = 6
TARGET_ROW = 12
IMBALANCE_K = 5
TARGET_FOLDER = r"D:\TradingData"

def workable_oi_levels(
        results: list,
        ticker: str,
        spot_price: float,
        expiry: str,
        out_dir: str = TARGET_FOLDER,
        band_pct: float =BAND_PCT,
        n_call: int = N_CALL,
        n_put: int = N_PUT,
        target_rows: int = TARGET_ROW,
        imbalance_k: int = IMBALANCE_K,
) -> None:
    """
    Build and save the 12 'workable' OI levels for a given ticker / expiry.
    results  – same list of dicts you pass to append_oi_data
    spot_price – current underlying price (float)
    expiry  – 'YYYYMMDD' or similar; becomes the 'date' column
    """

    # ── 1. drop strikes outside the ±band_pct window ──────────────────────────
    band = band_pct * spot_price
    filtered = [
        r for r in results
        if abs(r['strike'] - spot_price) <= band
    ]
    if not filtered:
        print("⚠️  No strikes inside ±%.1f%% band" % (band_pct*100))
        return

    # ── 2. enrich with helper columns ─────────────────────────────────────────
    for r in filtered:
        r['call_oi'] = r['call']['oi']
        r['put_oi']  = r['put']['oi']
        r['combined']= r['call_oi'] + r['put_oi']

    # ── 3. pick top walls ─────────────────────────────────────────────────────
    top_calls = sorted(filtered, key=lambda x: x['call_oi'], reverse=True)[:n_call]
    top_puts  = sorted(filtered, key=lambda x: x['put_oi'],  reverse=True)[:n_put]
    core = {r['strike']: r for r in top_calls + top_puts}   # union via dict

    # ── 4. fill or trim to the target_rows count ──────────────────────────────
    if len(core) < target_rows:
        extras = [
            r for r in sorted(filtered, key=lambda x: x['combined'], reverse=True)
            if r['strike'] not in core
        ]
        for r in extras:
            core[r['strike']] = r
            if len(core) == target_rows:
                break
    elif len(core) > target_rows:
        # drop the lowest-combined until size matches
        to_drop = sorted(core.values(), key=lambda x: x['combined'])
        while len(core) > target_rows:
            core.pop(to_drop.pop(0)['strike'])

    # ── 5. imbalance cleanup ──────────────────────────────────────────────────
    final_rows = []
    for r in sorted(core.values(), key=lambda x: x['strike']):
        c, p = r['call_oi'], r['put_oi']
        if c >= imbalance_k * max(p, 1):
            p = 0
        elif p >= imbalance_k * max(c, 1):
            c = 0
        final_rows.append({
            'expiry'     : expiry,
            'timestamp': '',           # left blank by design
            'strike'   : r['strike'],
            'call_oi'  : int(c),
            'put_oi'   : int(p),
        })

    # ── 6. save to CSV ────────────────────────────────────────────────────────
    out_path = Path(out_dir) / f"{ticker.upper()}_OI_levels.csv"
    pd.DataFrame(final_rows).to_csv(out_path, index=False)
    print(f"✅  Saved {len(final_rows)} levels → {out_path}")


def append_oi_data(results, ticker, expiry, data_dir: str = "./data", spot: int | None = None):
    """
    Append a batch of OI results to data/{ticker}_oi.csv, creating the file if needed.

    results: list of dicts with keys 'strike', 'call', 'put', where
             result['call']['oi'] and result['put']['oi'] exist.
    ticker:  the symbol string, e.g. "ES" or "NQ"
    data_dir: path to directory where CSVs live
    """
    now = datetime.now()
    yyyymm     = now.strftime('%Y%m')         # e.g. 202507
    base_dir = Path(TARGET_FOLDER) / "historical_OI"
    month_folder = Path(base_dir) / yyyymm
    # ensure directory exists
    data_dir = Path(data_dir)
    # data_dir.mkdir(parents=True, exist_ok=True)
    base_dir.mkdir(parents=True, exist_ok=True)

    # CSV path for this ticker
    # csv_path = data_dir / f"{ticker}_oi.csv"
    csv_path = base_dir / f"{yyyymm}_{ticker}_oi.csv"

    # Build DataFrame of new rows
    rows = []

    now_ts   = datetime.now().isoformat(timespec='minutes')
    default_ts = now_ts.replace('-', '').replace(':', '').replace('T', '')
    for result in results:
        row = {
            "expiry":      expiry,
            "timestamp": default_ts,
            "strike":    result["strike"],
            "call_oi":   result["call"]["oi"],
            "put_oi":    result["put"]["oi"]
        }
        if spot is not None:
            row["spot"] = spot
        rows.append(row)

    base_columns = ["expiry", "timestamp", "strike", "call_oi", "put_oi"]
    if rows and "spot" in rows[0]:
        base_columns.append("spot")
    new_df = pd.DataFrame(rows, columns=base_columns)

    # Load existing (if any) and append
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        df = pd.concat([df, new_df], ignore_index=True)
    else:
        df = new_df

    # Write back out
    df.to_csv(csv_path, index=False)
    log_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{log_time}] ✅  Appended {len(new_df)} rows → {csv_path!r}")


def gex_data_save(results,
                  ticker: str,
                  base_dir: str = r"D:\TradingData",
                  spot: int | None = None) -> None:
    """
    Append a snapshot of GEX data to a daily file located at
    {base_dir}\YYYYMM\{TICKER}_GEX_YYYYMMDD.csv

    Columns: timestamp (YYYYMMDDhhmm), strike, call_gex, put_gex
    Each call simply *appends* the current run to the file for that day.
    """
    now = datetime.now()
    yyyymm     = now.strftime('%Y%m')         # e.g. 202507
    yyyymmdd   = now.strftime('%Y%m%d')       # e.g. 20250716
    timestamp  = now.strftime('%Y%m%d%H%M')   # e.g. 202507161505

    # ── 1. build folder + file paths ────────────────────────────────────────
    month_folder = Path(base_dir) / yyyymm
    month_folder.mkdir(parents=True, exist_ok=True)

    csv_path = month_folder / f"{ticker.upper()}_GEX_{yyyymmdd}.csv"

    # ── 2. create a DataFrame for this run ───────────────────────────────────
    rows = []
    for r in results:
        row = {
            "timestamp": timestamp,
            "strike"   : r["strike"],
            "call_gex" : round(r["call"]["call_gex"] / 1e6, 1),
            "put_gex"  : round(r["put"]["put_gex"]  / 1e6, 1),
            "net_gex"  : round(r["net_gex"]         / 1e6, 1),
        }
        if spot is not None:
            row["spot"] = spot
        rows.append(row)

    columns = ["timestamp", "strike", "call_gex", "put_gex", "net_gex"]
    if rows and "spot" in rows[0]:
        columns.append("spot")
    new_df = pd.DataFrame(rows, columns=columns)

    # ── 3. append (or create) ────────────────────────────────────────────────
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        df = pd.concat([df, new_df], ignore_index=True)
    else:
        df = new_df

    df.to_csv(csv_path, index=False)
    log_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{log_time}] ✅  Appended {len(new_df)} rows → {csv_path}")   