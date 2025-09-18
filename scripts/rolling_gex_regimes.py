import argparse
from pathlib import Path
import pandas as pd
import math
import numpy as np
from pandas.errors import EmptyDataError

BASE_DIR = Path(r"D:\TradingData")


def _rolling_percentile_of_last(values: pd.Series, window: int) -> pd.Series:
    def pct(a: np.ndarray) -> float:
        if a.size == 0:
            return np.nan
        last = a[-1]
        return float(np.mean(a <= last))
    return values.rolling(window, min_periods=1).apply(pct, raw=True)


def compute_rolling(df: pd.DataFrame, window: int,
                    pin_a: float, pin_b: float, pin_min_pts: float,
                    wall_weight: float = 1.5) -> pd.DataFrame:
    df = df.sort_values("timestamp").copy()

    # Deltas (current - previous)
    df["delta_total_net_gex"] = df["total_net_gex"].diff()
    df["delta_zgamma"] = df["zgamma"].diff()
    df["delta_ramp"] = df["ramp"].diff()

    # Rolling means/std (window)
    df["avg_net_gex_window"] = df["total_net_gex"].rolling(window, min_periods=1).mean()
    df["avg_compression_window"] = df["compression_score"].rolling(window, min_periods=1).mean()
    df["avg_ramp_window"] = df["ramp"].rolling(window, min_periods=1).mean()
    df["net_gex_vol_window"] = df["total_net_gex"].rolling(window, min_periods=2).std()

    # Percentile ranks (window-based) for regime classifier
    abs_net_norm = df.get("total_net_gex_norm", (df["total_net_gex"] / df["spot"].replace(0, np.nan))).abs()
    abs_ramp = df["ramp"].abs()
    df["rank_abs_net"] = _rolling_percentile_of_last(abs_net_norm, window)
    df["rank_abs_ramp"] = _rolling_percentile_of_last(abs_ramp, window)

    # Regime score and pin band
    df["regime_score"] = 0.5 * df["rank_abs_net"].fillna(0) + 0.5 * df["rank_abs_ramp"].fillna(0)
    df["pin_band_pts"] = (pin_a - pin_b * df["rank_abs_net"].fillna(0)).clip(lower=pin_min_pts)
    df["wall_weight"] = float(wall_weight)

    # Dual-anchor selection per spec
    if "dist_to_zgamma_pts" not in df.columns:
        df["dist_to_zgamma_pts"] = (df["spot"] - df["zgamma"]).abs()
    if "dist_to_nearest_wall_pts" not in df.columns:
        if "nearest_wall_strike" in df.columns:
            df["dist_to_nearest_wall_pts"] = (df["spot"] - df["nearest_wall_strike"]).abs()
        else:
            df["dist_to_nearest_wall_pts"] = np.nan
    norm_wall = df["dist_to_nearest_wall_pts"].astype(float) / df["wall_weight"].astype(float)
    dz = df["dist_to_zgamma_pts"].astype(float)
    use_zgamma = dz <= norm_wall
    zg = df["zgamma"].astype(float)
    nws = df.get("nearest_wall_strike", pd.Series([np.nan] * len(df))).astype(float)
    df["pin_anchor"] = np.where(use_zgamma.values, zg.values, nws.values)
    df["pin_anchor_type"] = np.where(use_zgamma.values, 'zgamma', 'wall')
    df["pin_anchor_dist_pts"] = np.where(use_zgamma.values, dz.values, df["dist_to_nearest_wall_pts"].astype(float).values)
    df["in_pin_band"] = (df["pin_anchor_dist_pts"].astype(float) <= df["pin_band_pts"].astype(float))

    return df


