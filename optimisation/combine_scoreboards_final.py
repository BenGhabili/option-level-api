#!/usr/bin/env python3
"""
Combine ALL scoreboard files into one master comparison file.
This analyzes the complete threshold sweep results.
"""

import pandas as pd
import glob
from pathlib import Path

def combine_all_scoreboards():
    # Find all scoreboard files in final_results
    results_dir = Path("./backtest_data/final_results")
    scoreboard_files = list(results_dir.glob("combo_*/scoreboard.csv"))
    
    print(f"🔍 Found {len(scoreboard_files)} final scoreboard files")
    
    if not scoreboard_files:
        print("❌ No scoreboard files found in final_results!")
        print("   Try running: run_scoreboards_robust.bat")
        return
    
    # Read and combine all scoreboards
    all_scoreboards = []
    failed_files = []
    total_files = len(scoreboard_files)
    
    print(f"📊 Processing {total_files} scoreboard files...")
    print("=" * 60)
    
    for i, file_path in enumerate(scoreboard_files, 1):
        combo_name = file_path.parent.name
        progress_pct = (i / total_files) * 100
        
        # Progress display every 50 files or at key milestones
        if i % 50 == 0 or i in [1, 10, 100, 500, 1000] or i == total_files:
            print(f"[{i:4}/{total_files}] ({progress_pct:5.1f}%) Processing {combo_name}...")
        
        try:
            df = pd.read_csv(file_path)
            if not df.empty:
                all_scoreboards.append(df)
            else:
                failed_files.append(f"Empty: {combo_name}")
                print(f"   ⚠️  WARNING: Empty file {combo_name}")
        except Exception as e:
            failed_files.append(f"Error {combo_name}: {e}")
            print(f"   ❌ ERROR: {combo_name} - {e}")
    
    print("=" * 60)
    
    if not all_scoreboards:
        print("❌ No valid scoreboards to combine!")
        return
    
    # Combine all dataframes
    print(f"📊 Combining {len(all_scoreboards)} valid scoreboards...")
    print("🔄 Creating master dataframe...")
    master_df = pd.concat(all_scoreboards, ignore_index=True)
    print(f"✅ Combined into {len(master_df):,} total rows")
    
    # Save master scoreboard
    output_path = Path("./backtest_data/MASTER_SCOREBOARD_FINAL.csv")
    master_df.to_csv(output_path, index=False)
    
    print(f"\n🎯 COMPLETE ANALYSIS!")
    print(f"✅ Combined {len(all_scoreboards)} scoreboards")
    print(f"📈 Total rows: {len(master_df):,}")
    print(f"🏷️  Unique threshold_tags: {master_df['threshold_tag'].nunique()}")
    print(f"💾 Master scoreboard: {output_path}")
    
    if failed_files:
        print(f"⚠️  Failed files: {len(failed_files)}")
        for fail in failed_files[:5]:  # Show first 5
            print(f"     {fail}")
    
    # Comprehensive analysis
    print(f"\n" + "="*60)
    print("📊 COMPREHENSIVE THRESHOLD ANALYSIS")
    print("="*60)
    
    # Best breakout combinations
    breakout_results = master_df[master_df['breakout_F1'] > 0].copy()
    if not breakout_results.empty:
        print(f"\n🚀 TOP 10 BREAKOUT COMBINATIONS (F1 Score):")
        print("-" * 50)
        top_breakout = breakout_results.nlargest(10, 'breakout_F1')[
            ['threshold_tag', 'breakout_precision', 'breakout_recall', 'breakout_F1', 
             'predicted_positives', 'H', 'K']
        ].round(3)
        print(top_breakout.to_string(index=False))
        
        # Best precision
        print(f"\n🎯 TOP 5 BREAKOUT PRECISION:")
        print("-" * 30)
        top_precision = breakout_results.nlargest(5, 'breakout_precision')[
            ['threshold_tag', 'breakout_precision', 'breakout_recall', 'breakout_F1', 'predicted_positives']
        ].round(3)
        print(top_precision.to_string(index=False))
    
    # Best pin combinations  
    pin_results = master_df[master_df['pin_success_F1'] > 0].copy()
    if not pin_results.empty:
        print(f"\n📌 TOP 5 PIN COMBINATIONS (F1 Score):")
        print("-" * 40)
        top_pin = pin_results.nlargest(5, 'pin_success_F1')[
            ['threshold_tag', 'pin_success_precision', 'pin_success_recall', 'pin_success_F1', 'H', 'K']
        ].round(3)
        print(top_pin.to_string(index=False))
    
    # Signal firing analysis
    signal_analysis = master_df.groupby('threshold_tag').agg({
        'predicted_positives': 'mean',
        'breakout_F1': 'max',
        'pin_success_F1': 'max'
    }).round(3)
    
    # Best overall combinations
    signal_analysis['combined_score'] = (signal_analysis['breakout_F1'] + signal_analysis['pin_success_F1']) / 2
    best_overall = signal_analysis.nlargest(10, 'combined_score')
    
    print(f"\n🏆 TOP 10 OVERALL COMBINATIONS (Combined Score):")
    print("-" * 50)
    print(best_overall.to_string())
    
    print(f"\n" + "="*60)
    print("🎉 ANALYSIS COMPLETE!")
    print(f"Your best threshold combination is: {best_overall.index[0]}")
    print("="*60)

if __name__ == "__main__":
    combine_all_scoreboards()
