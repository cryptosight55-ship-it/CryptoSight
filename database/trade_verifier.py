"""
Enhanced trade verification system with robust price data handling
Supports timezone-aware verification and comprehensive error handling
"""

import time
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timezone, timedelta
from typing import Tuple, Optional, Dict
import ccxt

from config.settings import config
from data.fetcher import get_data_fetcher

logger = logging.getLogger(__name__)

class TradeVerifier:
    """Enhanced trade verification with comprehensive price analysis"""
    
    def __init__(self):
        self.exchange = ccxt.binance()
        self.price_cache = {}
        self.cache_ttl = 60  # Cache prices for 1 minute
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price with caching"""
        try:
            current_time = datetime.now(timezone.utc).timestamp()
            
            # Check cache
            if symbol in self.price_cache:
                cached_price, cached_time = self.price_cache[symbol]
                if current_time - cached_time < self.cache_ttl:
                    return cached_price
            
            # Fetch fresh price
            ticker = self.exchange.fetch_ticker(symbol)
            last_price = ticker.get('last')
            close_price = ticker.get('close')
            price = float(last_price if last_price is not None else close_price if close_price is not None else 0.0)
            
            if price > 0:
                # Update cache
                self.price_cache[symbol] = (price, current_time)
                return price
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting current price for {symbol}: {e}")
            return None
    
    def normalize_timestamp(self, timestamp_str: str) -> datetime:
        """Normalize timestamp string to UTC datetime"""
        try:
            # Parse timestamp
            dt = pd.to_datetime(timestamp_str)
            
            # If timezone-naive, assume UTC
            if dt.tzinfo is None:
                dt = dt.tz_localize('UTC')
            else:
                # Convert to UTC if in different timezone
                dt = dt.tz_convert('UTC')
            
            return dt
            
        except Exception as e:
            logger.error(f"❌ Error normalizing timestamp {timestamp_str}: {e}")
            # Fallback to current time
            return datetime.now(timezone.utc)
    
    def fetch_price_history(self, symbol: str, start_time: str, end_time: str) -> Optional[pd.DataFrame]:
        """Fetch price history for verification period"""
        try:
            start_dt = self.normalize_timestamp(start_time)
            end_dt = self.normalize_timestamp(end_time)
            
            # Ensure we have reasonable time range
            time_diff = end_dt - start_dt
            if time_diff.total_seconds() < 0:
                logger.error(f"❌ Invalid time range: end before start")
                return None
            
            if time_diff.total_seconds() > 30 * 24 * 3600:  # 30 days max
                logger.warning(f"⚠️ Time range too large, limiting to 30 days")
                start_dt = end_dt - timedelta(days=30)
            
            # Convert to milliseconds
            since_ms = int(start_dt.timestamp() * 1000)
            until_ms = int(end_dt.timestamp() * 1000)
            
            logger.debug(f"📊 Fetching price history for {symbol}: {start_dt} to {end_dt}")
            
            # Fetch OHLCV data
            all_ohlcv = []
            current_since = since_ms
            
            while current_since < until_ms:
                try:
                    ohlcv = self.exchange.fetch_ohlcv(
                        symbol, 
                        timeframe='1m', 
                        since=current_since, 
                        limit=1000
                    )
                    
                    if not ohlcv:
                        break
                    
                    # Filter candles within our time range
                    filtered_ohlcv = [
                        candle for candle in ohlcv 
                        if since_ms <= candle[0] <= until_ms
                    ]
                    
                    all_ohlcv.extend(filtered_ohlcv)
                    
                    # Update since for next batch
                    if ohlcv:
                        current_since = ohlcv[-1][0] + 1
                    else:
                        break
                    
                    # Prevent infinite loops
                    if len(all_ohlcv) > 50000:  # ~35 days of 1m candles
                        logger.warning("⚠️ Price history fetch limit reached")
                        break
                        
                except ccxt.RateLimitExceeded:
                    logger.warning("⏰ Rate limit hit, waiting...")
                    time.sleep(2)
                    continue
                except Exception as e:
                    logger.error(f"❌ Error fetching batch: {e}")
                    break
            
            if all_ohlcv:
                df = pd.DataFrame(
                    all_ohlcv,
                    columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
                )
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
                
                # Remove duplicates and sort
                df = df.drop_duplicates(subset='timestamp', keep='first')
                df = df.sort_values('timestamp').reset_index(drop=True)
                
                logger.debug(f"✅ Fetched {len(df)} price candles")
                return df
            else:
                logger.warning(f"⚠️ No price data found for {symbol}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error fetching price history for {symbol}: {e}")
            return None
    
    def analyze_price_action(self, df: pd.DataFrame, entry: float, 
                           stoploss: float, tp1: float, tp2: float, tp3: float,
                           direction: str) -> Tuple[str, Optional[float], Optional[str]]:
        """
        Analyze price action to determine trade result
        
        Returns:
            Tuple of (result, exit_price, exit_time)
        """
        try:
            if df.empty:
                return "ERROR", None, None
            
            direction = direction.upper()
            
            # Analyze each candle for hits
            for _, candle in df.iterrows():
                timestamp = candle['timestamp']
                high_price = candle['high']
                low_price = candle['low']
                
                if direction == "LONG":
                    # Check stop loss first (more important)
                    if low_price <= stoploss:
                        logger.debug(f"🛑 LONG Stop Loss hit: {low_price:.6f} <= {stoploss:.6f}")
                        return "Loss", low_price, timestamp.isoformat()
                    
                    # Check take profits (highest first)
                    if high_price >= tp3:
                        logger.debug(f"✅ LONG TP3 hit: {high_price:.6f} >= {tp3:.6f}")
                        return "TP3", high_price, timestamp.isoformat()
                    elif high_price >= tp2:
                        logger.debug(f"✅ LONG TP2 hit: {high_price:.6f} >= {tp2:.6f}")
                        return "TP2", high_price, timestamp.isoformat()
                    elif high_price >= tp1:
                        logger.debug(f"✅ LONG TP1 hit: {high_price:.6f} >= {tp1:.6f}")
                        return "TP1", high_price, timestamp.isoformat()
                
                elif direction == "SHORT":
                    # Check stop loss first
                    if high_price >= stoploss:
                        logger.debug(f"🛑 SHORT Stop Loss hit: {high_price:.6f} >= {stoploss:.6f}")
                        return "Loss", high_price, timestamp.isoformat()
                    
                    # Check take profits (lowest first)
                    if low_price <= tp3:
                        logger.debug(f"✅ SHORT TP3 hit: {low_price:.6f} <= {tp3:.6f}")
                        return "TP3", low_price, timestamp.isoformat()
                    elif low_price <= tp2:
                        logger.debug(f"✅ SHORT TP2 hit: {low_price:.6f} <= {tp2:.6f}")
                        return "TP2", low_price, timestamp.isoformat()
                    elif low_price <= tp1:
                        logger.debug(f"✅ SHORT TP1 hit: {low_price:.6f} <= {tp1:.6f}")
                        return "TP1", low_price, timestamp.isoformat()
            
            # No targets hit
            logger.debug("⏳ No targets hit during verification period")
            current_price = df['close'].iloc[-1]
            current_time = df['timestamp'].iloc[-1]
            
            return "TIMEOUT", current_price, current_time.isoformat()
            
        except Exception as e:
            logger.error(f"❌ Error analyzing price action: {e}")
            return "ERROR", None, None
    
    def verify_trade_result(self, symbol: str, entry: float, stoploss: float,
                          tp1: float, tp2: float, tp3: float, direction: str,
                          start_time: str, end_time: str) -> Tuple[str, Optional[float], Optional[str]]:
        """
        Main trade verification method
        
        Args:
            symbol: Trading symbol
            entry: Entry price
            stoploss: Stop loss price
            tp1, tp2, tp3: Take profit levels
            direction: Trade direction (LONG/SHORT)
            start_time: Trade start time
            end_time: Trade end time (or current time)
            
        Returns:
            Tuple of (result, hit_price, hit_time)
        """
        logger.info(f"🔍 Verifying {direction} trade for {symbol}")
        logger.debug(f"   Entry: {entry:.6f}, SL: {stoploss:.6f}")
        logger.debug(f"   TP1: {tp1:.6f}, TP2: {tp2:.6f}, TP3: {tp3:.6f}")
        
        try:
            # Validate inputs
            if entry <= 0 or stoploss <= 0 or tp1 <= 0:
                logger.error("❌ Invalid price levels")
                return "ERROR", None, None
            
            # Validate direction-specific price relationships
            direction = direction.upper()
            if direction == "LONG":
                if stoploss >= entry or tp1 <= entry:
                    logger.error(f"❌ Invalid LONG levels: SL={stoploss}, Entry={entry}, TP1={tp1}")
                    return "ERROR", None, None
            elif direction == "SHORT":
                if stoploss <= entry or tp1 >= entry:
                    logger.error(f"❌ Invalid SHORT levels: SL={stoploss}, Entry={entry}, TP1={tp1}")
                    return "ERROR", None, None
            else:
                logger.error(f"❌ Invalid direction: {direction}")
                return "ERROR", None, None
            
            # Fetch price history
            df = self.fetch_price_history(symbol, start_time, end_time)
            if df is None or df.empty:
                logger.warning(f"⚠️ No price data available for {symbol}")
                # Try to get current price as fallback
                current_price = self.get_current_price(symbol)
                if current_price:
                    return "TIMEOUT", current_price, datetime.now(timezone.utc).isoformat()
                else:
                    return "ERROR", None, None
            
            # Analyze price action
            result, hit_price, hit_time = self.analyze_price_action(
                df, entry, stoploss, tp1, tp2, tp3, direction
            )
            
            logger.info(f"📊 Verification result for {symbol}: {result}")
            if hit_price:
                logger.debug(f"   Exit price: {hit_price:.6f}")
            
            return result, hit_price, hit_time
            
        except Exception as e:
            logger.error(f"❌ Trade verification failed for {symbol}: {e}")
            return "ERROR", None, None
    
    def get_trade_performance_summary(self, symbol: str, entry: float, 
                                    current_price: float, direction: str) -> Dict:
        """Get performance summary for an ongoing trade"""
        try:
            direction = direction.upper()
            
            if direction == "LONG":
                pnl_pct = ((current_price - entry) / entry) * 100
            else:  # SHORT
                pnl_pct = ((entry - current_price) / entry) * 100
            
            return {
                'symbol': symbol,
                'direction': direction,
                'entry': entry,
                'current_price': current_price,
                'pnl_pct': round(pnl_pct, 2),
                'pnl_usd': round(pnl_pct, 2),  # Assuming 1 unit position
                'status': 'profit' if pnl_pct > 0 else 'loss' if pnl_pct < 0 else 'neutral'
            }
            
        except Exception as e:
            logger.error(f"❌ Error calculating performance summary: {e}")
            return {}

# Global instance
trade_verifier = TradeVerifier()

# Backward compatibility function
def verify_trade_result(symbol, entry, stoploss, tp1, tp2, tp3, direction, start_time, end_time):
    """Backward compatibility wrapper"""
    return trade_verifier.verify_trade_result(
        symbol, entry, stoploss, tp1, tp2, tp3, direction, start_time, end_time
    )