def primary_regime_classifier(df: pd.DataFrame,
                              expansion_score_max: float,
                              expansion_ramp_max: float,
                              window: int) -> pd.Series:
    labels = []
    # Compression rule
    comp_mask = df["in_pin_band"].fillna(False) & (df["rank_abs_net"].fillna(0) >= 0.6) & (df["rank_abs_ramp"].fillna(0) >= 0.6)

    # Expansion rule base condition per-row
    prev_total = df["total_net_gex"].shift(window)
    pct_drop = (df["total_net_gex"] - prev_total) / prev_total.abs()
    pct_drop = pct_drop.fillna(0.0)
    dzg = df["delta_zgamma"].abs().fillna(0.0)
    expansion_row = (df["compression_score"].fillna(100.0) < expansion_score_max) & (df["ramp"].fillna(float("inf")) < expansion_ramp_max) & ((pct_drop <= -0.20) | (dzg >= 0.3))
    # Require consecutive >=2
    consec2 = []
    for i in range(len(df)):
        seq = expansion_row.iloc[max(0, i - 1): i + 1]
        consec2.append(bool(len(seq) == 2 and seq.all()))
    expansion_mask = pd.Series(consec2, index=df.index)

    # Precedence: compression > expansion > neutral
    for i in range(len(df)):
        if comp_mask.iloc[i]:
            labels.append("compression")
        elif expansion_mask.iloc[i]:
            labels.append("expansion")
        else:
            labels.append("neutral")
    return pd.Series(labels, index=df.index)


def classify_with_reasons(df: pd.DataFrame,
                          compression_enter: float = 0.60,
                          compression_exit: float = 0.56,
                          expansion_score_max: float = 58.0,
                          expansion_ramp_max: float = 70.0,
                          window: int = 4) -> pd.DataFrame:
    labels = []
    reasons = []
    prev_label = None

    prev_total = df["total_net_gex"].shift(window)
    pct_drop = (df["total_net_gex"] - prev_total) / prev_total.abs()
    pct_drop = pct_drop.fillna(0.0)
    dzg = df["delta_zgamma"].abs().fillna(0.0)
    expansion_row = (df["compression_score"].fillna(100.0) < expansion_score_max) & \
                    (df["ramp"].fillna(float("inf")) < expansion_ramp_max) & \
                    ((pct_drop <= -0.20) | (dzg >= 0.3))

    for i in range(len(df)):
        seq = expansion_row.iloc[max(0, i - 1): i + 1]
        expansion_ok = bool(len(seq) == 2 and seq.all())
        rs = float(df["regime_score"].iloc[i]) if not pd.isna(df["regime_score"].iloc[i]) else 0.0
        in_pin = bool(df["in_pin_band"].iloc[i]) if not pd.isna(df["in_pin_band"].iloc[i]) else False

        if (in_pin and rs >= compression_enter) or (prev_label == "compression" and rs >= compression_exit):
            label = "compression"
            reason = "in_pin & score>=enter" if (in_pin and rs >= compression_enter) else "prev=comp & score>=exit"
        elif expansion_ok:
            label = "expansion"
            reason = "comp<58 & ramp<70 & (drop<=-0.20 or |dZg|>=0.3) x2"
        else:
            label = "neutral"
            reason = "default"

        labels.append(label)
        reasons.append(reason)
        prev_label = label

    out = pd.DataFrame({
        "primary_regime": labels,
        "why_primary_regime": reasons
    }, index=df.index)

    out["inputs_used"] = (
        "score=" + df["regime_score"].round(2).astype(str) +
        ", in_pin=" + df["in_pin_band"].astype(str) +
        ", comp=" + df["compression_score"].round(1).astype(str) +
        ", ramp=" + df["ramp"].round(1).astype(str) +
        ", dZg=" + df["delta_zgamma"].round(3).astype(str)
    )

    return out

