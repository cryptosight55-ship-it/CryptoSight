"""
Enhanced Performance Tracking System for AI Crypto Trading Bot
Real-time trade monitoring with win/loss/tie tracking and TP analysis
"""

import pandas as pd
import numpy as np
import logging
import os
import ccxt
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import asyncio
import threading
import time

from config.settings import config
from data.fetcher import get_data_fetcher
from database.winrate import winrate_analyzer

logger = logging.getLogger(__name__)

class PerformanceTracker:
    """Enhanced performance tracking with real-time monitoring"""
    
    def __init__(self):
        self.trade_log_file = config.TRADE_LOG_FILE
        self.winrate_file = config.WINRATE_FILE
        self.exchange = None
        self.monitoring_active = False
        self.monitor_thread = None
        
        # Ensure directories exist
        config.ensure_directories()
        self.ensure_trade_log_file()
    
    def ensure_trade_log_file(self):
        """Ensure trade log file exists with proper structure"""
        if not os.path.exists(self.trade_log_file):
            df = pd.DataFrame(columns=[
                "signal_id", "symbol", "direction", "timeframe", "entry", "current_price",
                "stop_loss", "take_profit_1", "take_profit_2", "take_profit_3",
                "probability", "suggested_at", "expires_at", "status", "result",
                "exit_price", "exit_time", "profit_pct", "duration_hours"
            ])
            df.to_csv(self.trade_log_file, index=False)
            logger.info(f"✅ Created trade log file: {self.trade_log_file}")
    
    def log_signal(self, signal: Dict) -> str:
        """Log a new trading signal for monitoring"""
        try:
            # Generate unique signal ID
            signal_id = f"{signal['symbol']}_{signal['timeframe']}_{int(signal['timestamp'].timestamp())}"
            
            # Calculate expiry time
            duration_hours = signal.get('duration_hours', 24)
            expires_at = signal['timestamp'] + timedelta(hours=duration_hours)
            
            # Create trade record
            trade_record = {
                "signal_id": signal_id,
                "symbol": signal['symbol'],
                "direction": signal['direction'],
                "timeframe": signal['timeframe'],
                "entry": signal['entry'],
                "current_price": signal['current_price'],
                "stop_loss": signal['stop_loss'],
                "take_profit_1": signal['take_profit_1'],
                "take_profit_2": signal['take_profit_2'],
                "take_profit_3": signal['take_profit_3'],
                "probability": signal['probability'],
                "suggested_at": signal['timestamp'].isoformat(),
                "expires_at": expires_at.isoformat(),
                "status": "active",
                "result": "pending",
                "exit_price": None,
                "exit_time": None,
                "profit_pct": None,
                "duration_hours": duration_hours
            }
            
            # Load existing data
            df = pd.read_csv(self.trade_log_file) if os.path.exists(self.trade_log_file) else pd.DataFrame()
            
            # Add new trade
            new_df = pd.DataFrame([trade_record])
            df = pd.concat([df, new_df], ignore_index=True)
            
            # Save updated data
            df.to_csv(self.trade_log_file, index=False)
            
            logger.info(f"📝 Logged signal: {signal_id}")
            return signal_id
            
        except Exception as e:
            logger.error(f"❌ Error logging signal: {e}")
            return ""
    
    def start_monitoring(self):
        """Start the performance monitoring system"""
        if self.monitoring_active:
            logger.info("📊 Performance monitoring already active")
            return
        
        try:
            self.exchange = get_data_fetcher().exchange
            self.monitoring_active = True
            
            # Start monitoring in a separate thread
            self.monitor_thread = threading.Thread(target=self._monitor_trades, daemon=True)
            self.monitor_thread.start()
            
            logger.info("📊 Performance monitoring started")
            
        except Exception as e:
            logger.error(f"❌ Error starting monitoring: {e}")
    
    def stop_monitoring(self):
        """Stop the performance monitoring system"""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("📊 Performance monitoring stopped")
    
    def _monitor_trades(self):
        """Main monitoring loop (runs in separate thread)"""
        logger.info("🔄 Trade monitoring loop started")
        
        while self.monitoring_active:
            try:
                self._check_active_trades()
                time.sleep(30)  # Check every 30 seconds
            except Exception as e:
                logger.error(f"❌ Error in monitoring loop: {e}")
                time.sleep(60)  # Wait longer on error
    
    def _check_active_trades(self):
        """Check all active trades for TP/SL hits or expiry"""
        try:
            if not os.path.exists(self.trade_log_file):
                return
            
            df = pd.read_csv(self.trade_log_file)
            active_trades = df[df['status'] == 'active'].copy()
            
            if active_trades.empty:
                return
            
            current_time = datetime.now(timezone.utc)
            updated_trades = []
            
            for idx, trade in active_trades.iterrows():
                try:
                    # Get current price
                    current_price = self._get_current_price(trade['symbol'])
                    if current_price is None:
                        continue
                    
                    # Check for TP/SL hits
                    result = self._check_trade_result(trade, current_price)
                    
                    if result['hit']:
                        # Trade completed
                        df.at[idx, 'status'] = 'finished'
                        df.at[idx, 'result'] = result['type']
                        df.at[idx, 'exit_price'] = current_price
                        df.at[idx, 'exit_time'] = current_time.isoformat()
                        df.at[idx, 'profit_pct'] = result['profit_pct']
                        
                        # Log to winrate system
                        self._log_to_winrate(trade, result, current_price, current_time)
                        
                        logger.info(f"🎯 Trade completed: {trade['symbol']} - {result['type']} "
                                  f"({result['profit_pct']:.2f}%)")
                        
                        updated_trades.append(trade['signal_id'])
                    
                    else:
                        # Check for expiry
                        expires_at = pd.to_datetime(trade['expires_at'])
                        if current_time > expires_at:
                            # Trade expired
                            df.at[idx, 'status'] = 'expired'
                            df.at[idx, 'result'] = 'TIMEOUT'
                            df.at[idx, 'exit_price'] = current_price
                            df.at[idx, 'exit_time'] = current_time.isoformat()
                            
                            # Calculate final profit/loss
                            entry_price = float(trade['entry'])
                            if trade['direction'] == 'LONG':
                                profit_pct = ((current_price - entry_price) / entry_price) * 100
                            else:
                                profit_pct = ((entry_price - current_price) / entry_price) * 100
                            
                            df.at[idx, 'profit_pct'] = profit_pct
                            
                            # Log to winrate system
                            result = {'type': 'TIMEOUT', 'profit_pct': profit_pct}
                            self._log_to_winrate(trade, result, current_price, current_time)
                            
                            logger.info(f"⏰ Trade expired: {trade['symbol']} - TIMEOUT "
                                      f"({profit_pct:.2f}%)")
                            
                            updated_trades.append(trade['signal_id'])
                
                except Exception as e:
                    logger.error(f"❌ Error checking trade {trade['symbol']}: {e}")
                    continue
            
            # Save updated data if any trades were modified
            if updated_trades:
                df.to_csv(self.trade_log_file, index=False)
                logger.info(f"📊 Updated {len(updated_trades)} trades")
            
        except Exception as e:
            logger.error(f"❌ Error checking active trades: {e}")
    
    def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for a symbol"""
        try:
            if self.exchange is None:
                logger.debug("Exchange not available for price fetching")
                return None
            
            # Convert symbol format if needed (e.g., BTC/USDT)
            if '/' not in symbol:
                symbol = symbol.replace('_', '/').replace('-', '/')
            
            ticker = self.exchange.fetch_ticker(symbol)
            return float(ticker['last'])
            
        except Exception as e:
            logger.debug(f"Error fetching price for {symbol}: {e}")
            return None
    
    def _check_trade_result(self, trade: pd.Series, current_price: float) -> Dict:
        """Check if trade hit TP or SL"""
        try:
            entry_price = float(trade['entry'])
            direction = trade['direction']
            
            # Define target levels
            sl = float(trade['stop_loss'])
            tp1 = float(trade['take_profit_1'])
            tp2 = float(trade['take_profit_2'])
            tp3 = float(trade['take_profit_3'])
            
            if direction == 'LONG':
                # Check stop loss
                if current_price <= sl:
                    profit_pct = ((current_price - entry_price) / entry_price) * 100
                    return {'hit': True, 'type': 'SL', 'profit_pct': profit_pct}
                
                # Check take profits (highest first)
                if current_price >= tp3:
                    profit_pct = ((current_price - entry_price) / entry_price) * 100
                    return {'hit': True, 'type': 'TP3', 'profit_pct': profit_pct}
                elif current_price >= tp2:
                    profit_pct = ((current_price - entry_price) / entry_price) * 100
                    return {'hit': True, 'type': 'TP2', 'profit_pct': profit_pct}
                elif current_price >= tp1:
                    profit_pct = ((current_price - entry_price) / entry_price) * 100
                    return {'hit': True, 'type': 'TP1', 'profit_pct': profit_pct}
            
            else:  # SHORT
                # Check stop loss
                if current_price >= sl:
                    profit_pct = ((entry_price - current_price) / entry_price) * 100
                    return {'hit': True, 'type': 'SL', 'profit_pct': profit_pct}
                
                # Check take profits (lowest first)
                if current_price <= tp3:
                    profit_pct = ((entry_price - current_price) / entry_price) * 100
                    return {'hit': True, 'type': 'TP3', 'profit_pct': profit_pct}
                elif current_price <= tp2:
                    profit_pct = ((entry_price - current_price) / entry_price) * 100
                    return {'hit': True, 'type': 'TP2', 'profit_pct': profit_pct}
                elif current_price <= tp1:
                    profit_pct = ((entry_price - current_price) / entry_price) * 100
                    return {'hit': True, 'type': 'TP1', 'profit_pct': profit_pct}
            
            return {'hit': False, 'type': None, 'profit_pct': 0}
            
        except Exception as e:
            logger.error(f"❌ Error checking trade result: {e}")
            return {'hit': False, 'type': None, 'profit_pct': 0}
    
    def _log_to_winrate(self, trade: pd.Series, result: Dict, exit_price: float, exit_time: datetime):
        """Log completed trade to winrate system"""
        try:
            winrate_analyzer.update_winrate_stats(
                symbol=trade['symbol'],
                entry=float(trade['entry']),
                stoploss=float(trade['stop_loss']),
                tp1=float(trade['take_profit_1']),
                tp2=float(trade['take_profit_2']),
                tp3=float(trade['take_profit_3']),
                timeframe=trade['timeframe'],
                suggested_at=trade['suggested_at'],
                result=result['type'],
                result_time=exit_time.isoformat(),
                direction=trade['direction'],
                exit_price=exit_price,
                probability=float(trade['probability']) if pd.notna(trade['probability']) else None
            )
        except Exception as e:
            logger.error(f"❌ Error logging to winrate: {e}")
    
    def get_active_trades_summary(self) -> Dict:
        """Get summary of currently active trades"""
        try:
            if not os.path.exists(self.trade_log_file):
                return {'active_count': 0, 'trades': []}
            
            df = pd.read_csv(self.trade_log_file)
            active_trades = df[df['status'] == 'active']
            
            trades_summary = []
            for _, trade in active_trades.iterrows():
                # Get current price and calculate unrealized P&L
                current_price = self._get_current_price(trade['symbol'])
                unrealized_pnl = 0
                
                if current_price:
                    entry_price = float(trade['entry'])
                    if trade['direction'] == 'LONG':
                        unrealized_pnl = ((current_price - entry_price) / entry_price) * 100
                    else:
                        unrealized_pnl = ((entry_price - current_price) / entry_price) * 100
                
                trades_summary.append({
                    'symbol': trade['symbol'],
                    'direction': trade['direction'],
                    'timeframe': trade['timeframe'],
                    'entry': trade['entry'],
                    'current_price': current_price,
                    'unrealized_pnl': round(unrealized_pnl, 2),
                    'probability': trade['probability'],
                    'suggested_at': trade['suggested_at'],
                    'expires_at': trade['expires_at']
                })
            
            return {
                'active_count': len(active_trades),
                'trades': trades_summary
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting active trades: {e}")
            return {'active_count': 0, 'trades': []}
    
    def get_performance_stats(self) -> Dict:
        """Get comprehensive performance statistics"""
        return winrate_analyzer.calculate_comprehensive_stats()
    
    def cleanup_old_trades(self, days: int = 30):
        """Clean up old completed trades"""
        try:
            if not os.path.exists(self.trade_log_file):
                return
            
            df = pd.read_csv(self.trade_log_file)
            df['suggested_at'] = pd.to_datetime(df['suggested_at'])
            
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            # Keep active trades and recent completed trades
            df_clean = df[
                (df['status'] == 'active') | 
                (df['suggested_at'] > cutoff_date)
            ]
            
            removed_count = len(df) - len(df_clean)
            
            if removed_count > 0:
                df_clean.to_csv(self.trade_log_file, index=False)
                logger.info(f"🧹 Cleaned up {removed_count} old trades")
            
        except Exception as e:
            logger.error(f"❌ Error cleaning up trades: {e}")

# Global instance
performance_tracker = PerformanceTracker()

# Auto-start monitoring when module is imported
def initialize_performance_tracking():
    """Initialize and start performance tracking"""
    try:
        performance_tracker.start_monitoring()
        logger.info("✅ Performance tracking initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize performance tracking: {e}")

# Start monitoring automatically
initialize_performance_tracking()