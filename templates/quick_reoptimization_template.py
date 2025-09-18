#!/usr/bin/env python3
"""
QUICK RE-OPTIMIZATION TEMPLATE
Copy and modify this script when you need to re-optimize with new data.
"""

import os
import shutil
from datetime import datetime

def quick_reoptimization():
    """Template for quick re-optimization with new data"""
    
    print("🚀 QUICK RE-OPTIMIZATION TEMPLATE")
    print("="*50)
    
    # Get today's date for folder naming
    today = datetime.now().strftime("%Y%m%d")
    
    print(f"📅 Date: {today}")
    print()
    
    print("📋 PRE-OPTIMIZATION CHECKLIST:")
    print("1. ✅ New GEX data files added to raw_levels_with_spot/")
    print("2. ✅ Market regime analyzed (volatility, trend, etc.)")
    print("3. ✅ Parameter ranges updated in run_focused_sweep.py")
    print("4. ✅ Sufficient disk space available")
    print("5. ✅ Current winning parameters documented")
    print()
    
    # Archive previous results
    print("📦 ARCHIVING PREVIOUS RESULTS:")
    if os.path.exists("focused_backtest_results"):
        archive_dir = f"archive/optimization_{today}_previous"
        os.makedirs(archive_dir, exist_ok=True)
        if not os.path.exists(f"{archive_dir}/focused_backtest_results"):
            shutil.move("focused_backtest_results", f"{archive_dir}/focused_backtest_results")
            print(f"   Moved previous results to {archive_dir}/")
        else:
            print("   Previous results already archived")
    
    print()
    print("🎛️ RECOMMENDED PARAMETER STRATEGIES:")
    print()
    
    print("💡 CONSERVATIVE (Around Current Winners):")
    print("   compression_max: [58, 60, 62, 64]")
    print("   ramp_max: [20, 25, 30, 35]") 
    print("   flip_strike_dist: [0.5, 0.75, 1.0, 1.25]")
    print("   → ~4,608 combinations (~8 hours)")
    print()
    
    print("🔍 EXPLORATORY (Market Regime Changed):")
    print("   compression_max: [50, 55, 60, 65, 70, 75]")
    print("   ramp_max: [15, 20, 25, 30, 35, 40]")
    print("   flip_strike_dist: [0.5, 0.75, 1.0, 1.25, 1.5]")
    print("   → ~15,000+ combinations (~24+ hours)")
    print()
    
    print("⚡ QUICK VALIDATION (Monthly Check):")
    print("   compression_max: [58, 60, 62]")
    print("   ramp_max: [23, 25, 27]")
    print("   flip_strike_dist: [0.7, 0.75, 0.8]")
    print("   → ~200 combinations (~2 hours)")
    print()
    
    print("🎯 CURRENT BASELINE TO BEAT:")
    print("   Breakout F1: 0.391")
    print("   Pin F1: 0.636")
    print("   (focused_combo_0025)")
    print()
    
    print("🚀 EXECUTION COMMANDS:")
    print("   Terminal 1: python run_focused_sweep.py")
    print("   Terminal 2: python monitor_focused_sweep.py")
    print()
    print("📊 POST-OPTIMIZATION:")
    print("   python combine_scoreboards_final.py")
    print("   python ruthless_analysis.py")
    print()
    
    response = input("Ready to start optimization? (y/N): ")
    if response.lower() == 'y':
        print("🚀 Starting optimization...")
        os.system("python run_focused_sweep.py")
    else:
        print("✋ Optimization cancelled. Review checklist and try again.")

def market_regime_analyzer():
    """Helper to analyze current market regime for parameter selection"""
    
    print("🔍 MARKET REGIME ANALYSIS HELPER")
    print("="*40)
    print()
    
    print("❓ Answer these questions to determine optimal parameter ranges:")
    print()
    
    volatility = input("Current VIX level? (High >25, Medium 15-25, Low <15): ").lower()
    trend = input("Market trend? (Trending/Choppy/Range-bound): ").lower()
    regime = input("Recent regime change? (Major/Minor/None): ").lower()
    
    print()
    print("🎯 RECOMMENDED APPROACH:")
    
    if volatility == "high" or "high" in volatility:
        print("📊 HIGH VOLATILITY DETECTED:")
        print("   → Use lower compression thresholds [50-60]")
        print("   → Use higher ramp tolerance [30-40]")
        print("   → Use higher expansion thresholds [50-70]")
    elif volatility == "low" or "low" in volatility:
        print("📊 LOW VOLATILITY DETECTED:")
        print("   → Use higher compression thresholds [65-75]")
        print("   → Use lower ramp tolerance [15-25]")
        print("   → Use lower expansion thresholds [30-40]")
    else:
        print("📊 MEDIUM VOLATILITY:")
        print("   → Use current baseline ranges around winning parameters")
    
    if "trend" in trend:
        print("📈 TRENDING MARKET:")
        print("   → Increase flip_strike_dist [1.0-1.5]")
        print("   → Increase expansion_ramp_max [80-100]")
    elif "chop" in trend or "range" in trend:
        print("📊 CHOPPY/RANGE-BOUND MARKET:")
        print("   → Earlier compression entry [55-65]")
        print("   → Earlier compression exit [50-60]")
    
    if regime == "major" or "major" in regime:
        print("🔄 MAJOR REGIME CHANGE:")
        print("   → Use EXPLORATORY approach (wide ranges)")
        print("   → Expect 24+ hour optimization")
    elif regime == "minor" or "minor" in regime:
        print("🔄 MINOR REGIME CHANGE:")
        print("   → Use CONSERVATIVE approach (narrow ranges)")
        print("   → Expect 8 hour optimization")
    else:
        print("🔄 NO REGIME CHANGE:")
        print("   → Use QUICK VALIDATION approach")
        print("   → Expect 2 hour optimization")

if __name__ == "__main__":
    print("🎯 RE-OPTIMIZATION TOOLKIT")
    print("="*30)
    print("1. Market Regime Analysis")
    print("2. Quick Re-optimization")
    print()
    
    choice = input("Choose option (1/2): ")
    
    if choice == "1":
        market_regime_analyzer()
    elif choice == "2":
        quick_reoptimization()
    else:
        print("Invalid choice. Run script again.")
