import argparse
from pathlib import Path
from datetime import datetime
import pandas as pd
import math

BASE_DIR = Path(r"D:\TradingData")


def strike_step_for(ticker: str, default_spx_step: int = 10) -> int:
    t = ticker.upper()
    if t == "SPX":
        return default_spx_step
    return 1


def find_zgamma(strikes, net_gex, spot):
    # choose the sign flip nearest to spot
    df = pd.DataFrame({"strike": strikes, "net": net_gex}).dropna().sort_values("strike")
    if df.empty:
        return math.nan
    # find adjacent rows where sign flips
    df["sign"] = (df["net"] > 0).astype(int) - (df["net"] < 0).astype(int)
    # indices of flips
    flips = []
    for i in range(1, len(df)):
        if df.iloc[i - 1]["sign"] == 0 or df.iloc[i]["sign"] == 0:
            continue
        if df.iloc[i - 1]["sign"] != df.iloc[i]["sign"]:
            flips.append(i)
    if not flips:
        return math.nan
    # choose flip closest to spot
    def interp(i):
        s0, n0 = df.iloc[i - 1]["strike"], df.iloc[i - 1]["net"]
        s1, n1 = df.iloc[i]["strike"], df.iloc[i]["net"]
        if n1 == n0:
            return (s0 + s1) / 2.0
        # linear interpolation for net=0 between (s0,n0) and (s1,n1)
        w = abs(n0) / (abs(n0) + abs(n1))
        return s0 + w * (s1 - s0)

    zcands = [(abs(interp(i) - spot), interp(i)) for i in flips]
    zcands.sort(key=lambda x: x[0])
    return zcands[0][1]


def ramp_around_spot(strikes, net_gex, spot, step):
    # approximate derivative using nearest lower/upper strikes by step
    df = pd.DataFrame({"strike": strikes, "net": net_gex}).dropna().sort_values("strike")
    if df.empty:
        return math.nan
    # nearest lower and upper strike multiples of step around spot rounding
    lower = math.floor(spot / step) * step
    upper = lower + step
    n_lower = df.loc[df["strike"] == lower, "net"]
    n_upper = df.loc[df["strike"] == upper, "net"]
    if n_lower.empty or n_upper.empty:
        return math.nan
    return float((n_upper.values[0] - n_lower.values[0]) / (upper - lower))


def largest_walls(strikes, call_gex, put_gex):
    df = pd.DataFrame({"strike": strikes, "call": call_gex, "put": put_gex}).dropna()
    if df.empty:
        return (math.nan, math.nan, math.nan, math.nan)
    call_idx = df["call"].idxmax()
    # put_gex is negative; use absolute to find largest magnitude put wall
    put_idx = (df["put"].abs()).idxmax()
    return (
        float(df.loc[call_idx, "strike"]), float(df.loc[call_idx, "call"]),
        float(df.loc[put_idx, "strike"]), float(df.loc[put_idx, "put"]) 
    )


def distances(spot, zgamma, wall_strikes):
    if spot is None or math.isnan(spot):
        return (math.nan, math.nan)
    dz = abs(spot - zgamma) if zgamma is not None and not math.isnan(zgamma) else math.nan
    nearest_wall = math.nan
    if wall_strikes:
        nearest_wall = min(abs(spot - ws) for ws in wall_strikes if ws is not None and not math.isnan(ws)) if any(wall_strikes) else math.nan
    return (dz, nearest_wall)


def nearest_wall_by_net(strikes, net_gex, spot):
    """Return the strike with maximum |Net_GEX|, tie-broken by closeness to spot,
    along with its |Net_GEX| magnitude and distance to spot.
    """
    if spot is None or math.isnan(spot):
        return (math.nan, math.nan, math.nan)
    df = pd.DataFrame({"strike": strikes, "net": net_gex}).dropna()
    if df.empty:
        return (math.nan, math.nan, math.nan)
    df["abs_net"] = df["net"].abs()
    max_abs = df["abs_net"].max()
    cands = df[df["abs_net"] == max_abs].copy()
    cands["dist"] = (cands["strike"] - spot).abs()
    row = cands.sort_values(["dist"]).iloc[0]
    return (float(row["strike"]), float(row["abs_net"]), float(row["dist"]))


