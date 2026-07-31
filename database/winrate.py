"""
Enhanced winrate and performance analytics system
Comprehensive statistics tracking with data validation and cleanup
"""

import pandas as pd
import numpy as np
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from config.settings import config

logger = logging.getLogger(__name__)

class WinrateAnalyzer:
    """Enhanced winrate analysis with comprehensive statistics"""
    
    def __init__(self):
        self.trade_log_file = config.TRADE_LOG_FILE
        self.winrate_file = config.WINRATE_FILE
        
        # Ensure directories exist
        config.ensure_directories()
    
    def ensure_winrate_file(self):
        """Ensure winrate file exists with proper structure"""
        if not os.path.exists(self.winrate_file):
            df = pd.DataFrame(columns=[
                "symbol", "entry", "stoploss", "tp1", "tp2", "tp3",
                "timeframe", "suggested_at", "result", "result_time", 
                "direction", "exit_price", "probability"
            ])
            df.to_csv(self.winrate_file, index=False)
            logger.info(f"✅ Created winrate file: {self.winrate_file}")
    
    def migrate_completed_trades(self) -> int:
        """Migrate completed trades from trade log to winrate log"""
        try:
            if not os.path.exists(self.trade_log_file):
                logger.info("📝 No trade log file to migrate from")
                return 0
            
            # Load trade signals
            trade_df = pd.read_csv(self.trade_log_file)
            
            if trade_df.empty:
                logger.info("📝 Trade log is empty")
                return 0
            
            # Ensure winrate file exists
            self.ensure_winrate_file()
            
            # Load existing winrate data
            winrate_df = pd.read_csv(self.winrate_file) if os.path.exists(self.winrate_file) else pd.DataFrame()
            
            # Find completed trades
            completed_trades = trade_df[
                (trade_df['status'] == 'finished') & 
                (trade_df['result'].notna()) &
                (trade_df['result'] != '') &
                (trade_df['result'] != 'pending')
            ].copy()
            
            if completed_trades.empty:
                logger.info("📝 No completed trades to migrate")
                return 0
            
            # Prepare migration data
            migrated_trades = []
            for _, row in completed_trades.iterrows():
                trade_record = {
                    "symbol": row.get("symbol", ""),
                    "entry": row.get("entry", 0),
                    "stoploss": row.get("stoploss", 0),
                    "tp1": row.get("tp1", 0),
                    "tp2": row.get("tp2", 0),
                    "tp3": row.get("tp3", 0),
                    "timeframe": row.get("timeframe", ""),
                    "suggested_at": row.get("suggested_at", ""),
                    "result": row.get("result", ""),
                    "result_time": row.get("exit_time", row.get("result_time", "")),
                    "direction": row.get("direction", "LONG"),
                    "exit_price": row.get("exit_price", None),
                    "probability": row.get("probability", None)
                }
                migrated_trades.append(trade_record)
            
            # Check for duplicates (simple deduplication)
            new_trades_df = pd.DataFrame(migrated_trades)
            
            if not winrate_df.empty:
                # Remove duplicates based on symbol and suggested_at
                existing_keys = set(
                    zip(winrate_df['symbol'], winrate_df['suggested_at'])
                )
                new_trades_df = new_trades_df[
                    ~new_trades_df.apply(
                        lambda x: (x['symbol'], x['suggested_at']) in existing_keys, 
                        axis=1
                    )
                ]
            
            # Save migrated trades
            if not new_trades_df.empty:
                combined_df = pd.concat([winrate_df, new_trades_df], ignore_index=True)
                combined_df.to_csv(self.winrate_file, index=False)
                logger.info(f"✅ Migrated {len(new_trades_df)} new trades to winrate log")
                return len(new_trades_df)
            else:
                logger.info("📝 No new trades to migrate")
                return 0
                
        except Exception as e:
            logger.error(f"❌ Error migrating trades: {e}")
            return 0
    
    def clean_invalid_data(self) -> int:
        """Clean invalid and corrupted data from winrate file"""
        try:
            if not os.path.exists(self.winrate_file):
                return 0
            
            df = pd.read_csv(self.winrate_file)
            
            if df.empty:
                return 0
            
            initial_len = len(df)
            
            # Remove records with missing critical data
            df = df.dropna(subset=['symbol', 'result'])
            df = df[df['symbol'] != '']
            df = df[df['result'] != '']
            
            # Normalize result values
            result_mapping = {
                'SL': 'Loss',
                'sl': 'Loss',
                'Stoploss': 'Loss',
                'Stop Loss': 'Loss',
                'pending': 'Tie',
                'TIMEOUT': 'Tie',
                'timeout': 'Tie'
            }
            df['result'] = df['result'].replace(result_mapping)
            
            # Remove impossible timestamp combinations
            try:
                df['suggested_at'] = pd.to_datetime(df['suggested_at'], errors='coerce')
                df['result_time'] = pd.to_datetime(df['result_time'], errors='coerce')
                
                # Remove records where result_time is before suggested_at
                valid_times = df['result_time'] >= df['suggested_at']
                df = df[valid_times]
                
            except Exception as e:
                logger.warning(f"⚠️ Error cleaning timestamps: {e}")
            
            # Remove impossible price relationships
            try:
                for i, row in df.iterrows():
                    if pd.notna(row.get('entry')) and pd.notna(row.get('exit_price')):
                        entry = float(row['entry'])
                        exit_price = float(row['exit_price'])
                        direction = row.get('direction', 'UNKNOWN')
                        result = row.get('result', '')
                        
                        # Check for impossible combinations
                        invalid = False
                        
                        if direction == 'LONG' and 'TP' in result and exit_price <= entry:
                            invalid = True
                        elif direction == 'SHORT' and 'TP' in result and exit_price >= entry:
                            invalid = True
                        
                        if invalid:
                            df = df.drop(i)
                            
            except Exception as e:
                logger.warning(f"⚠️ Error cleaning price relationships: {e}")
            
            # Save cleaned data
            final_len = len(df)
            removed_count = initial_len - final_len
            
            if removed_count > 0:
                df.to_csv(self.winrate_file, index=False)
                logger.info(f"🧹 Cleaned {removed_count} invalid records from winrate data")
            
            return removed_count
            
        except Exception as e:
            logger.error(f"❌ Error cleaning winrate data: {e}")
            return 0
    
    def calculate_comprehensive_stats(self) -> Dict:
        """Calculate comprehensive trading statistics"""
        try:
            # Ensure data is migrated and clean
            self.migrate_completed_trades()
            self.clean_invalid_data()
            
            if not os.path.exists(self.winrate_file):
                return self._empty_stats()
            
            df = pd.read_csv(self.winrate_file)
            
            if df.empty:
                return self._empty_stats()
            
            # Clean result column
            df = df.dropna(subset=['result'])
            df = df[df['result'] != '']
            
            if df.empty:
                return self._empty_stats()
            
            # Calculate basic stats
            total_trades = len(df)
            
            # Count different result types
            tp1_hits = len(df[df['result'] == 'TP1'])
            tp2_hits = len(df[df['result'] == 'TP2'])
            tp3_hits = len(df[df['result'] == 'TP3'])
            losses = len(df[df['result'].isin(['Loss', 'SL'])])
            ties = len(df[df['result'].isin(['Tie', 'TIMEOUT'])])
            
            total_wins = tp1_hits + tp2_hits + tp3_hits
            winrate = (total_wins / total_trades * 100) if total_trades > 0 else 0
            
            # Performance by timeframe
            timeframe_stats = {}
            if 'timeframe' in df.columns:
                for tf in df['timeframe'].unique():
                    if pd.notna(tf):
                        tf_df = df[df['timeframe'] == tf]
                        tf_wins = len(tf_df[tf_df['result'].str.contains('TP', na=False)])
                        tf_total = len(tf_df)
                        tf_winrate = (tf_wins / tf_total * 100) if tf_total > 0 else 0
                        
                        timeframe_stats[tf] = {
                            'total': tf_total,
                            'wins': tf_wins,
                            'winrate': round(tf_winrate, 2)
                        }
            
            # Performance by probability bucket
            probability_stats = {}
            if 'probability' in df.columns:
                df_prob = df.dropna(subset=['probability'])
                if not df_prob.empty:
                    # Create probability buckets
                    df_prob['prob_bucket'] = pd.cut(
                        df_prob['probability'], 
                        bins=[0, 0.6, 0.7, 0.8, 0.9, 1.0],
                        labels=['50-60%', '60-70%', '70-80%', '80-90%', '90-100%']
                    )
                    
                    for bucket in df_prob['prob_bucket'].unique():
                        if pd.notna(bucket):
                            bucket_df = df_prob[df_prob['prob_bucket'] == bucket]
                            bucket_wins = len(bucket_df[bucket_df['result'].str.contains('TP', na=False)])
                            bucket_total = len(bucket_df)
                            bucket_winrate = (bucket_wins / bucket_total * 100) if bucket_total > 0 else 0
                            
                            probability_stats[str(bucket)] = {
                                'total': bucket_total,
                                'wins': bucket_wins,
                                'winrate': round(bucket_winrate, 2)
                            }
            
            # Recent performance (last 30 days)
            recent_stats = {}
            try:
                df['result_time'] = pd.to_datetime(df['result_time'], errors='coerce')
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
                recent_df = df[df['result_time'] > cutoff_date]
                
                if not recent_df.empty:
                    recent_wins = len(recent_df[recent_df['result'].str.contains('TP', na=False)])
                    recent_total = len(recent_df)
                    recent_winrate = (recent_wins / recent_total * 100) if recent_total > 0 else 0
                    
                    recent_stats = {
                        'total': recent_total,
                        'wins': recent_wins,
                        'winrate': round(recent_winrate, 2)
                    }
            except:
                pass
            
            # Get recent trades for display
            recent_trades = []
            try:
                recent_df = df.tail(10)
                for _, row in recent_df.iterrows():
                    recent_trades.append({
                        'symbol': row.get('symbol', 'N/A'),
                        'result': row.get('result', 'N/A'),
                        'direction': row.get('direction', 'N/A'),
                        'timeframe': row.get('timeframe', 'N/A'),
                        'suggested_at': row.get('suggested_at', 'N/A')
                    })
            except:
                pass
            
            return {
                'total': total_trades,
                'wins': total_wins,
                'losses': losses,
                'ties': ties,
                'winrate': round(winrate, 2),
                'tp1_hits': tp1_hits,
                'tp2_hits': tp2_hits,
                'tp3_hits': tp3_hits,
                'timeframe_stats': timeframe_stats,
                'probability_stats': probability_stats,
                'recent_stats': recent_stats,
                'recent_trades': recent_trades
            }
            
        except Exception as e:
            logger.error(f"❌ Error calculating stats: {e}")
            return self._empty_stats()
    
    def _empty_stats(self) -> Dict:
        """Return empty statistics structure"""
        return {
            'total': 0,
            'wins': 0,
            'losses': 0,
            'ties': 0,
            'winrate': 0.0,
            'tp1_hits': 0,
            'tp2_hits': 0,
            'tp3_hits': 0,
            'timeframe_stats': {},
            'probability_stats': {},
            'recent_stats': {},
            'recent_trades': []
        }
    
    def update_winrate_stats(self, symbol: str, entry: float, stoploss: float,
                           tp1: float, tp2: float, tp3: float, timeframe: str,
                           suggested_at: str, result: str, result_time: str,
                           direction: str = "LONG", exit_price: Optional[float] = None,
                           probability: Optional[float] = None):
        """Add a completed trade to winrate statistics"""
        try:
            self.ensure_winrate_file()
            
            # Create new trade record
            new_trade = {
                "symbol": symbol,
                "entry": entry,
                "stoploss": stoploss,
                "tp1": tp1,
                "tp2": tp2,
                "tp3": tp3,
                "timeframe": timeframe,
                "suggested_at": suggested_at,
                "result": result,
                "result_time": result_time,
                "direction": direction,
                "exit_price": exit_price,
                "probability": probability
            }
            
            # Load existing data
            df = pd.read_csv(self.winrate_file) if os.path.exists(self.winrate_file) else pd.DataFrame()
            
            # Add new trade
            new_df = pd.DataFrame([new_trade])
            df = pd.concat([df, new_df], ignore_index=True)
            
            # Save updated data
            df.to_csv(self.winrate_file, index=False)
            
            logger.info(f"📊 Trade result logged: {symbol} - {result}")
            
        except Exception as e:
            logger.error(f"❌ Error updating winrate stats: {e}")

# Global instance
winrate_analyzer = WinrateAnalyzer()

# Backward compatibility functions
def get_winrate_stats():
    """Backward compatibility function"""
    return winrate_analyzer.calculate_comprehensive_stats()

def update_winrate_stats(symbol, entry, stoploss, tp1, tp2, tp3, timeframe, 
                        suggested_at, result, result_time, direction="LONG", 
                        exit_price=None, probability=None):
    """Backward compatibility function"""
    return winrate_analyzer.update_winrate_stats(
        symbol, entry, stoploss, tp1, tp2, tp3, timeframe,
        suggested_at, result, result_time, direction, exit_price, probability
    )

def update_expired_trades():
    """Backward compatibility function"""
    return winrate_analyzer.migrate_completed_trades()