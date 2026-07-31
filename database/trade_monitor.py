"""
Enhanced trade monitoring system with real-time tracking and automated verification
Supports graceful error handling and comprehensive status updates
"""

import os
import pandas as pd
import logging
import time
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict
import schedule

from config.settings import config
from .trade_verifier import trade_verifier
from .winrate import update_winrate_stats

logger = logging.getLogger(__name__)

class TradeMonitor:
    """Enhanced trade monitoring with automated verification"""
    
    def __init__(self):
        self.is_running = False
        self.monitor_thread = None
        self.verification_interval = config.VERIFICATION_INTERVAL_MINUTES
        self.last_verification = None
        self.monitored_trades = []
        
    def load_active_trades(self) -> pd.DataFrame:
        """Load trades that need monitoring"""
        try:
            if not os.path.exists(config.TRADE_LOG_FILE):
                logger.info("📝 No trade log file found")
                return pd.DataFrame()
            
            df = pd.read_csv(config.TRADE_LOG_FILE)
            
            if df.empty:
                logger.info("📝 Trade log file is empty")
                return pd.DataFrame()
            
            # Convert timestamp columns
            time_columns = ['suggested_at', 'expires_at', 'grace_until']
            for col in time_columns:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], utc=True)
            
            # Filter for active trades
            now = datetime.now(timezone.utc)
            active_trades = df[
                (df['status'] == 'ongoing') & 
                (df['result'] == 'pending') &
                (df['grace_until'] > now)
            ].copy()
            
            logger.info(f"📊 Found {len(active_trades)} active trades")
            return active_trades
            
        except Exception as e:
            logger.error(f"❌ Error loading active trades: {e}")
            return pd.DataFrame()
    
    def get_expired_trades(self) -> pd.DataFrame:
        """Get trades that have passed their grace period"""
        try:
            if not os.path.exists(config.TRADE_LOG_FILE):
                return pd.DataFrame()
            
            df = pd.read_csv(config.TRADE_LOG_FILE)
            
            if df.empty:
                return pd.DataFrame()
            
            # Convert timestamps
            df['grace_until'] = pd.to_datetime(df['grace_until'], utc=True)
            
            # Filter for expired ongoing trades
            now = datetime.now(timezone.utc)
            expired_trades = df[
                (df['status'] == 'ongoing') & 
                (df['grace_until'] <= now)
            ].copy()
            
            return expired_trades
            
        except Exception as e:
            logger.error(f"❌ Error getting expired trades: {e}")
            return pd.DataFrame()
    
    def update_trade_status(self, trade_id: int, status: str, result: str, 
                           exit_price: Optional[float] = None, 
                           exit_time: Optional[str] = None) -> bool:
        """Update trade status in the log file"""
        try:
            df = pd.read_csv(config.TRADE_LOG_FILE)
            
            if trade_id not in df.index:
                logger.error(f"❌ Trade ID {trade_id} not found")
                return False
            
            # Update the trade
            df.loc[trade_id, 'status'] = status
            df.loc[trade_id, 'result'] = result
            
            if exit_price is not None:
                df.loc[trade_id, 'exit_price'] = exit_price
            
            if exit_time is not None:
                df.loc[trade_id, 'exit_time'] = exit_time
            else:
                df.loc[trade_id, 'exit_time'] = datetime.now(timezone.utc).isoformat()
            
            # Save back to file
            df.to_csv(config.TRADE_LOG_FILE, index=False)
            
            logger.info(f"✅ Updated trade {trade_id}: {status} - {result}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to update trade status: {e}")
            return False
    
    def verify_active_trade(self, trade: pd.Series) -> Optional[Dict]:
        """Verify a single active trade"""
        try:
            logger.debug(f"🔍 Verifying {trade['symbol']}...")
            
            # Verify the trade using trade_verifier
            result, hit_price, hit_time = trade_verifier.verify_trade_result(
                symbol=trade['symbol'],
                entry=trade['entry'],
                stoploss=trade['stoploss'],
                tp1=trade['tp1'],
                tp2=trade['tp2'],
                tp3=trade['tp3'],
                direction=trade['direction'],
                start_time=trade['suggested_at'].isoformat(),
                end_time=datetime.now(timezone.utc).isoformat()
            )
            
            # If trade hit a target or stop loss
            if result not in ["TIMEOUT", "ERROR"]:
                logger.info(f"🎯 Trade hit for {trade['symbol']}: {result}")
                return {
                    'trade_id': trade.name,
                    'symbol': trade['symbol'],
                    'status': 'finished',
                    'result': result,
                    'exit_price': hit_price,
                    'exit_time': hit_time
                }
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error verifying trade {trade['symbol']}: {e}")
            return None
    
    def process_expired_trades(self):
        """Process trades that have exceeded their grace period"""
        try:
            expired_trades = self.get_expired_trades()
            
            if expired_trades.empty:
                return
            
            logger.info(f"⏰ Processing {len(expired_trades)} expired trades")
            
            for _, trade in expired_trades.iterrows():
                # Final verification for expired trades
                result, exit_price, exit_time = trade_verifier.verify_trade_result(
                    symbol=trade['symbol'],
                    entry=trade['entry'],
                    stoploss=trade['stoploss'],
                    tp1=trade['tp1'],
                    tp2=trade['tp2'],
                    tp3=trade['tp3'],
                    direction=trade['direction'],
                    start_time=trade['suggested_at'].isoformat(),
                    end_time=trade['grace_until'].isoformat()
                )
                
                # If still no hit, mark as tie
                if result in ["TIMEOUT", "ERROR"]:
                    result = "Tie"
                    exit_price = trade_verifier.get_current_price(trade['symbol'])
                    exit_time = datetime.now(timezone.utc).isoformat()
                
                # Update trade status
                self.update_trade_status(
                    trade_id=trade.name,
                    status='finished',
                    result=result,
                    exit_price=exit_price,
                    exit_time=exit_time
                )
                
                # Update winrate stats
                update_winrate_stats(
                    symbol=trade['symbol'],
                    entry=trade['entry'],
                    stoploss=trade['stoploss'],
                    tp1=trade['tp1'],
                    tp2=trade['tp2'],
                    tp3=trade['tp3'],
                    timeframe=trade['timeframe'],
                    suggested_at=trade['suggested_at'].isoformat(),
                    result=result,
                    result_time=exit_time,
                    direction=trade['direction'],
                    exit_price=exit_price
                )
                
        except Exception as e:
            logger.error(f"❌ Error processing expired trades: {e}")
    
    def monitor_cycle(self):
        """Single monitoring cycle"""
        try:
            logger.debug("🔄 Starting monitor cycle")
            
            # Process expired trades first
            self.process_expired_trades()
            
            # Load active trades
            active_trades = self.load_active_trades()
            
            if active_trades.empty:
                logger.debug("📝 No active trades to monitor")
                return
            
            logger.info(f"👀 Monitoring {len(active_trades)} active trades")
            
            # Verify each active trade
            for _, trade in active_trades.iterrows():
                verification_result = self.verify_active_trade(trade)
                
                if verification_result:
                    # Update trade status
                    self.update_trade_status(
                        trade_id=verification_result['trade_id'],
                        status=verification_result['status'],
                        result=verification_result['result'],
                        exit_price=verification_result['exit_price'],
                        exit_time=verification_result['exit_time']
                    )
                    
                    # Update winrate stats
                    update_winrate_stats(
                        symbol=trade['symbol'],
                        entry=trade['entry'],
                        stoploss=trade['stoploss'],
                        tp1=trade['tp1'],
                        tp2=trade['tp2'],
                        tp3=trade['tp3'],
                        timeframe=trade['timeframe'],
                        suggested_at=trade['suggested_at'].isoformat(),
                        result=verification_result['result'],
                        result_time=verification_result['exit_time'],
                        direction=trade['direction'],
                        exit_price=verification_result['exit_price']
                    )
            
            self.last_verification = datetime.now(timezone.utc)
            logger.debug("✅ Monitor cycle completed")
            
        except Exception as e:
            logger.error(f"❌ Error in monitor cycle: {e}")
    
    def start_monitoring(self, interval_minutes: Optional[int] = None):
        """Start automated monitoring"""
        if self.is_running:
            logger.warning("⚠️ Monitor already running")
            return
        
        if interval_minutes:
            self.verification_interval = interval_minutes
        
        logger.info(f"🚀 Starting trade monitor (interval: {self.verification_interval} minutes)")
        
        def monitor_loop():
            self.is_running = True
            
            while self.is_running:
                try:
                    self.monitor_cycle()
                    time.sleep(self.verification_interval * 60)
                except KeyboardInterrupt:
                    logger.info("⏹️ Monitor stopped by user")
                    break
                except Exception as e:
                    logger.error(f"❌ Error in monitor loop: {e}")
                    time.sleep(60)  # Wait 1 minute before retrying
        
        self.monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        logger.info("✅ Trade monitor started")
    
    def stop_monitoring(self):
        """Stop automated monitoring"""
        if not self.is_running:
            logger.warning("⚠️ Monitor not running")
            return
        
        logger.info("⏹️ Stopping trade monitor...")
        self.is_running = False
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=10)
        
        logger.info("✅ Trade monitor stopped")
    
    def get_monitor_status(self) -> Dict:
        """Get current monitor status"""
        active_trades = self.load_active_trades()
        
        return {
            'is_running': self.is_running,
            'verification_interval': self.verification_interval,
            'last_verification': self.last_verification,
            'active_trades_count': len(active_trades),
            'monitored_symbols': active_trades['symbol'].tolist() if not active_trades.empty else []
        }
    
    def manual_verify_all(self):
        """Manually verify all active trades"""
        logger.info("🔍 Manual verification of all active trades")
        self.monitor_cycle()

# Global instance
trade_monitor = TradeMonitor()

# Backward compatibility
def monitor_trades():
    """Backward compatibility function"""
    trade_monitor.start_monitoring()