"""
Enhanced trade scanner with improved filtering, signal generation, and error handling
Supports multiple timeframes and comprehensive market analysis
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Callable, Tuple
import talib
import os

from .config import config
from .data_fetcher import data_fetcher
from .feature_engineer import feature_engineer
from .predictor import model_predictor
from .alert import send_alert

logger = logging.getLogger(__name__)

class TradeLevelCalculator:
    """Calculate dynamic trade levels based on market conditions"""
    
    @staticmethod
    def calculate_volatility_based_levels(df: pd.DataFrame, timeframe: str) -> Dict[str, float]:
        """Calculate trade levels based on volatility (ATR)"""
        try:
            # Get timeframe settings
            settings = config.TIMEFRAME_SETTINGS.get(timeframe, config.TIMEFRAME_SETTINGS['1d'])
            
            current_close = df['close'].iloc[-1]
            
            # Calculate ATR for volatility-based adjustments
            atr = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14).iloc[-1]
            atr_pct = (atr / current_close) * 100
            
            # Adjust targets based on volatility
            base_profit = settings['profit_target_pct']
            base_stop = settings['stop_loss_pct']
            
            # Scale based on ATR (higher volatility = wider targets)
            volatility_multiplier = max(0.5, min(2.0, atr_pct / 2.0))
            
            profit_target_pct = base_profit * volatility_multiplier
            stop_loss_pct = base_stop * volatility_multiplier
            
            return {
                'profit_target_pct': profit_target_pct,
                'stop_loss_pct': stop_loss_pct,
                'atr_pct': atr_pct,
                'volatility_multiplier': volatility_multiplier
            }
            
        except Exception as e:
            logger.error(f"❌ Error calculating volatility levels: {e}")
            # Fallback to default settings
            settings = config.TIMEFRAME_SETTINGS.get(timeframe, config.TIMEFRAME_SETTINGS['1d'])
            return {
                'profit_target_pct': settings['profit_target_pct'],
                'stop_loss_pct': settings['stop_loss_pct'],
                'atr_pct': 2.0,
                'volatility_multiplier': 1.0
            }
    
    @staticmethod
    def determine_direction(df: pd.DataFrame) -> str:
        """Determine trade direction based on technical analysis"""
        try:
            # Calculate multiple indicators
            sma_5 = df['close'].tail(5).mean()
            sma_20 = df['close'].tail(20).mean()
            
            ema_12 = talib.EMA(df['close'], timeperiod=12).iloc[-1]
            ema_26 = talib.EMA(df['close'], timeperiod=26).iloc[-1]
            
            rsi = talib.RSI(df['close'], timeperiod=14).iloc[-1]
            
            # Recent momentum
            momentum_5d = (df['close'].iloc[-1] / df['close'].iloc[-5] - 1) * 100
            
            # Volume confirmation
            recent_volume = df['volume'].tail(5).mean()
            avg_volume = df['volume'].tail(20).mean()
            volume_strength = recent_volume / avg_volume if avg_volume > 0 else 1
            
            # Bullish signals
            bullish_signals = sum([
                sma_5 > sma_20,  # Short MA above long MA
                ema_12 > ema_26,  # MACD line positive
                rsi > 50,  # RSI above midline
                momentum_5d > 0,  # Positive momentum
                volume_strength > 1.2  # Above average volume
            ])
            
            # Bearish signals
            bearish_signals = 5 - bullish_signals
            
            # Direction with confidence threshold
            if bullish_signals >= 4:
                return "LONG"
            elif bearish_signals >= 4:
                return "SHORT"
            else:
                # Neutral - prefer LONG for crypto generally
                return "LONG" if bullish_signals >= bearish_signals else "SHORT"
                
        except Exception as e:
            logger.error(f"❌ Error determining direction: {e}")
            return "LONG"  # Default to LONG
    
    @classmethod
    def calculate_trade_levels(cls, df: pd.DataFrame, symbol: str, timeframe: str) -> Dict:
        """
        Calculate comprehensive trade levels
        
        Returns:
            Dict with trade parameters
        """
        try:
            current_close = df['close'].iloc[-1]
            
            # Get volatility-based levels
            levels = cls.calculate_volatility_based_levels(df, timeframe)
            
            # Determine direction
            direction = cls.determine_direction(df)
            
            # Calculate timeframe settings
            settings = config.TIMEFRAME_SETTINGS.get(timeframe, config.TIMEFRAME_SETTINGS['1d'])
            
            # Calculate price levels
            profit_pct = levels['profit_target_pct'] / 100
            stop_pct = levels['stop_loss_pct'] / 100
            
            if direction == "LONG":
                entry = current_close
                stoploss = entry * (1 - stop_pct)
                tp1 = entry * (1 + profit_pct)
                tp2 = entry * (1 + profit_pct * 1.25)
                tp3 = entry * (1 + profit_pct * 1.5)
            else:  # SHORT
                entry = current_close
                stoploss = entry * (1 + stop_pct)
                tp1 = entry * (1 - profit_pct)
                tp2 = entry * (1 - profit_pct * 1.25)
                tp3 = entry * (1 - profit_pct * 1.5)
            
            return {
                'symbol': symbol,
                'direction': direction,
                'entry': round(entry, 8),
                'stoploss': round(stoploss, 8),
                'tp1': round(tp1, 8),
                'tp2': round(tp2, 8),
                'tp3': round(tp3, 8),
                'timeframe': timeframe,
                'duration_hours': settings['duration_hours'],
                'grace_hours': settings['grace_hours'],
                'profit_target_pct': levels['profit_target_pct'],
                'stop_loss_pct': levels['stop_loss_pct'],
                'atr_pct': levels['atr_pct']
            }
            
        except Exception as e:
            logger.error(f"❌ Error calculating trade levels for {symbol}: {e}")
            return {}

class MarketFilter:
    """Advanced market filtering for signal quality"""
    
    @staticmethod
    def volume_filter(df: pd.DataFrame, min_ratio: float = 0.8) -> Tuple[bool, float]:
        """Filter based on volume ratio"""
        try:
            avg_volume = df['volume'].tail(20).mean()
            recent_volume = df['volume'].tail(5).mean()
            volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 0
            
            return volume_ratio >= min_ratio, volume_ratio
            
        except Exception as e:
            logger.error(f"❌ Volume filter error: {e}")
            return False, 0.0
    
    @staticmethod
    def volatility_filter(df: pd.DataFrame, min_vol: float = 0.5, max_vol: float = 25.0) -> Tuple[bool, float]:
        """Filter based on volatility (ATR)"""
        try:
            atr = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14).iloc[-1]
            atr_percent = (atr / df['close'].iloc[-1]) * 100
            
            return min_vol <= atr_percent <= max_vol, atr_percent
            
        except Exception as e:
            logger.error(f"❌ Volatility filter error: {e}")
            return False, 0.0
    
    @staticmethod
    def momentum_filter(df: pd.DataFrame, min_momentum: float = 1.5) -> Tuple[bool, float]:
        """Filter based on recent momentum"""
        try:
            # 5-day momentum
            momentum_5d = (df['close'].iloc[-1] / df['close'].iloc[-5] - 1) * 100
            
            return abs(momentum_5d) >= min_momentum, momentum_5d
            
        except Exception as e:
            logger.error(f"❌ Momentum filter error: {e}")
            return False, 0.0
    
    @staticmethod
    def trend_strength_filter(df: pd.DataFrame, min_strength: float = 0.6) -> Tuple[bool, float]:
        """Filter based on trend strength"""
        try:
            # ADX for trend strength
            adx = talib.ADX(df['high'], df['low'], df['close'], timeperiod=14).iloc[-1]
            
            # Normalize ADX (0-100 scale to 0-1)
            trend_strength = adx / 100
            
            return trend_strength >= min_strength, trend_strength
            
        except Exception as e:
            logger.error(f"❌ Trend strength filter error: {e}")
            return False, 0.0
    
    @classmethod
    def apply_all_filters(cls, df: pd.DataFrame, symbol: str) -> Dict:
        """Apply all market filters and return results"""
        filters = {}
        
        # Volume filter
        vol_pass, vol_ratio = cls.volume_filter(df, config.MIN_VOLUME_RATIO)
        filters['volume'] = {'pass': vol_pass, 'value': vol_ratio}
        
        # Volatility filter
        volat_pass, volat_pct = cls.volatility_filter(df, config.MIN_VOLATILITY_PCT, config.MAX_VOLATILITY_PCT)
        filters['volatility'] = {'pass': volat_pass, 'value': volat_pct}
        
        # Momentum filter
        mom_pass, mom_pct = cls.momentum_filter(df, config.MIN_MOMENTUM_PCT)
        filters['momentum'] = {'pass': mom_pass, 'value': mom_pct}
        
        # Trend strength filter
        trend_pass, trend_strength = cls.trend_strength_filter(df)
        filters['trend_strength'] = {'pass': trend_pass, 'value': trend_strength}
        
        # Overall pass
        all_pass = all(f['pass'] for f in filters.values())
        filters['overall'] = all_pass
        
        return filters

class TradeScanner:
    """Enhanced trade scanner with comprehensive analysis"""
    
    def __init__(self):
        self.stats = {
            'total_scanned': 0,
            'volume_passed': 0,
            'volatility_passed': 0,
            'momentum_passed': 0,
            'trend_passed': 0,
            'ai_passed': 0,
            'final_signals': 0
        }
        self.signals = []
        
        # Ensure model is loaded
        if not model_predictor.is_loaded():
            logger.info("🤖 Loading AI model...")
            if not model_predictor.load_model():
                logger.error("❌ Failed to load AI model")
                raise RuntimeError("AI model not available")
    
    def reset_stats(self):
        """Reset scanning statistics"""
        self.stats = {key: 0 for key in self.stats}
        self.signals = []
    
    def log_trade_signal(self, signal: Dict):
        """Log trade signal to CSV file"""
        try:
            config.ensure_directories()
            
            # Add timestamps
            now = datetime.now(timezone.utc)
            signal.update({
                'suggested_at': now,
                'expires_at': now + timedelta(hours=signal['duration_hours']),
                'grace_until': now + timedelta(hours=signal['duration_hours'] + signal['grace_hours']),
                'status': 'ongoing',
                'result': 'pending',
                'exit_price': None,
                'exit_time': None
            })
            
            # Create DataFrame
            df = pd.DataFrame([signal])
            
            # Check if file exists to determine if header is needed
            file_exists = os.path.exists(config.TRADE_LOG_FILE)
            
            # Append to file
            df.to_csv(config.TRADE_LOG_FILE, mode='a', header=not file_exists, index=False)
            
            logger.info(f"✅ Logged trade signal for {signal['symbol']}")
            
        except Exception as e:
            logger.error(f"❌ Failed to log trade signal: {e}")
    
    def scan_single_symbol(self, symbol: str, timeframe: str, prob_threshold: float) -> Optional[Dict]:
        """
        Scan a single symbol for trading opportunities
        
        Args:
            symbol: Trading symbol (e.g., 'BTC/USDT')
            timeframe: Timeframe for analysis
            prob_threshold: AI probability threshold
            
        Returns:
            Trade signal dict if found, None otherwise
        """
        self.stats['total_scanned'] += 1
        
        try:
            logger.debug(f"🔍 Scanning {symbol} ({timeframe})")
            
            # Fetch market data
            df = data_fetcher.fetch_live_data(symbol, timeframe, limit=500)
            if df is None or len(df) < 100:
                logger.debug(f"❌ Insufficient data for {symbol}")
                return None
            
            # Apply market filters
            filters = MarketFilter.apply_all_filters(df, symbol)
            
            # Log filter results
            if filters['volume']['pass']:
                self.stats['volume_passed'] += 1
                logger.debug(f"  ✅ Volume: {filters['volume']['value']:.2f}")
            else:
                logger.debug(f"  ❌ Volume: {filters['volume']['value']:.2f}")
                return None
            
            if filters['volatility']['pass']:
                self.stats['volatility_passed'] += 1
                logger.debug(f"  ✅ Volatility: {filters['volatility']['value']:.2f}%")
            else:
                logger.debug(f"  ❌ Volatility: {filters['volatility']['value']:.2f}%")
                return None
            
            if filters['momentum']['pass']:
                self.stats['momentum_passed'] += 1
                logger.debug(f"  ✅ Momentum: {filters['momentum']['value']:.2f}%")
            else:
                logger.debug(f"  ❌ Momentum: {filters['momentum']['value']:.2f}%")
                return None
            
            if filters['trend_strength']['pass']:
                self.stats['trend_passed'] += 1
                logger.debug(f"  ✅ Trend: {filters['trend_strength']['value']:.2f}")
            else:
                logger.debug(f"  ❌ Trend: {filters['trend_strength']['value']:.2f}")
                return None
            
            # Extract features for AI prediction
            features = feature_engineer.extract_features(df, timeframe)
            if features.empty:
                logger.debug(f"❌ Feature extraction failed for {symbol}")
                return None
            
            # Get AI prediction
            prediction, probability = model_predictor.predict_breakout(features.iloc[[-1]])
            logger.debug(f"  🤖 AI: Prediction={prediction}, Probability={probability:.3f}")
            
            # Check AI threshold
            if prediction == 1 and probability >= prob_threshold:
                self.stats['ai_passed'] += 1
                
                # Calculate trade levels
                trade_levels = TradeLevelCalculator.calculate_trade_levels(df, symbol, timeframe)
                if not trade_levels:
                    logger.debug(f"❌ Failed to calculate trade levels for {symbol}")
                    return None
                
                # Add AI info
                trade_levels['probability'] = probability
                trade_levels['prediction'] = prediction
                
                # Add filter results for reference
                trade_levels['filters'] = filters
                
                logger.info(f"✅ Signal generated for {symbol}: {trade_levels['direction']} @ {trade_levels['entry']:.6f}")
                self.stats['final_signals'] += 1
                
                return trade_levels
            else:
                logger.debug(f"  ❌ AI threshold not met (prob: {probability:.3f} < {prob_threshold})")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error scanning {symbol}: {e}")
            return None
    
    def scan_trades(self, 
                   num_coins: int = 50, 
                   timeframe: str = "1d", 
                   prob_threshold: float = 0.6,
                   max_signals: int = 3,
                   progress_callback: Optional[Callable] = None) -> pd.DataFrame:
        """
        Main trade scanning function
        
        Args:
            num_coins: Number of coins to scan
            timeframe: Trading timeframe
            prob_threshold: AI probability threshold
            max_signals: Maximum signals to generate
            progress_callback: Optional progress callback function
            
        Returns:
            DataFrame with generated signals
        """
        logger.info(f"🚀 Starting enhanced scan: {num_coins} coins, {timeframe}, threshold {prob_threshold}")
        
        # Reset statistics
        self.reset_stats()
        
        try:
            # Get coins to scan
            coins_to_scan = data_fetcher.get_top_coins(limit=num_coins)
            logger.info(f"📊 Scanning {len(coins_to_scan)} coins")
            
            signals = []
            
            for idx, symbol in enumerate(coins_to_scan, 1):
                # Progress callback
                if progress_callback:
                    progress_callback(idx, len(coins_to_scan), symbol)
                
                # Scan symbol
                signal = self.scan_single_symbol(symbol, timeframe, prob_threshold)
                
                if signal:
                    signals.append(signal)
                    
                    # Log the signal
                    self.log_trade_signal(signal)
                    
                    # Send alert
                    try:
                        send_alert(
                            symbol=signal['symbol'],
                            probability=signal['probability'],
                            entry=signal['entry'],
                            stoploss=signal['stoploss'],
                            tp1=signal['tp1'],
                            tp2=signal['tp2'],
                            tp3=signal['tp3'],
                            direction=signal['direction'],
                            timeframe=signal['timeframe']
                        )
                    except Exception as e:
                        logger.error(f"❌ Failed to send alert for {symbol}: {e}")
                    
                    # Check max signals limit
                    if len(signals) >= max_signals:
                        logger.info(f"🛑 Reached maximum signals limit ({max_signals})")
                        break
            
            # Print statistics
            self.print_scan_statistics()
            
            # Store signals
            self.signals = signals
            
            return pd.DataFrame(signals) if signals else pd.DataFrame()
            
        except Exception as e:
            logger.error(f"❌ Scan failed: {e}")
            return pd.DataFrame()
    
    def print_scan_statistics(self):
        """Print detailed scan statistics"""
        total = self.stats['total_scanned']
        if total == 0:
            return
        
        logger.info("📊 SCAN STATISTICS:")
        logger.info(f"  Total Scanned: {total}")
        logger.info(f"  Volume Filter: {self.stats['volume_passed']}/{total} ({self.stats['volume_passed']/total*100:.1f}%)")
        logger.info(f"  Volatility Filter: {self.stats['volatility_passed']}/{total} ({self.stats['volatility_passed']/total*100:.1f}%)")
        logger.info(f"  Momentum Filter: {self.stats['momentum_passed']}/{total} ({self.stats['momentum_passed']/total*100:.1f}%)")
        logger.info(f"  Trend Filter: {self.stats['trend_passed']}/{total} ({self.stats['trend_passed']/total*100:.1f}%)")
        logger.info(f"  AI Filter: {self.stats['ai_passed']}/{total} ({self.stats['ai_passed']/total*100:.1f}%)")
        logger.info(f"  Final Signals: {self.stats['final_signals']}")

# Global instance
trade_scanner = TradeScanner()

# Backward compatibility function
def scan_trades(num_coins=50, timeframe="1d", prob_threshold=0.6, progress_callback=None):
    """Backward compatibility wrapper"""
    return trade_scanner.scan_trades(num_coins, timeframe, prob_threshold, config.MAX_SIGNALS_PER_SCAN, progress_callback)