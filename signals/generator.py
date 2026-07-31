"""
Signal Generation Engine for CryptoSight v2.0 - FIXED VERSION
Now properly analyzes any coin with available market data
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from config.settings import config
from data.fetcher import get_data_fetcher
from indicators.features import feature_engineer
from strategies.ml_model.predictor import model_predictor
from database.performance_tracker import performance_tracker

logger = logging.getLogger(__name__)

class SignalGenerator:
    """
    Advanced signal generation with AI predictions and market filtering
    """
    
    def __init__(self):
        self.predictor = model_predictor
        self.is_initialized = False
        
    def initialize(self) -> bool:
        """Initialize the signal generator with loaded model"""
        try:
            if self.predictor.load_model():
                self.is_initialized = True
                logger.info("✅ Signal generator initialized with AI model")
                return True
            else:
                logger.error("❌ Failed to initialize signal generator - model loading failed")
                return False
        except Exception as e:
            logger.error(f"❌ Signal generator initialization error: {e}")
            return False
    
    def generate_signal(self, symbol: str, timeframe: str, probability_threshold: float = 0.1) -> Optional[Dict]:
        """
        EMERGENCY FIX: Much more lenient signal generation
        """
        if not self.is_initialized:
            logger.warning("⚠️ Signal generator not initialized")
            return None
            
        try:
            # Fetch market data with very flexible requirements
            data = None
            for limit in [500, 300, 200, 100, 50]:
                try:
                    data = get_data_fetcher().fetch_live_data(symbol, timeframe, limit=limit)
                    if data is not None and len(data) >= 20:  # Even more lenient - just 20 candles
                        break
                except:
                    continue
            
            if data is None or len(data) < 20:
                logger.warning(f"⚠️ Insufficient data for {symbol}: {len(data) if data is not None else 0} candles")
                return None
            
            # Extract features
            features = feature_engineer.extract_features(data, timeframe)
            if features.empty:
                return None
            
            # Get prediction
            prediction_result = self.predictor.predict(features.iloc[-1:])
            if prediction_result is None:
                return None
            
            prediction, probability = prediction_result
            
            # EMERGENCY: Much more lenient criteria - use OR instead of AND
            signal_strength = self._calculate_signal_strength(data, prediction, probability)
            
            # Multiple ways to qualify for a signal (OR conditions):
            qualifies = (
                probability >= probability_threshold or                    # AI confidence
                signal_strength >= 0.3 or                                # Market conditions 
                self._has_strong_momentum(data) or                        # Strong price movement
                self._has_high_volume_spike(data) or                     # Volume spike
                (prediction == 1 and probability >= 0.05)               # Any long signal with minimal confidence
            )
            
            if not qualifies:
                return None
            
            # Create signal with adjusted probability if needed
            adjusted_probability = max(probability, 0.5) if qualifies else probability
            
            current_price = data['close'].iloc[-1]
            signal_params = self._calculate_signal_parameters(current_price, prediction, timeframe, data)
            
            signal = {
                'symbol': symbol,
                'timeframe': timeframe,
                'direction': 'LONG' if prediction == 1 else 'SHORT',
                'prediction': int(prediction),
                'probability': float(adjusted_probability),
                'original_probability': float(probability),
                'signal_strength': signal_strength,
                'current_price': float(current_price),
                'entry': signal_params['entry'],
                'stop_loss': signal_params['stop_loss'],
                'take_profit_1': signal_params['tp1'],
                'take_profit_2': signal_params['tp2'],
                'take_profit_3': signal_params['tp3'],
                'timestamp': datetime.now(timezone.utc),
                'duration_hours': config.get_timeframe_setting(timeframe, 'duration_hours', 24),
                'volatility': self._calculate_volatility(data),
                'data_points': len(data),
                'qualification_reason': self._get_qualification_reason(probability, signal_strength, data)
            }
            
            logger.info(f"🎯 Generated {signal['direction']} signal for {symbol} "
                    f"(P: {probability:.3f}→{adjusted_probability:.3f}, S: {signal_strength:.2f})")
            
            return signal
            
        except Exception as e:
            logger.error(f"❌ Signal generation error for {symbol}: {e}")
            return None

    def _calculate_signal_strength(self, data: pd.DataFrame, prediction: int, probability: float) -> float:
        """Calculate overall signal strength from multiple factors"""
        try:
            strength = 0.0
            
            # Factor 1: AI Probability (0-0.3)
            strength += min(probability * 0.6, 0.3)
            
            # Factor 2: Volume (0-0.2)
            recent_volume = data['volume'].tail(5).mean()
            avg_volume = data['volume'].tail(20).mean()
            if avg_volume > 0:
                volume_ratio = recent_volume / avg_volume
                strength += min(volume_ratio * 0.1, 0.2)
            
            # Factor 3: Volatility (0-0.2)
            volatility = self._calculate_volatility(data)
            if 1 <= volatility <= 20:  # Sweet spot
                strength += 0.2
            elif volatility > 0:
                strength += 0.1
            
            # Factor 4: Momentum (0-0.3)
            momentum = abs(self._calculate_momentum(data))
            if momentum > 5:
                strength += 0.3
            elif momentum > 2:
                strength += 0.2
            elif momentum > 0.5:
                strength += 0.1
            
            return min(strength, 1.0)
            
        except:
            return probability

    def _has_strong_momentum(self, data: pd.DataFrame) -> bool:
        """Check for strong price momentum"""
        try:
            momentum = abs(self._calculate_momentum(data))
            return momentum > 3.0  # 3% movement
        except:
            return False

    def _has_high_volume_spike(self, data: pd.DataFrame) -> bool:
        """Check for volume spike"""
        try:
            recent_volume = data['volume'].tail(3).mean()
            avg_volume = data['volume'].tail(20).mean()
            return recent_volume > (avg_volume * 1.5) if avg_volume > 0 else False
        except:
            return False

    def _get_qualification_reason(self, probability: float, signal_strength: float, data: pd.DataFrame) -> str:
        """Get reason why signal qualified"""
        reasons = []
        
        if probability >= 0.1:
            reasons.append(f"AI_CONF({probability:.3f})")
        if signal_strength >= 0.3:
            reasons.append(f"STRENGTH({signal_strength:.2f})")
        if self._has_strong_momentum(data):
            reasons.append("MOMENTUM")
        if self._has_high_volume_spike(data):
            reasons.append("VOLUME")
        
        return "|".join(reasons) if reasons else "MINIMAL"

    def scan_multiple_symbols(self, symbols: List[str], timeframes: List[str], 
                            max_signals: int = 20, probability_threshold: float = 0.05) -> List[Dict]:
        """EMERGENCY SCAN: Very lenient signal detection"""
        if not self.is_initialized:
            return []
        
        signals = []
        processed_count = 0
        successful_scans = 0
        
        logger.info(f"🔍 EMERGENCY SCAN: Looking for ANY tradeable signals...")
        
        signal = None  # Initialize signal variable
        
        for symbol in symbols:
            for timeframe in timeframes:
                try:
                    processed_count += 1
                    signal = self.generate_signal(symbol, timeframe, probability_threshold)
                    
                    if signal:
                        signals.append(signal)
                        successful_scans += 1
                        
                        # Log signal for performance tracking
                        performance_tracker.log_signal(signal)
                        
                        logger.info(f"✅ Signal #{len(signals)}: {signal['symbol']} {signal['direction']} "
                                f"(P: {signal['probability']:.3f}, Reason: {signal['qualification_reason']})")
                    
                    if len(signals) >= max_signals:
                        break
                        
                    import time
                    time.sleep(0.05)  # Faster scanning
                        
                except Exception as e:
                    logger.error(f"❌ Error scanning {symbol} {timeframe}: {e}")
                    continue
            
            if len(signals) >= max_signals:
                break
        
        # Sort by signal strength and probability
        signals.sort(key=lambda x: (x['signal_strength'], x['probability']), reverse=True)
        
        logger.info(f"🔍 EMERGENCY SCAN COMPLETE: {len(signals)} signals from {processed_count} combinations")
        logger.info(f"📊 Success rate: {successful_scans}/{processed_count} ({(successful_scans/processed_count)*100:.1f}%)")
        
        return signals[:max_signals]
    
    def _passes_relaxed_market_filter(self, data: pd.DataFrame, symbol: str) -> bool:
        """
        Apply very relaxed market condition filters to allow more signals
        """
        try:
            # Only filter out completely dead coins or extreme cases
            
            # 1. Basic volume check - ensure there's some trading activity
            recent_volume = data['volume'].tail(5).mean()
            if recent_volume <= 0:
                logger.debug(f"🔍 {symbol} filtered: zero volume")
                return False
            
            # 2. Price movement check - ensure price isn't completely static
            price_std = data['close'].tail(20).std()
            if price_std == 0:
                logger.debug(f"🔍 {symbol} filtered: no price movement")
                return False
            
            # 3. Extreme volatility check - filter out obvious pump and dumps
            volatility = self._calculate_volatility(data)
            if volatility > 100:  # More than 100% volatility might be manipulation
                logger.debug(f"🔍 {symbol} filtered: extreme volatility {volatility:.1f}%")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Market filter error for {symbol}: {e}")
            return True  # Pass by default if error
    
    def _calculate_volatility(self, data: pd.DataFrame) -> float:
        """Calculate recent volatility percentage"""
        try:
            available_periods = min(20, len(data) - 1)
            if available_periods < 2:
                return 0.0
                
            returns = data['close'].pct_change().tail(available_periods)
            volatility = returns.std() * np.sqrt(available_periods) * 100
            return volatility if not np.isnan(volatility) else 0.0
        except:
            return 0.0
    
    def _calculate_momentum(self, data: pd.DataFrame) -> float:
        """Calculate recent momentum percentage"""
        try:
            lookback = min(5, len(data) - 1)
            if lookback < 1:
                return 0.0
                
            current = data['close'].iloc[-1]
            previous = data['close'].iloc[-(lookback + 1)]
            momentum = ((current - previous) / previous) * 100
            return momentum if not np.isnan(momentum) else 0.0
        except:
            return 0.0
    
    def _calculate_signal_parameters(self, current_price: float, prediction: int, 
                                   timeframe: str, data: pd.DataFrame) -> Dict:
        """
        Calculate signal parameters based on timeframe and volatility
        """
        try:
            # Get timeframe-specific settings with fallbacks
            profit_target_pct = config.get_timeframe_setting(timeframe, 'profit_target_pct', 5.0) or 5.0
            stop_loss_pct = config.get_timeframe_setting(timeframe, 'stop_loss_pct', 2.5) or 2.5
            
            # Calculate dynamic adjustments based on volatility
            volatility = self._calculate_volatility(data)
            volatility_multiplier = max(0.5, min(2.0, volatility / 5.0))
            
            # Adjust targets
            adjusted_profit = profit_target_pct * volatility_multiplier
            adjusted_stop = stop_loss_pct * volatility_multiplier
            
            if prediction == 1:  # LONG
                entry = current_price
                stop_loss = entry * (1 - adjusted_stop / 100)
                tp1 = entry * (1 + adjusted_profit * 0.4 / 100)
                tp2 = entry * (1 + adjusted_profit * 0.7 / 100)
                tp3 = entry * (1 + adjusted_profit / 100)
            else:  # SHORT
                entry = current_price
                stop_loss = entry * (1 + adjusted_stop / 100)
                tp1 = entry * (1 - adjusted_profit * 0.4 / 100)
                tp2 = entry * (1 - adjusted_profit * 0.7 / 100)
                tp3 = entry * (1 - adjusted_profit / 100)
            
            return {
                'entry': round(entry, 8),
                'stop_loss': round(stop_loss, 8),
                'tp1': round(tp1, 8),
                'tp2': round(tp2, 8),
                'tp3': round(tp3, 8)
            }
            
        except Exception as e:
            logger.error(f"❌ Error calculating signal parameters: {e}")
            # Simple fallback
            if prediction == 1:
                return {
                    'entry': round(current_price, 8),
                    'stop_loss': round(current_price * 0.975, 8),
                    'tp1': round(current_price * 1.02, 8),
                    'tp2': round(current_price * 1.035, 8),
                    'tp3': round(current_price * 1.05, 8)
                }
            else:
                return {
                    'entry': round(current_price, 8),
                    'stop_loss': round(current_price * 1.025, 8),
                    'tp1': round(current_price * 0.98, 8),
                    'tp2': round(current_price * 0.965, 8),
                    'tp3': round(current_price * 0.95, 8)
                }

# Global instance
signal_generator = SignalGenerator()