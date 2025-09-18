import argparse
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def parse_args():
    p = argparse.ArgumentParser(description="Backtest regimes and signals with walk-forward splits")
    p.add_argument("--metrics_dir", default=str(Path(".") / "backtest_data" / "metrics"))
    p.add_argument("--regimes_dir", default=str(Path(".") / "backtest_data" / "regimes"))
    p.add_argument("--out_dir", default=str(Path(".") / "backtest_data" / "backtest_results"))
    p.add_argument("--symbols", nargs="*", default=["SPY"], help="Symbols to include (prefix of filenames)")
    p.add_argument("--bar_minutes", type=int, default=5)
    p.add_argument("--H_minutes", nargs="*", type=int, default=[30, 60])
    p.add_argument("--K_pts", nargs="*", type=float, default=[1.0, 1.5, 2.0])
    p.add_argument("--compression_thresholds", nargs="*", type=float, default=[60, 62, 64])
    p.add_argument("--pin_band_pts", nargs="*", type=float, default=[1.0, 1.25, 1.5])
    p.add_argument("--flip_vol_threshold", type=float, default=0.003, help="stdev threshold over H for flip_realized_vol (fraction)")
    # Threshold tuning for signals (for identifying best params from regimes with different thresholds)
    p.add_argument("--threshold_tag", default="", help="Tag to identify which threshold combination was used in regimes")
    # Breakout v2 controls
    p.add_argument("--use_breakout_v2", default='Y', help="Use v2 breakout labeling (Y/N)")
    p.add_argument("--breakout_confirm_bars", type=int, default=1)
    p.add_argument("--breakout_buffer_pts", type=float, default=0.25)
    return p.parse_args()


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if "timestamp" in df.columns:
        df["timestamp"] = df["timestamp"].astype(str)
    return df


def list_days(regimes_dir: Path, symbols: list[str]) -> list[tuple[str, str, Path, Path]]:
    days = []
    for csv_path in sorted(regimes_dir.glob("*_GEX_????????_regimes.csv")):
        name = csv_path.stem  # e.g., SPY_GEX_20250717_regimes
        sym, _, ymd, _ = name.split("_")
        if symbols and sym not in symbols:
            continue
        metrics_path = csv_path.parent.parent / "metrics" / f"{sym}_GEX_{ymd}_metrics.csv"
        days.append((sym, ymd, metrics_path, csv_path))
    return days


def weekly_key(ymd: str) -> str:
    dt = datetime.strptime(ymd, "%Y%m%d")
    year, week, _ = dt.isocalendar()
    return f"{year}-W{int(week):02d}"


def label_outcomes(regimes: pd.DataFrame,
                   H_minutes: int,
                   K_pts: float,
                   flip_vol_threshold: float,
                   bar_minutes: int,
                   use_breakout_v2: bool,
                   breakout_confirm_bars: int,
                   breakout_buffer_pts: float) -> pd.DataFrame:
    df = regimes.sort_values("timestamp").copy()
    # basic forward windows in bars
    horizon = max(1, int(H_minutes / bar_minutes))
    # Pin anchor must exist; fill forward 1 bar for stability
    df["pin_anchor"] = df.get("pin_anchor", pd.Series([np.nan] * len(df))).astype(float).ffill(limit=1)
    df["pin_band_pts"] = df.get("pin_band_pts", pd.Series([1.0] * len(df))).astype(float)
    df["spot"] = df["spot"].astype(float)

    # breakout labeling
    spot_f = df["spot"].to_numpy()
    pin_t = df["pin_anchor"].to_numpy()
    breakout = []
    pin_success = []
    flip_vol = []
    n = len(df)
    outside = np.abs(spot_f - pin_t) >= (df["pin_band_pts"].to_numpy() + float(breakout_buffer_pts))
    for i in range(n):
        end = min(n, i + 1 + horizon)
        window = spot_f[i:end]
        if use_breakout_v2:
            # Trigger requires outside-band by buffer and optional confirmation bars
            trigger = bool(outside[i])
            if trigger and breakout_confirm_bars > 1:
                jend = min(n, i + breakout_confirm_bars)
                trigger = bool(outside[i:jend].all())
            if trigger:
                # Directional success: move away from spot_i by >= K within horizon
                direction = 1.0 if (spot_f[i] - pin_t[i]) > 0 else -1.0
                if window.size > 0:
                    moves = (window - spot_f[i]) * direction
                    succ = bool(np.nanmax(moves) >= K_pts)
                else:
                    succ = False
                breakout.append(succ)
            else:
                breakout.append(False)
        else:
            # Legacy: max abs deviation from pin anchor within horizon
            max_dev = float(np.nanmax(np.abs(window - pin_t[i]))) if window.size > 0 else np.nan
            breakout.append(bool(max_dev >= K_pts))
        # pin success at window end
        if end - 1 < n:
            close_end = spot_f[end - 1]
            pin_success.append(bool(abs(close_end - pin_t[i]) <= float(df["pin_band_pts"].iloc[i])))
        else:
            pin_success.append(False)
        # flip vol = stdev of returns over horizon >= threshold
        if end - i >= 2:
            arr = window.astype(float)
            rets = np.diff(arr) / np.clip(arr[:-1], 1e-9, None)
            flip_vol.append(bool(np.nanstd(rets) >= flip_vol_threshold))
        else:
            flip_vol.append(False)
    out = pd.DataFrame({
        "timestamp": df["timestamp"],
        "breakout": breakout,
        "pin_success": pin_success,
        "flip_realized_vol": flip_vol,
    })
    return out