def compression_score(total_net_norm, ramp_abs, dist_to_z_pts, eps=1e-6):
    # simple deterministic score in [0, 100]; use logs to keep scale stable
    s1 = math.log1p(abs(total_net_norm))
    s2 = math.log1p(abs(ramp_abs)) if not math.isnan(ramp_abs) else 0.0
    s3 = math.log1p(1.0 / max(dist_to_z_pts, eps)) if not math.isnan(dist_to_z_pts) else 0.0
    raw = 0.5 * s1 + 0.3 * s2 + 0.2 * s3
    return round(100.0 * raw / (raw + 1.0), 2)


def process_one_snap(df_snap, ticker, spx_step):
    # df_snap has columns: timestamp, strike, call_gex, put_gex, net_gex, optionally spot
    strikes = df_snap["strike"].tolist()
    call_g = df_snap["call_gex"].tolist()
    put_g = df_snap["put_gex"].tolist()
    net_g = df_snap["net_gex"].tolist()
    spot = df_snap.get("spot", pd.Series([math.nan])).iloc[0]

    total_net = float(pd.Series(net_g).sum())
    step = strike_step_for(ticker, spx_step)
    zg = find_zgamma(strikes, net_g, spot)
    ramp = ramp_around_spot(strikes, net_g, spot, step)
    c_strike, c_mag, p_strike, p_mag = largest_walls(strikes, call_g, put_g)
    dz, dn = distances(spot, zg, [c_strike, p_strike])
    nw_strike, nw_value, nw_dist = nearest_wall_by_net(strikes, net_g, spot)
    total_net_norm = total_net / spot if spot and not math.isnan(spot) and spot != 0 else math.nan
    comp = compression_score(total_net_norm if not math.isnan(total_net_norm) else 0.0,
                             ramp if not math.isnan(ramp) else 0.0,
                             dz if not math.isnan(dz) else 1.0)

    ts = df_snap["timestamp"].iloc[0]
    return {
        "timestamp": ts,
        "spot": spot if spot is not None else math.nan,
        "total_net_gex": round(total_net, 3),
        "total_net_gex_norm": round(total_net_norm, 6) if not math.isnan(total_net_norm) else math.nan,
        "zgamma": round(zg, 2) if not math.isnan(zg) else math.nan,
        "ramp": round(ramp, 6) if not math.isnan(ramp) else math.nan,
        "largest_call_wall_strike": c_strike,
        "largest_call_wall": round(c_mag, 1) if not math.isnan(c_mag) else math.nan,
        "largest_put_wall_strike": p_strike,
        "largest_put_wall": round(p_mag, 1) if not math.isnan(p_mag) else math.nan,
        "dist_to_zgamma_pts": round(dz, 2) if not math.isnan(dz) else math.nan,
        "dist_to_nearest_wall_pts": round(dn, 2) if not math.isnan(dn) else math.nan,
        # Extensions
        "dist_to_zgamma": round(dz, 2) if not math.isnan(dz) else math.nan,
        "nearest_wall_strike": nw_strike,
        "nearest_wall_value": round(nw_value, 1) if not math.isnan(nw_value) else math.nan,
        "dist_to_nearest_wall": round(nw_dist, 2) if not math.isnan(nw_dist) else math.nan,
        "compression_score": comp,
    }