def compute_tags_and_gate(df: pd.DataFrame,
                          flip_strike_dist: float,
                          flip_consec: int,
                          wall_shift_strikes: float,
                          window: int,
                          compression_max: float,
                          ramp_max: float,
                          zgamma_min_drift: float) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    # flip_risk tag (new rule: dist <= 0.75 and ramp < 90 for >=2)
    dist = df.get("dist_to_zgamma_pts", (df["spot"] - df["zgamma"]).abs())
    flip_ok = (dist <= flip_strike_dist) & (df["ramp"].fillna(float("inf")) < 90.0)
    flip_tag = []
    for i in range(len(df)):
        seq = flip_ok.iloc[max(0, i - flip_consec + 1): i + 1]
        flip_tag.append(bool(len(seq) == flip_consec and seq.all()))
    out["flip_risk"] = flip_tag

    # wall_shift tag
    if "nearest_wall_strike" in df.columns:
        shift = (df["nearest_wall_strike"] - df["nearest_wall_strike"].shift(1)).abs()
        out["nearest_wall_shift"] = shift
        out["wall_shift"] = shift.rolling(window, min_periods=2).max().fillna(0).ge(wall_shift_strikes)
    else:
        out["nearest_wall_shift"] = 0.0
        out["wall_shift"] = False

    # anomaly tag
    anomaly = df["ramp"].isna()
    if "zgamma_confidence" in df.columns:
        anomaly = anomaly | (df["zgamma_confidence"].astype(str).str.lower() == "low")
    if "ramp_r2" in df.columns:
        anomaly = anomaly | (df["ramp_r2"].fillna(1.0) < 0.3)
    out["anomaly"] = anomaly

    # breakout gate over last 2 rows
    comp_ok = df["compression_score"] < compression_max
    ramp_ok = df["ramp"].fillna(float("inf")) < ramp_max
    net_avg = df["avg_net_gex_window"]
    net_avg_falling = net_avg.diff().fillna(0.0) < 0
    zg_drift = df["zgamma"].diff().abs().fillna(0.0) >= zgamma_min_drift
    pin_band_pts = df.get("pin_band_pts", pd.Series([1.0] * len(df)))
    in_pin = (df["spot"] - df["zgamma"]).abs() <= pin_band_pts
    near_wall = (df.get("dist_to_nearest_wall_pts", pd.Series([float("inf")] * len(df))) <= 0.5)
    crossed_nearest_wall = (df.get("nearest_wall_shift", pd.Series([0.0] * len(df))).abs() >= 0.5)

    gate_seq = comp_ok & ramp_ok & (df["delta_total_net_gex"].fillna(0.0) < 0) & net_avg_falling & (~in_pin) & (near_wall | crossed_nearest_wall)
    # require last 2 rows all true
    gate = []
    for i in range(len(df)):
        seq = gate_seq.iloc[max(0, i - 1): i + 1]
        gate.append(bool(len(seq) == 2 and seq.all()))
    out["breakout_ok"] = gate
    out["crossed_nearest_wall"] = crossed_nearest_wall

    # Extra label: range_break (in_pin_band == false) for >=2 consecutive snapshots AND ramp > 0
    rb_mask = (~df["in_pin_band"].fillna(False)) & (df["ramp"].fillna(-1) > 0)
    rb_consec2 = []
    for i in range(len(df)):
        seq = rb_mask.iloc[max(0, i - 1): i + 1]
        rb_consec2.append(bool(len(seq) == 2 and seq.all()))
    out["range_break"] = rb_consec2

    # Extra label: shelf_pin (in_pin_band AND anchor is wall AND compression_score>=60 or regime_score>=0.6)
    shelf_mask = (df["in_pin_band"].fillna(False)) & (df.get("pin_anchor_type", pd.Series(['']*len(df))) == 'wall') & \
                 ((df["compression_score"].fillna(0) >= 60.0) | (df["regime_score"].fillna(0) >= 0.6))
    out["shelf_pin"] = shelf_mask
    return out