def evaluate_signals(regimes: pd.DataFrame, labels: pd.DataFrame, threshold_comp: float) -> tuple[dict, dict]:
    df = regimes.merge(labels, on="timestamp", how="inner")
    # Signals
    sig_breakout = df["breakout_ok"].astype(bool)
    sig_flip = df["flip_risk"].astype(bool)
    sig_pin = (df["compression_score"].astype(float) >= threshold_comp) & df["in_pin_band"].astype(bool)

    def prf(y_true: pd.Series, y_pred: pd.Series) -> tuple[float, float, float, float]:
        t = y_true.astype(bool).to_numpy()
        p = y_pred.astype(bool).to_numpy()
        tp = int(np.sum(p & t))
        fp = int(np.sum(p & ~t))
        fn = int(np.sum(~p & t))
        tn = int(np.sum(~p & ~t))
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2*prec*rec/(prec+rec) if (prec+rec) else 0.0
        mcc_d = (tp+fp)*(tp+fn)*(tn+fp)*(tn+fn)
        mcc = ((tp*tn - fp*fn) / np.sqrt(mcc_d)) if mcc_d else 0.0
        return prec, rec, f1, mcc

    br = prf(df["breakout"], sig_breakout)
    fr = prf(df["flip_realized_vol"], sig_flip)
    pr = prf(df["pin_success"], sig_pin)

    # Append counts for scoreboard (using breakout by default)
    y_true = df["breakout"].astype(bool).to_numpy()
    y_pred = sig_breakout.astype(bool).to_numpy()
    tp = int(np.sum(y_true & y_pred))
    fp = int(np.sum(~y_true & y_pred))
    fn = int(np.sum(y_true & ~y_pred))
    tn = int(np.sum(~y_true & ~y_pred))
    support_bars = int(len(df))
    positives = int(np.sum(y_true))
    predicted_positives = int(np.sum(y_pred))
    base_rate = (positives / support_bars) if support_bars else 0.0

    metrics = {
        "breakout": {"precision": br[0], "recall": br[1], "F1": br[2], "MCC": br[3]},
        "flip_realized_vol": {"precision": fr[0], "recall": fr[1], "F1": fr[2], "MCC": fr[3]},
        "pin_success": {"precision": pr[0], "recall": pr[1], "F1": pr[2], "MCC": pr[3]},
    }
    counts = {
        "TP": tp,
        "FP": fp,
        "FN": fn,
        "TN": tn,
        "predicted_positives": predicted_positives,
        "positives": positives,
        "base_rate": base_rate,
        "support_bars": support_bars,
    }
    return metrics, counts


def main():
    a = parse_args()
    metrics_dir = Path(a.metrics_dir)
    regimes_dir = Path(a.regimes_dir)
    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Collect day list
    days = list_days(regimes_dir, a.symbols)
    if not days:
        print("No regimes found to backtest.")
        return

    # Group by weekly fold
    folds: dict[str, list[tuple[str, str, Path, Path]]] = {}
    for sym, ymd, mp, rp in days:
        folds.setdefault(weekly_key(ymd), []).append((sym, ymd, mp, rp))

    # Walk-forward: for each fold k, validate on k, test on k+1 (no training stage here; just reporting)
    fold_keys = sorted(folds.keys())
    results_rows = []
    for i, fk in enumerate(fold_keys):
        val_days = folds[fk]
        test_days = folds[fold_keys[i+1]] if i+1 < len(fold_keys) else []
        for split_name, split_days in [("val", val_days), ("test", test_days)]:
            if not split_days:
                continue
            # Concatenate regimes of split
            regimes_list = []
            for sym, ymd, mp, rp in split_days:
                r = _read_csv(rp)
                regimes_list.append(r)
            R = pd.concat(regimes_list, ignore_index=True) if regimes_list else pd.DataFrame()
            if R.empty:
                continue
            # For each H,K and compression, pin_band setting compute labels and metrics
            for H in a.H_minutes:
                for K in a.K_pts:
                    L = label_outcomes(
                        R,
                        H_minutes=H,
                        K_pts=K,
                        flip_vol_threshold=a.flip_vol_threshold,
                        bar_minutes=a.bar_minutes,
                        use_breakout_v2=str(a.use_breakout_v2).strip().upper().startswith('Y'),
                        breakout_confirm_bars=int(a.breakout_confirm_bars),
                        breakout_buffer_pts=float(a.breakout_buffer_pts),
                    )
                    for ct in a.compression_thresholds:
                        metrics_map, counts_map = evaluate_signals(R, L, threshold_comp=ct)
                        results_rows.append({
                            "fold": fk,
                            "split": split_name,
                            "H": H,
                            "K": K,
                            "compression": ct,
                            "threshold_tag": a.threshold_tag,
                            **{f"{k}_{m}": v[m] for k, v in metrics_map.items() for m in v},
                            **counts_map,
                        })

    if results_rows:
        dfres = pd.DataFrame(results_rows)
        dfres.to_csv(out_dir / "scoreboard.csv", index=False)
        print(f"Wrote scoreboard → {out_dir / 'scoreboard.csv'}")
    else:
        print("No results to write.")


if __name__ == "__main__":
    main()


