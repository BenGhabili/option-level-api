#!/usr/bin/env python3
"""
Monitor the FOCUSED sweep progress and validate quality.
"""

import pandas as pd
from pathlib import Path
import hashlib
import time
import random

def monitor_focused_sweep():
    print("📊 FOCUSED SWEEP MONITOR")
    print("="*50)
    
    sweep_dir = Path("./focused_sweep")
    if not sweep_dir.exists():
        print("❌ Focused sweep directory not found")
        return
    
    # Get all combo folders
    combo_folders = [d for d in sweep_dir.iterdir() if d.is_dir() and d.name.startswith("focused_combo_")]
    combo_folders.sort()
    
    if not combo_folders:
        print("❌ No focused combo folders found")
        return
    
    print(f"📁 Found {len(combo_folders)} focused combo folders")
    
    # Expected metrics files
    metrics_dir = Path("./backtest_data/metrics")
    expected_files = len(list(metrics_dir.glob("*_metrics.csv")))
    
    print(f"📄 Expected {expected_files} regime files per combo")
    print()
    
    # Progress analysis
    print("🔍 PROGRESS ANALYSIS:")
    print("-" * 30)
    
    completed_combos = 0
    partial_combos = 0
    empty_combos = 0
    total_regime_files = 0
    
    for combo_dir in combo_folders:
        regime_files = list(combo_dir.glob("*_regimes.csv"))
        file_count = len(regime_files)
        total_regime_files += file_count
        
        if file_count == expected_files:
            completed_combos += 1
        elif file_count > 0:
            partial_combos += 1
        else:
            empty_combos += 1
    
    total_combos = len(combo_folders)
    completion_rate = (completed_combos / total_combos) * 100 if total_combos > 0 else 0
    
    print(f"✅ Completed combos: {completed_combos}/{total_combos} ({completion_rate:.1f}%)")
    print(f"🔄 Partial combos: {partial_combos}")
    print(f"❌ Empty combos: {empty_combos}")
    print(f"📊 Total regime files: {total_regime_files:,}")
    print(f"🎯 Expected total: {total_combos * expected_files:,}")
    
    # Quality validation on random sample
    print(f"\n🧪 QUALITY VALIDATION:")
    print("-" * 25)
    
    if completed_combos >= 3:
        # Test 3 random completed combos
        completed_combo_dirs = [d for d in combo_folders if len(list(d.glob("*_regimes.csv"))) == expected_files]
        test_combos = random.sample(completed_combo_dirs, min(3, len(completed_combo_dirs)))
        
        print(f"Testing {len(test_combos)} random completed combos for quality...")
        
        # Test the same regime file across different combos
        test_file = "SPY_GEX_20250717_regimes.csv"
        
        test_results = {}
        for combo_dir in test_combos:
            combo_name = combo_dir.name
            regime_file = combo_dir / test_file
            
            if regime_file.exists():
                try:
                    df = pd.read_csv(regime_file)
                    
                    # Key metrics
                    breakout_sum = df['breakout_ok'].sum() if 'breakout_ok' in df.columns else 0
                    flip_sum = df['flip_risk'].sum() if 'flip_risk' in df.columns else 0
                    
                    # File hash
                    with open(regime_file, 'rb') as f:
                        file_hash = hashlib.md5(f.read()).hexdigest()
                    
                    test_results[combo_name] = {
                        'breakout_ok': breakout_sum,
                        'flip_risk': flip_sum,
                        'hash': file_hash[:8],
                        'rows': len(df)
                    }
                    
                    print(f"  {combo_name}: breakout={breakout_sum:3}, flip={flip_sum:3}, hash={file_hash[:8]}")
                    
                except Exception as e:
                    print(f"  {combo_name}: ❌ Error: {e}")
        
        # Check for variety
        if len(test_results) >= 2:
            hashes = [r['hash'] for r in test_results.values()]
            breakout_counts = [r['breakout_ok'] for r in test_results.values()]
            flip_counts = [r['flip_risk'] for r in test_results.values()]
            
            unique_hashes = len(set(hashes))
            unique_breakouts = len(set(breakout_counts))
            unique_flips = len(set(flip_counts))
            
            print(f"\n  📈 Variety check:")
            print(f"     Unique file hashes: {unique_hashes}/{len(test_results)}")
            print(f"     Unique breakout counts: {unique_breakouts}")
            print(f"     Unique flip counts: {unique_flips}")
            
            if unique_hashes >= 2 and (unique_breakouts >= 2 or unique_flips >= 2):
                print(f"     ✅ Quality looks EXCELLENT - focused sweep working!")
            else:
                print(f"     ⚠️  Warning - still too similar despite optimization")
    else:
        print("Not enough completed combos for quality testing yet")
    
    # Recent activity check
    print(f"\n⏱️  RECENT ACTIVITY:")
    print("-" * 20)
    
    if combo_folders:
        # Check modification times of recent combos
        recent_combos = combo_folders[-5:] if len(combo_folders) >= 5 else combo_folders
        
        for combo_dir in recent_combos:
            regime_files = list(combo_dir.glob("*_regimes.csv"))
            if regime_files:
                # Get newest file modification time
                newest_file = max(regime_files, key=lambda f: f.stat().st_mtime)
                mod_time = newest_file.stat().st_mtime
                time_ago = time.time() - mod_time
                
                if time_ago < 300:  # 5 minutes
                    status = "🟢 Active"
                elif time_ago < 1800:  # 30 minutes
                    status = "🟡 Recent"
                else:
                    status = "🔴 Old"
                
                print(f"  {combo_dir.name}: {len(regime_files):2} files, {status} ({time_ago/60:.1f}m ago)")
            else:
                print(f"  {combo_dir.name}: No files yet")
    
    # Expected completion estimate
    if total_combos > 0:
        expected_total = 216  # Our target
        print(f"\n🎯 TARGET: {expected_total} total combos")
        if total_combos >= expected_total:
            print("✅ TARGET REACHED!")
        else:
            remaining = expected_total - total_combos
            print(f"🔄 {remaining} combos remaining to reach target")

if __name__ == "__main__":
    monitor_focused_sweep()

