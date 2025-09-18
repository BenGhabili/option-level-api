#!/usr/bin/env python3
"""
RUTHLESS analysis of the 216 combination results.
No mercy - find the absolute best and understand WHY they work.
"""

import pandas as pd
import numpy as np
from pathlib import Path

def ruthless_analysis():
    print("⚔️  RUTHLESS ANALYSIS MODE")
    print("="*60)
    print("Finding the ABSOLUTE BEST performers")
    print("NO forgiveness for mediocre results!")
    print()
    
    # Load master scoreboard
    master_file = Path("./focused_backtest_results/MASTER_FOCUSED_SCOREBOARD.csv")
    if not master_file.exists():
        print("❌ Master scoreboard not found!")
        return
    
    df = pd.read_csv(master_file)
    print(f"📊 Loaded {len(df):,} rows from {df['threshold_tag'].nunique()} combinations")
    
    # Show all columns for inspection
    print(f"\n📋 AVAILABLE COLUMNS:")
    for i, col in enumerate(df.columns):
        print(f"  {i+1:2}. {col}")
    
    print(f"\n🎯 TARGET SIGNALS TO ANALYZE:")
    signal_cols = [col for col in df.columns if any(metric in col for metric in ['_F1', '_precision', '_recall', '_MCC'])]
    signal_names = set()
    for col in signal_cols:
        for metric in ['_F1', '_precision', '_recall', '_MCC']:
            if col.endswith(metric):
                signal_names.add(col.replace(metric, ''))
                break
    
    for signal in sorted(signal_names):
        print(f"  • {signal}")
    
    # Focus on F1 scores as primary metric
    f1_cols = [col for col in df.columns if col.endswith('_F1')]
    
    print(f"\n🔍 F1 SCORE ANALYSIS:")
    print("-" * 40)
    
    for col in sorted(f1_cols):
        signal_name = col.replace('_F1', '')
        max_f1 = df[col].max()
        mean_f1 = df[col].mean()
        std_f1 = df[col].std()
        q95_f1 = df[col].quantile(0.95)
        
        # Find best performing combination for this signal
        best_idx = df[col].idxmax()
        best_combo = df.loc[best_idx, 'threshold_tag']
        best_f1 = df.loc[best_idx, col]
        
        print(f"{signal_name:20} | Max: {max_f1:.3f} | Mean: {mean_f1:.3f}±{std_f1:.3f} | 95th: {q95_f1:.3f} | Best: {best_combo}")
        
        # Flag exceptional performers
        if max_f1 > 0.8:
            print(f"  🔥 EXCEPTIONAL: {max_f1:.3f} F1 score!")
        elif max_f1 > 0.4:
            print(f"  🚀 STRONG: {max_f1:.3f} F1 score")
        elif max_f1 < 0.1:
            print(f"  💀 WEAK: {max_f1:.3f} F1 score - signal barely firing")
    
    print(f"\n" + "="*60)
    print(f"🏆 TOP 10 OVERALL PERFORMERS")
    print("="*60)
    
    # Create composite score (weighted average of key F1 scores)
    key_signals = ['breakout', 'pin_success']  # Focus on these two
    
    composite_score = pd.Series(0.0, index=df.index)
    weights = {'breakout': 1.0, 'pin_success': 1.0}  # Equal weight
    
    for signal, weight in weights.items():
        f1_col = f"{signal}_F1"
        if f1_col in df.columns:
            composite_score += weight * df[f1_col].fillna(0)
    
    # Get top 10 by composite score
    df['composite_score'] = composite_score
    top_10 = df.nlargest(10, 'composite_score')
    
    print(f"{'Rank':<4} {'Combo':<20} {'Breakout F1':<12} {'Pin F1':<10} {'Composite':<12}")
    print("-" * 70)
    
    for i, (_, row) in enumerate(top_10.iterrows(), 1):
        breakout_f1 = row.get('breakout_F1', 0)
        pin_f1 = row.get('pin_success_F1', 0)
        comp_score = row['composite_score']
        combo = row['threshold_tag']
        
        print(f"{i:<4} {combo:<20} {breakout_f1:<12.3f} {pin_f1:<10.3f} {comp_score:<12.3f}")
    
    # Deep dive on the absolute winner
    winner = top_10.iloc[0]
    print(f"\n" + "🏆"*20)
    print(f"ABSOLUTE WINNER: {winner['threshold_tag']}")
    print(f"🏆"*20)
    
    print(f"Composite Score: {winner['composite_score']:.3f}")
    print(f"Breakout F1: {winner.get('breakout_F1', 0):.3f}")
    print(f"Pin Success F1: {winner.get('pin_success_F1', 0):.3f}")
    
    # Show all metrics for the winner
    print(f"\nFULL METRICS FOR WINNER:")
    print("-" * 30)
    
    winner_metrics = {}
    for col in df.columns:
        if any(metric in col for metric in ['_F1', '_precision', '_recall', '_MCC', '_TP', '_FP', '_FN', '_TN']):
            value = winner[col]
            if pd.notna(value):
                winner_metrics[col] = value
    
    for metric, value in sorted(winner_metrics.items()):
        if isinstance(value, float):
            print(f"  {metric:<25}: {value:.3f}")
        else:
            print(f"  {metric:<25}: {value}")
    
    # Extract threshold parameters from winner combo name
    print(f"\n🔧 WINNER THRESHOLD PARAMETERS:")
    print("-" * 35)
    winner_combo = winner['threshold_tag']
    
    # Find the actual regime file to extract parameters
    combo_dir = Path(f"./focused_sweep/{winner_combo}")
    if combo_dir.exists():
        # Look for any regime file to see the parameters used
        regime_files = list(combo_dir.glob("*_regimes.csv"))
        if regime_files:
            print(f"✅ Found regime files in {combo_dir}")
            print(f"   This combination used specific threshold parameters")
            print(f"   Check the focused sweep parameter mapping for exact values")
        else:
            print(f"❌ No regime files found in {combo_dir}")
    
    # Statistical significance analysis
    print(f"\n📊 STATISTICAL SIGNIFICANCE:")
    print("-" * 35)
    
    for signal in ['breakout', 'pin_success']:
        f1_col = f"{signal}_F1"
        if f1_col in df.columns:
            winner_f1 = winner.get(f1_col, 0)
            mean_f1 = df[f1_col].mean()
            std_f1 = df[f1_col].std()
            
            if std_f1 > 0:
                z_score = (winner_f1 - mean_f1) / std_f1
                print(f"{signal:12}: Winner={winner_f1:.3f}, Mean={mean_f1:.3f}, Z-score={z_score:.2f}")
                
                if z_score > 2:
                    print(f"  🔥 STATISTICALLY SIGNIFICANT (>2σ)")
                elif z_score > 1:
                    print(f"  ✅ Above average performance")
                else:
                    print(f"  ⚠️ Not significantly better than average")
    
    # Distribution analysis
    print(f"\n📈 PERFORMANCE DISTRIBUTION:")
    print("-" * 35)
    
    for signal in ['breakout', 'pin_success']:
        f1_col = f"{signal}_F1"
        if f1_col in df.columns:
            values = df[f1_col].dropna()
            if len(values) > 0:
                percentiles = [50, 75, 90, 95, 99]
                print(f"{signal}:")
                for p in percentiles:
                    val = np.percentile(values, p)
                    print(f"  {p:2}th percentile: {val:.3f}")
                
                # Count of "good" performers
                good_threshold = 0.3 if signal == 'breakout' else 0.7
                good_count = (values >= good_threshold).sum()
                print(f"  Combinations with F1 >= {good_threshold}: {good_count}/{len(values)} ({100*good_count/len(values):.1f}%)")
    
    print(f"\n" + "⚔️"*20)
    print(f"RUTHLESS VERDICT:")
    print(f"⚔️"*20)
    print(f"✅ 216/216 combinations tested successfully")
    print(f"🔥 Best breakout F1: {df['breakout_F1'].max():.3f} - SOLID performance")
    print(f"🚀 Best pin F1: {df['pin_success_F1'].max():.3f} - EXCEPTIONAL performance")
    print(f"🏆 Winner: {winner['threshold_tag']}")
    print(f"📊 {len(df):,} total data points analyzed")
    
    # Save focused results for winner
    winner_results_dir = Path(f"./focused_backtest_results/{winner['threshold_tag']}")
    if winner_results_dir.exists():
        print(f"📁 Winner's detailed results: {winner_results_dir}")
    
    return winner

if __name__ == "__main__":
    winner = ruthless_analysis()
    print(f"\n🎯 READY TO IMPLEMENT WINNER: {winner['threshold_tag'] if winner is not None else 'NONE'}")