def derive_regimes_for_day(ticker: str,
                           yyyymmdd: str,
                           window: int,
                           compression_thresh: float,
                           compression_consec: int,
                           expansion_drop_pct: float,
                           flip_strike_dist: float,
                           flip_consec: int,
                           wall_shift_strikes: float,
                           latest_only: bool,
                           full: bool,
                           input_file: str = None,
                           output_dir: str = None,
                           compression_max: float = 58.0,
                           ramp_max: float = 70.0,
                           expansion_score_max: float = 58.0,
                           expansion_ramp_max: float = 70.0,
                           compression_enter: float = 0.60,
                           compression_exit: float = 0.56,
                           zgamma_min_drift: float = 0.3):
    month = yyyymmdd[:6]
    if input_file:
        metrics_path = Path(input_file)
    else:
        metrics_path = BASE_DIR / month / "analysis" / f"{ticker.upper()}_GEX_{yyyymmdd}_metrics.csv"
    if not metrics_path.exists():
        print(f"Missing metrics file: {metrics_path}")
        return None, None

    df = pd.read_csv(metrics_path)
    # Normalize types
    df["timestamp"] = df["timestamp"].astype(str)
    # Ensure required base fields exist
    needed = ["timestamp", "spot", "total_net_gex", "zgamma", "ramp", "compression_score"]
    for col in needed:
        if col not in df.columns:
            raise ValueError(f"Missing column in metrics CSV: {col}")

    # Compute rolling stats, ranks, regime_score and pin band (a=2.0, b=1.0, min=0.5)
    dfr = compute_rolling(df, window, pin_a=2.0, pin_b=1.0, pin_min_pts=0.5, wall_weight=1.5)

    # Primary regime with reasons (hysteresis)
    pr = classify_with_reasons(dfr, compression_enter=compression_enter, compression_exit=compression_exit,
                               expansion_score_max=expansion_score_max, expansion_ramp_max=expansion_ramp_max, window=window)
    dfr = pd.concat([dfr, pr], axis=1)

    tags_df = compute_tags_and_gate(
        dfr,
        flip_strike_dist=flip_strike_dist,
        flip_consec=flip_consec,
        wall_shift_strikes=wall_shift_strikes,
        window=window,
        compression_max=compression_max,
        ramp_max=ramp_max,
        zgamma_min_drift=zgamma_min_drift
    )
    dfr = pd.concat([dfr, tags_df], axis=1)

    # Select outputs
    out_cols = [
        "timestamp", "spot", "total_net_gex", "zgamma", "ramp", "compression_score",
        "delta_total_net_gex", "delta_zgamma", "delta_ramp",
        "avg_net_gex_window", "avg_compression_window", "avg_ramp_window", "net_gex_vol_window",
        "dist_to_zgamma_pts", "dist_to_nearest_wall_pts", "wall_weight",
        "pin_anchor", "pin_anchor_type", "pin_anchor_dist_pts", "pin_band_pts", "in_pin_band", "regime_score",
        "primary_regime", "why_primary_regime", "inputs_used",
        "flip_risk", "wall_shift", "anomaly", "breakout_ok", "crossed_nearest_wall", "range_break", "shelf_pin"
    ]
    out = dfr[out_cols].copy()

    if output_dir:
        analysis_dir = Path(output_dir)
        regimes_path = analysis_dir / f"{ticker.upper()}_GEX_{yyyymmdd}_regimes.csv"
    else:
        analysis_dir = BASE_DIR / month / "analysis"
        regimes_path = analysis_dir / f"{ticker.upper()}_GEX_{yyyymmdd}_regimes.csv"

    # Determine target timestamps
    all_ts = out["timestamp"].tolist()
    if latest_only:
        target_ts = [all_ts[-1]] if all_ts else []
    elif full:
        target_ts = all_ts
    else:
        if regimes_path.exists() and regimes_path.stat().st_size > 0:
            try:
                existing = pd.read_csv(regimes_path)
                existing_ts = set(existing["timestamp"].astype(str).tolist()) if "timestamp" in existing.columns else set()
            except EmptyDataError:
                existing_ts = set()
        else:
            existing_ts = set()
        target_ts = [ts for ts in all_ts if ts not in existing_ts]

    out = out[out["timestamp"].isin(target_ts)]
    return out, regimes_path


