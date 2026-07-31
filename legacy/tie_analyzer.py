# In src/tie_analyzer.py (REPLACE THE ENTIRE FILE)

import pandas as pd
import ccxt
import os
from datetime import datetime, timezone

# --- SETTINGS ---
TRADE_LOG_FILE = "data/trade_signals.csv"
NEAR_MISS_THRESHOLD_PERCENT = 0.2 # How close to TP1 (in %) counts as a "near miss"

def analyze_ties():
    """
    Analyzes all 'Tie' trades to see how close they came to hitting Take Profit 1.
    This version is robust and handles different timestamp formats.
    """
    if not os.path.exists(TRADE_LOG_FILE):
        print(f"ERROR: Trade log file not found at '{TRADE_LOG_FILE}'")
        return

    print(f"--- Starting Tie Analysis on {TRADE_LOG_FILE} ---")
    df = pd.read_csv(TRADE_LOG_FILE)

    tie_df = df[df['result'] == 'Tie'].copy()
    if tie_df.empty:
        print("No 'Tie' trades found to analyze.")
        return

    print(f"Found {len(tie_df)} 'Tie' trades to analyze. This may take a moment...")

    exchange = ccxt.binance()
    results = []
    near_miss_count = 0

    for index, trade in tie_df.iterrows():
        symbol, direction, entry_price, tp1 = trade['symbol'], trade['direction'], trade['entry'], trade['tp1']
        
        try:
            # --- ROBUST TIMESTAMP HANDLING ---
            start_dt = pd.to_datetime(trade['suggested_at'])
            end_dt = pd.to_datetime(trade['exit_time'])

            # If the timestamp is naive (no tz info), assign UTC. If it's aware, do nothing.
            if start_dt.tzinfo is None:
                start_dt = start_dt.tz_localize('UTC')
            if end_dt.tzinfo is None:
                end_dt = end_dt.tz_localize('UTC')

            since_ms = int(start_dt.timestamp() * 1000)
            
            print(f"\nAnalyzing {symbol} (Trade #{index})...")

            ohlcv = exchange.fetch_ohlcv(symbol, '1m', since=since_ms, limit=1000)
            if not ohlcv:
                print(f"  -> WARNING: No price data for {symbol} in active period.")
                continue

            price_df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            price_df['timestamp'] = pd.to_datetime(price_df['timestamp'], unit='ms', utc=True)
            
            trade_window_df = price_df[(price_df['timestamp'] >= start_dt) & (price_df['timestamp'] <= end_dt)]
            
            if trade_window_df.empty:
                print(f"  -> WARNING: No price data in the precise trade window for {symbol}.")
                continue

            highest_price, lowest_price = trade_window_df['high'].max(), trade_window_df['low'].min()
            distance_pct, is_near_miss = None, False

            if direction.upper() == 'LONG':
                if highest_price >= entry_price:
                    distance_pct = ((tp1 - highest_price) / entry_price) * 100
                    if distance_pct <= NEAR_MISS_THRESHOLD_PERCENT:
                        is_near_miss = True; near_miss_count += 1
                else: distance_pct = ((tp1 - entry_price) / entry_price) * 100
            elif direction.upper() == 'SHORT':
                if lowest_price <= entry_price:
                    distance_pct = ((lowest_price - tp1) / entry_price) * 100
                    if distance_pct <= NEAR_MISS_THRESHOLD_PERCENT:
                        is_near_miss = True; near_miss_count += 1
                else: distance_pct = ((entry_price - tp1) / entry_price) * 100
            
            results.append({
                'symbol': symbol, 'distance_to_tp1_pct': round(distance_pct, 4) if distance_pct is not None else 'N/A',
                'was_near_miss': is_near_miss, 'highest_price': highest_price, 'lowest_price': lowest_price
            })
            print(f"  -> Closest distance to TP1: {distance_pct:.4f}%")

        except Exception as e:
            print(f"  -> ERROR processing trade for {symbol}: {e}")

    # --- Final Report ---
    if not results:
        print("\nNo valid 'Tie' trades were analyzed successfully.")
        return
        
    results_df = pd.DataFrame(results)
    results_df.to_csv("data/tie_analysis_results.csv", index=False)
    
    near_miss_percentage = (near_miss_count / len(results_df)) * 100 if results else 0
    avg_miss_distance = results_df[results_df['was_near_miss']]['distance_to_tp1_pct'].mean() if near_miss_count > 0 else 0
    
    print("\n\n--- 📈 Tie Analysis Report ---")
    print("=" * 35)
    print(f"Total 'Tie' Trades Analyzed: {len(results_df)}")
    print(f"Near Misses (within {NEAR_MISS_THRESHOLD_PERCENT}% of TP1): {near_miss_count}")
    print(f"Percentage of Ties that were Near Misses: {near_miss_percentage:.1f}%")
    print(f"Average Distance for Near Misses: {avg_miss_distance:.4f}%")
    print("=" * 35)
    print("\nDetailed results saved to 'data/tie_analysis_results.csv'")

if __name__ == '__main__':
    analyze_ties()