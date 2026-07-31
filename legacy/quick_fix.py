# Create this as: quick_fix.py
# Run this immediately to improve your bot's performance

import os
import shutil
import pandas as pd
from datetime import datetime

def apply_quick_fixes():
    """
    Apply immediate fixes to improve bot performance
    """
    print("🚀 APPLYING QUICK FIXES TO IMPROVE BOT PERFORMANCE")
    print("=" * 55)
    
    fixes_applied = []
    
    # 1. Update trade scanner with more realistic settings
    print("\n1. 📝 Updating trade scanner settings...")
    
    scanner_path = "src/trade_scanner.py"
    if os.path.exists(scanner_path):
        # Read current scanner
        with open(scanner_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Create backup
        backup_path = f"{scanner_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(scanner_path, backup_path)
        
        # Apply critical fixes to the existing scanner
        fixes = [
            # Reduce profit targets
            ('REWARD_PERCENT = 15.0', 'REWARD_PERCENT = 8.0'),  # 15% to 8%
            ('RISK_PERCENT = 5.0', 'RISK_PERCENT = 4.0'),      # 5% to 4% 
            
            # Increase trade duration
            ('trade_duration_hours = timeframe_map.get(timeframe, 12)', 
             'trade_duration_hours = timeframe_map.get(timeframe, 12) * 3'),  # 3x longer
            
            # Lower AI threshold in function signature
            ('prob_threshold=0.7', 'prob_threshold=0.65'),
            
            # Reduce maximum signals
            ('if len(signals) >= 19:', 'if len(signals) >= 3:'),
        ]
        
        updated_content = content
        for old, new in fixes:
            if old in updated_content:
                updated_content = updated_content.replace(old, new)
                print(f"   ✅ Fixed: {old} → {new}")
                fixes_applied.append(f"Scanner: {old} → {new}")
        
        # Write updated scanner
        with open(scanner_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        print(f"   💾 Scanner updated (backup saved as {backup_path})")
    else:
        print("   ❌ Scanner file not found!")
    
    # 2. Update app.py default settings
    print("\n2. 🎛️  Updating app default settings...")
    
    app_path = "app.py"
    if os.path.exists(app_path):
        with open(app_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Create backup
        backup_path = f"{app_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(app_path, backup_path)
        
        # Apply fixes
        app_fixes = [
            ('num_coins = st.sidebar.slider("Number of Coins to Scan", 1, 100, 20)', 
             'num_coins = st.sidebar.slider("Number of Coins to Scan", 1, 100, 50)'),
            ('prob_threshold = st.sidebar.slider("Breakout Probability Threshold", 0.1, 1.0, 0.7, 0.01)',
             'prob_threshold = st.sidebar.slider("Breakout Probability Threshold", 0.1, 1.0, 0.65, 0.01)'),
            ('timeframe = st.sidebar.selectbox("Select Timeframe", ["4h", "6h", "12h", "1d"], index=2)',
             'timeframe = st.sidebar.selectbox("Select Timeframe", ["4h", "6h", "12h", "1d"], index=3)')  # Default to 1d
        ]
        
        updated_content = content
        for old, new in app_fixes:
            if old in updated_content:
                updated_content = updated_content.replace(old, new)
                print(f"   ✅ Fixed: Default values updated")
                fixes_applied.append(f"App: {old} → {new}")
        
        with open(app_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        print(f"   💾 App updated (backup saved as {backup_path})")
    else:
        print("   ❌ App file not found!")
    
        # 3. Clean up stale ongoing trades
    print("\n3. 🧹 Cleaning up stale trades...")
    
    trade_file = "data/trade_signals.csv"
    if os.path.exists(trade_file):
        try:
            df = pd.read_csv(trade_file)
            # Convert timestamps, strip timezone if present
            df['suggested_at'] = pd.to_datetime(df['suggested_at'], errors='coerce').dt.tz_localize(None)
            df['grace_until'] = pd.to_datetime(df['grace_until'], errors='coerce').dt.tz_localize(None)
            now = pd.Timestamp.utcnow().tz_localize(None)
            expired_mask = (df['status'] == 'ongoing') & (df['grace_until'] < now)
            expired_count = expired_mask.sum()
            
            if expired_count > 0:
                print(f"   🔄 Marking {expired_count} trades as expired...")
                
                # Mark as finished with "Tie" result
                df.loc[expired_mask, 'status'] = 'finished'
                df.loc[expired_mask, 'result'] = 'Tie'
                df.loc[expired_mask, 'exit_time'] = now
                
                # Save updated file
                backup_path = f"{trade_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(trade_file, backup_path)
                
                df.to_csv(trade_file, index=False)
                print(f"   ✅ Trade file updated (backup: {backup_path})")
                fixes_applied.append(f"Cleaned {expired_count} stale trades")
            else:
                print("   ✅ No stale trades found")
                
        except Exception as e:
            print(f"   ❌ Error cleaning trades: {e}")
    else:
        print("   ⚠️ No trade file found")    
    # 4. Create recommended settings file
    print("\n4. 📋 Creating recommended settings file...")
    
    settings = {
        'scanner_settings': {
            'num_coins': 50,
            'timeframe': '1d',
            'prob_threshold': 0.65,
            'max_signals_per_scan': 3
        },
        'trade_settings': {
            'profit_target_pct': 8.0,
            'stop_loss_pct': 4.0,
            'trade_duration_days': 7,
            'grace_period_hours': 12
        },
        'model_settings': {
            'retrain_frequency': 'monthly',
            'min_training_samples': 1000,
            'feature_importance_threshold': 0.01
        }
    }
    
    settings_file = "recommended_settings.txt"
    with open(settings_file, 'w', encoding='utf-8') as f:
        f.write("🎯 RECOMMENDED SETTINGS FOR BETTER PERFORMANCE\n")
        f.write("=" * 50 + "\n\n")
        
        for category, values in settings.items():
            f.write(f"{category.upper()}:\n")
            for key, value in values.items():
                f.write(f"  {key}: {value}\n")
            f.write("\n")
        
        f.write("USAGE INSTRUCTIONS:\n")
        f.write("1. Use 1d timeframe with 7-day trade duration\n")
        f.write("2. Scan 50+ coins but accept max 3 signals\n")
        f.write("3. Use 65% AI confidence threshold\n")
        f.write("4. Target 8% profits with 4% stop losses\n")
        f.write("5. Wait full duration before calling trades ties\n")
        f.write("6. Retrain model monthly with fresh data\n")
    
    print(f"   ✅ Settings saved to {settings_file}")
    fixes_applied.append("Created recommended settings file")
    
    # 5. Summary and next steps
    print(f"\n✅ QUICK FIXES APPLIED ({len(fixes_applied)} fixes)")
    print("=" * 55)
    
    for i, fix in enumerate(fixes_applied, 1):
        print(f"{i}. {fix}")
    
    print(f"\n🎯 IMMEDIATE NEXT STEPS:")
    print("1. 🔄 Restart your Streamlit app: streamlit run app.py")
    print("2. 🎲 Run a new scan with these settings:")
    print("   - 50+ coins")
    print("   - 1d timeframe") 
    print("   - 0.65 threshold")
    print("   - Accept max 3 signals")
    print("3. ⏰ Wait 7 days before evaluating results")
    print("4. 📊 Run the performance analyzer: python analyze_performance.py")
    
    print(f"\n💡 EXPECTED IMPROVEMENTS:")
    print("- ✅ Fewer but higher quality signals")
    print("- ✅ More realistic profit targets")
    print("- ✅ Longer timeframes for better success")
    print("- ✅ Reduced tie rate")
    print("- ✅ Better risk/reward ratio")
    
    print(f"\n🚨 IMPORTANT:")
    print("These are quick fixes. For best results, also:")
    print("- Train the improved model (run 04_improved_training.ipynb)")
    print("- Update to the improved scanner code")
    print("- Monitor performance weekly")

if __name__ == "__main__":
    apply_quick_fixes()