def main():
    parser = argparse.ArgumentParser(description="Compute rolling GEX regimes from per-snapshot metrics")
    parser.add_argument("--ticker", default="SPY")
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    parser.add_argument("--window", type=int, default=4, help="Rolling window length (snapshots)")
    parser.add_argument("--compression_thresh", type=float, default=60.0)
    parser.add_argument("--compression_consec", type=int, default=3)
    parser.add_argument("--expansion_drop_pct", type=float, default=0.2, help="20% = 0.2")
    parser.add_argument("--flip_strike_dist", type=float, default=0.75)
    parser.add_argument("--flip_consec", type=int, default=2)
    parser.add_argument("--wall_shift_strikes", type=float, default=1.0)
    # Threshold tuning parameters - OPTIMIZED VALUES FROM focused_combo_0025
    parser.add_argument("--compression_max", type=float, default=60.0, help="Max compression score for breakout_ok gate")
    parser.add_argument("--ramp_max", type=float, default=25.0, help="Max ramp for breakout_ok gate")
    parser.add_argument("--expansion_score_max", type=float, default=40.0, help="Max compression score for expansion regime")
    parser.add_argument("--expansion_ramp_max", type=float, default=75.0, help="Max ramp for expansion regime")
    parser.add_argument("--compression_enter", type=float, default=65.0, help="Compression enter threshold")
    parser.add_argument("--compression_exit", type=float, default=58.0, help="Compression exit threshold")
    parser.add_argument("--zgamma_min_drift", type=float, default=0.1, help="Min zgamma drift for breakout_ok")
    parser.add_argument("--csv", default='N', help="Write regimes CSV (Y/N)")
    parser.add_argument("--quiet", action="store_true", help="Suppress console output")
    parser.add_argument("--latest", default='N', help="Compute only latest snapshot (Y/N)")
    parser.add_argument("--full", default='N', help="Recompute entire day (Y/N). Overrides --latest")
    parser.add_argument("--input_file", default=None, help="Optional explicit input metrics CSV path")
    parser.add_argument("--output", default=None, help="Optional output directory for regimes CSVs")
    args = parser.parse_args()

    latest_only = str(args.latest).strip().upper().startswith('Y')
    full = str(args.full).strip().upper().startswith('Y')
    if full:
        latest_only = False

    out, regimes_path = derive_regimes_for_day(
        args.ticker.upper(), args.date, args.window,
        args.compression_thresh, args.compression_consec,
        args.expansion_drop_pct, args.flip_strike_dist, args.flip_consec,
        args.wall_shift_strikes,
        latest_only, full,
        input_file=args.input_file, output_dir=args.output,
        compression_max=args.compression_max,
        ramp_max=args.ramp_max,
        expansion_score_max=args.expansion_score_max,
        expansion_ramp_max=args.expansion_ramp_max,
        compression_enter=args.compression_enter,
        compression_exit=args.compression_exit,
        zgamma_min_drift=args.zgamma_min_drift
    )
    if out is None:
        return

    write_csv = str(args.csv).strip().upper().startswith('Y')
    if write_csv:
        if out.empty:
            if not args.quiet:
                print("No new regime rows to write.")
            return
        regimes_path.parent.mkdir(parents=True, exist_ok=True)
        if full or not regimes_path.exists():
            out.to_csv(regimes_path, index=False)
        else:
            if regimes_path.exists() and regimes_path.stat().st_size > 0:
                try:
                    existing = pd.read_csv(regimes_path)
                except EmptyDataError:
                    existing = pd.DataFrame()
            else:
                existing = pd.DataFrame()
            combined = pd.concat([existing, out], ignore_index=True)
            if "timestamp" in combined.columns:
                combined["timestamp"] = combined["timestamp"].astype(str)
                combined = combined.drop_duplicates(subset=["timestamp"], keep="last")
            combined = combined.sort_values("timestamp")
            combined.to_csv(regimes_path, index=False)
        if not args.quiet:
            print(f"✅ Wrote {len(out)} new rows → {regimes_path}")
    else:
        if not args.quiet:
            print(f"Symbol: {args.ticker.upper()}  Date: {args.date}  Rows: {len(out)}")
            if out.empty:
                print("(no rows)")
            else:
                print("timestamp,spot,total_net_gex,avg_compression_window,primary_regime")
                for _, r in out.iterrows():
                    print(f"{r['timestamp']},{r['spot']},{r['total_net_gex']},{round(r['avg_compression_window'],2)},{r['primary_regime']}")


if __name__ == "__main__":
    main()