def derive_for_day(ticker: str, yyyymmdd: str, spx_step: int = 10, latest_only: bool = False, full: bool = False,
                   input_file: str = None, output_dir: str = None):
    month = yyyymmdd[:6]
    # Resolve input
    if input_file:
        gex_path = Path(input_file)
    else:
        gex_path = BASE_DIR / month / f"{ticker.upper()}_GEX_{yyyymmdd}.csv"
    if not gex_path.exists():
        print(f"Missing GEX file: {gex_path}")
        return None, None

    df = pd.read_csv(gex_path)
    # normalize columns
    cols = {c.lower(): c for c in df.columns}
    df = df.rename(columns={v: k for k, v in cols.items()})
    # unify timestamp as string for grouping/comparison
    if "timestamp" in df.columns:
        df["timestamp"] = df["timestamp"].astype(str)
    # ensure required columns
    required = {"timestamp", "strike", "call_gex", "put_gex", "net_gex"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in {gex_path}: {missing}")

    # decide which timestamps to compute
    out_rows = []
    # Resolve output path
    if output_dir:
        analysis_dir = Path(output_dir)
        out_path = analysis_dir / f"{ticker.upper()}_GEX_{yyyymmdd}_metrics.csv"
    else:
        analysis_dir = BASE_DIR / month / "analysis"
        out_path = analysis_dir / f"{ticker.upper()}_GEX_{yyyymmdd}_metrics.csv"
    all_ts = sorted(df["timestamp"].unique())

    if latest_only:
        target_ts = [all_ts[-1]] if all_ts else []
    elif full:
        target_ts = all_ts
    else:
        # incremental: only timestamps not already present in metrics file
        if out_path.exists():
            existing = pd.read_csv(out_path)
            if "timestamp" in existing.columns:
                existing_ts = set(existing["timestamp"].astype(str).tolist())
            else:
                existing_ts = set()
        else:
            existing_ts = set()
        target_ts = [ts for ts in all_ts if ts not in existing_ts]

    for ts, snap in df.groupby("timestamp"):
        if ts not in target_ts:
            continue
        # enforce numeric types
        snap = snap.copy()
        for c in ["strike", "call_gex", "put_gex", "net_gex", "spot"]:
            if c in snap.columns:
                snap[c] = pd.to_numeric(snap[c], errors="coerce")
        out_rows.append(process_one_snap(snap, ticker, spx_step))

    out = pd.DataFrame(out_rows)
    if not out.empty:
        out = out.sort_values("timestamp")
    return out, out_path


def main():
    parser = argparse.ArgumentParser(description="Derive per-snapshot GEX metrics from daily CSV")
    parser.add_argument("--ticker", default="SPY")
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    parser.add_argument("--spx_step", type=int, default=10, help="SPX strike step (default 10)")
    parser.add_argument("--csv", default='N', help="Write metrics CSV (Y/N)")
    parser.add_argument("--quiet", action="store_true", help="Suppress console output")
    parser.add_argument("--latest", default='N', help="Compute only latest snapshot (Y/N)")
    parser.add_argument("--full", default='N', help="Recompute entire day (Y/N). Overrides --latest")
    parser.add_argument("--input_file", default=None, help="Optional explicit input GEX CSV path")
    parser.add_argument("--output", default=None, help="Optional output directory for metrics CSVs")
    args = parser.parse_args()
    latest_only = str(args.latest).strip().upper().startswith('Y')
    full = str(args.full).strip().upper().startswith('Y')
    if full:
        latest_only = False
    
    df, out_path = derive_for_day(
        args.ticker.upper(), args.date, args.spx_step,
        latest_only=latest_only, full=full,
        input_file=args.input_file, output_dir=args.output
    )
    if df is None:
        return
    write_csv = str(args.csv).strip().upper().startswith('Y')
    if write_csv:
        if df.empty:
            if not args.quiet:
                print("No new timestamps to write.")
            return
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if full or not out_path.exists():
            # overwrite for full recompute or first write
            df.to_csv(out_path, index=False)
        else:
            # append and de-dupe on timestamp
            existing = pd.read_csv(out_path) if out_path.exists() else pd.DataFrame()
            combined = pd.concat([existing, df], ignore_index=True)
            if "timestamp" in combined.columns:
                combined["timestamp"] = combined["timestamp"].astype(str)
                combined = combined.drop_duplicates(subset=["timestamp"], keep="last")
            combined = combined.sort_values("timestamp")
            combined.to_csv(out_path, index=False)
        if not args.quiet:
            print(f"✅ Wrote {len(df)} new rows → {out_path}")
    else:
        if not args.quiet:
            print(f"Symbol: {args.ticker.upper()}  Date: {args.date}  Rows: {len(df)}")
            if df.empty:
                print("(no rows)")
                return
            print("timestamp,spot,total_net_gex,zgamma,ramp,compression_score")
            for _, r in df.iterrows():
                print(f"{r['timestamp']},{r['spot']},{r['total_net_gex']},{r['zgamma']},{r['ramp']},{r['compression_score']}")


if __name__ == "__main__":
    main()


