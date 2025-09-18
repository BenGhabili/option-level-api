#!/usr/bin/env python3
"""
FOCUSED THRESHOLD SWEEP - Smart parameter ranges around validated optimal values.
No wasteful extreme values - only practical, tradeable ranges.
"""

import subprocess
from pathlib import Path
import itertools
import time

def run_focused_sweep():
    print("🎯 FOCUSED THRESHOLD SWEEP")
    print("="*60)
    print("Smart parameter ranges around validated optimal values")
    print("No wasteful extremes - only practical trading ranges")
    print()
    
    # Paths
    metrics_dir = Path("./backtest_data/metrics")
    regimes_base = Path("./focused_sweep")
    python_exe = Path("./.venv/Scripts/python.exe")
    
    # Get all metrics files
    metrics_files = list(metrics_dir.glob("*_metrics.csv"))
    if not metrics_files:
        print("❌ No metrics files found")
        return False
    
    print(f"📊 Found {len(metrics_files)} metrics files to process")
    
    # OPTIMIZED parameter ranges - weakest values removed based on validation
    param_ranges = {
        'compression_max': [70.0, 80.0, 90.0],                # Remove 60.0 (weakest: 3 signals)
        'ramp_max': [50.0, 70.0, 100.0],                      # Remove 150.0 (too loose)
        'flip_strike_dist': [1.0, 2.0, 4.0],                  # Remove 6.0 (too far)
        'compression_enter': [0.35, 0.50],                    # Remove 0.25 (too low)
        'compression_exit': [0.20, 0.30],                     # Remove 0.45 (too high)
        'zgamma_min_drift': [0.0, 0.5]                        # Remove 2.0 (too high)
    }
    
    # Calculate total combinations
    total_combinations = 1
    for param, values in param_ranges.items():
        total_combinations *= len(values)
    
    print(f"📈 FOCUSED parameter ranges:")
    for param, values in param_ranges.items():
        print(f"   {param}: {values}")
    
    print(f"\n🎯 Total combinations: {total_combinations}")
    print(f"📁 Total regime files: {total_combinations * len(metrics_files)}")
    
    # Estimate time (should be much faster)
    estimated_hours = total_combinations * len(metrics_files) * 2 / 3600
    print(f"⏱️  Estimated time: {estimated_hours:.1f} hours")
    
    # Confirm
    print(f"\n✅ SMART APPROACH:")
    print("   - Focused around validated optimal ranges")
    print("   - No wasteful extreme values")  
    print("   - All combinations should produce meaningful signals")
    print("   - Much faster than the 6,400 combo approach")
    
    print(f"\nContinue? (y/N): ", end="")
    response = input().strip().lower()
    
    if response != 'y':
        print("❌ Aborted by user")
        return False
    
    # Create base directory
    regimes_base.mkdir(exist_ok=True)
    
    # Generate all parameter combinations
    param_names = list(param_ranges.keys())
    param_values_lists = [param_ranges[name] for name in param_names]
    all_combinations = list(itertools.product(*param_values_lists))
    
    print(f"\n🚀 Starting focused sweep...")
    print(f"Processing {len(all_combinations)} combinations × {len(metrics_files)} files")
    print("="*60)
    
    start_time = time.time()
    successful_combos = 0
    failed_combos = 0
    
    for combo_idx, param_combo in enumerate(all_combinations, 1):
        # Create parameter dictionary
        params = dict(zip(param_names, param_combo))
        
        # Create combo directory name
        combo_name = f"focused_combo_{combo_idx:04d}"
        combo_dir = regimes_base / combo_name
        combo_dir.mkdir(exist_ok=True)
        
        # Progress reporting
        elapsed = time.time() - start_time
        avg_time = elapsed / combo_idx if combo_idx > 0 else 0
        remaining_time = (len(all_combinations) - combo_idx) * avg_time
        progress_pct = (combo_idx / len(all_combinations)) * 100
        
        print(f"[{combo_idx:4}/{len(all_combinations)}] ({progress_pct:5.1f}%) {combo_name} | ETA: {remaining_time/60:.1f}m")
        print(f"   comp_max={params['compression_max']:5.1f}, ramp_max={params['ramp_max']:5.1f}, flip_dist={params['flip_strike_dist']:3.1f}")
        
        # Process all metrics files for this combination
        combo_success = True
        files_processed = 0
        
        for metrics_file in metrics_files:
            # Extract ticker and date
            filename = metrics_file.name
            if '_metrics.csv' in filename:
                parts = filename.replace('_metrics.csv', '').split('_')
                if len(parts) >= 3:
                    ticker = parts[0]
                    date = parts[2]
                else:
                    continue
            else:
                continue
            
            # Build command
            cmd = [
                str(python_exe), "-u", "./scripts/rolling_gex_regimes.py",
                "--ticker", ticker,
                "--date", date,
                "--window", "4",
                "--full", "Y",
                "--csv", "Y",
                "--quiet",
                "--input_file", str(metrics_file),
                "--output", str(combo_dir),
                "--compression_max", str(params['compression_max']),
                "--ramp_max", str(params['ramp_max']),
                "--flip_strike_dist", str(params['flip_strike_dist']),
                "--compression_enter", str(params['compression_enter']),
                "--compression_exit", str(params['compression_exit']),
                "--zgamma_min_drift", str(params['zgamma_min_drift'])
            ]
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    files_processed += 1
                else:
                    combo_success = False
                    break
            except:
                combo_success = False
                break
        
        if combo_success:
            successful_combos += 1
            print(f"   ✅ Success: {files_processed}/{len(metrics_files)} files")
        else:
            failed_combos += 1
            print(f"   ❌ Failed: {files_processed}/{len(metrics_files)} files processed")
        
        # Progress checkpoint every 100 combos
        if combo_idx % 100 == 0:
            elapsed_hours = elapsed / 3600
            print(f"\n📊 CHECKPOINT:")
            print(f"   Processed: {combo_idx}/{len(all_combinations)} combos")
            print(f"   Success: {successful_combos}, Failed: {failed_combos}")
            print(f"   Time elapsed: {elapsed_hours:.1f}h, Remaining: {remaining_time/3600:.1f}h")
            print("-" * 60)
    
    # Final report
    total_elapsed = time.time() - start_time
    print(f"\n" + "="*60)
    print(f"🎉 FOCUSED SWEEP COMPLETE!")
    print(f"⏱️  Total time: {total_elapsed/3600:.1f} hours")
    print(f"✅ Successful combos: {successful_combos}/{len(all_combinations)}")
    print(f"❌ Failed combos: {failed_combos}")
    print(f"📁 Results saved to: {regimes_base}")
    print("="*60)
    
    return successful_combos > 0

if __name__ == "__main__":
    success = run_focused_sweep()
    if success:
        print(f"\n🎯 Ready for backtesting with FOCUSED threshold combinations!")
    else:
        print(f"\n💥 Focused sweep failed - check errors above")
