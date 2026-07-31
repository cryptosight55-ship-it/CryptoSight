"""
Enhanced AI model predictor with bias correction and improved signal distribution
Fixed for proper LONG/SHORT balance and probability calibration
"""

import joblib
import pandas as pd
import numpy as np
import logging
import os
from typing import Tuple, Optional, List
from config.settings import config

logger = logging.getLogger(__name__)

class ModelPredictor:
    """Enhanced predictor with bias correction and signal balancing"""
    
    def __init__(self):
        self.model = None
        self.feature_names = None
        self.model_path = None
        self.is_calibrated = False
        self.model_info = {}
        self.bias_correction_enabled = True
        self.long_bias_multiplier = 1.8  # Boost LONG signals to counteract training bias
        
    def load_model(self, model_path: Optional[str] = None) -> bool:
        """
        Load AI model with fallback support
        
        Args:
            model_path: Optional custom model path
            
        Returns:
            True if model loaded successfully
        """
        # Determine model path
        if model_path is None:
            primary_model = config.get_model_path(config.MODEL_FILE)
            fallback_model = config.get_model_path(config.FALLBACK_MODEL_FILE)
            
            if os.path.exists(primary_model):
                model_path = primary_model
                logger.info(f"🎯 Using improved model: {config.MODEL_FILE}")
            elif os.path.exists(fallback_model):
                model_path = fallback_model
                logger.warning(f"⚠️ Using fallback model: {config.FALLBACK_MODEL_FILE}")
            else:
                logger.error("❌ No model files found!")
                return False
        
        try:
            # Load model
            self.model = joblib.load(model_path)
            self.model_path = model_path
            
            # Check if model is calibrated
            self.is_calibrated = hasattr(self.model, 'calibrated_classifiers_')
            
            # Load feature names
            feature_names_path = config.get_model_path(config.FEATURE_NAMES_FILE)
            if os.path.exists(feature_names_path):
                self.feature_names = joblib.load(feature_names_path)
                logger.info(f"✅ Loaded {len(self.feature_names)} feature names")
            else:
                logger.warning("⚠️ Feature names file not found, using model features")
                if hasattr(self.model, 'feature_names_in_'):
                    self.feature_names = list(self.model.feature_names_in_)
                elif hasattr(self.model, 'estimator') and hasattr(self.model.estimator, 'feature_names_in_'):
                    self.feature_names = list(self.model.estimator.feature_names_in_)
                else:
                    logger.error("❌ Cannot determine feature names")
                    return False
            
            # Store model info
            self.model_info = {
                'path': model_path,
                'calibrated': self.is_calibrated,
                'num_features': len(self.feature_names),
                'model_type': type(self.model).__name__,
                'bias_correction': self.bias_correction_enabled
            }
            
            logger.info(f"✅ Model loaded successfully: {self.model_info}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to load model from {model_path}: {e}")
            return False
    
    def validate_features(self, features_df: pd.DataFrame) -> bool:
        """Validate feature DataFrame against model requirements"""
        if self.feature_names is None:
            logger.error("❌ Feature names not loaded")
            return False
        
        # Check required features
        missing_features = set(self.feature_names) - set(features_df.columns)
        if missing_features:
            logger.error(f"❌ Missing features: {missing_features}")
            return False
        
        # Check for NaN values
        if features_df[self.feature_names].isnull().any().any():
            logger.warning("⚠️ Features contain NaN values")
        
        # Check for infinite values
        if np.isinf(features_df[self.feature_names]).any().any():
            logger.warning("⚠️ Features contain infinite values")
        
        return True
    
    def prepare_features(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """Prepare features for prediction"""
        if self.feature_names is None:
            logger.error("❌ Feature names not available")
            return pd.DataFrame()
        
        try:
            # Select and order features according to model
            model_features = features_df[self.feature_names].copy()
            
            # Handle missing values
            model_features = model_features.fillna(0)
            
            # Handle infinite values
            model_features = model_features.replace([np.inf, -np.inf], 0)
            
            return model_features
            
        except Exception as e:
            logger.error(f"❌ Feature preparation failed: {e}")
            return pd.DataFrame()
    
    def _apply_bias_correction(self, raw_probabilities: np.ndarray, features_df: pd.DataFrame) -> Tuple[int, float]:
        """
        Apply bias correction to counteract training data imbalance
        
        Args:
            raw_probabilities: Original model probabilities [prob_short, prob_long]
            features_df: Feature data for additional analysis
            
        Returns:
            Corrected prediction and probability
        """
        try:
            prob_short = raw_probabilities[0]
            prob_long = raw_probabilities[1]
            
            # Market momentum analysis
            momentum_features = self._analyze_momentum_features(features_df)
            volatility_signal = self._analyze_volatility_features(features_df)
            trend_strength = self._analyze_trend_features(features_df)
            
            # Bias correction factors
            long_boost = 1.0
            
            # Factor 1: Momentum bias correction
            if momentum_features['positive_momentum']:
                long_boost *= 1.5
            
            # Factor 2: Volatility adjustment  
            if volatility_signal['moderate_volatility']:
                long_boost *= 1.2
            
            # Factor 3: Trend strength
            if trend_strength['bullish_indicators'] > trend_strength['bearish_indicators']:
                long_boost *= 1.3
            
            # Factor 4: Base bias correction for training imbalance
            long_boost *= self.long_bias_multiplier
            
            # Apply corrections
            corrected_prob_long = min(prob_long * long_boost, 0.95)  # Cap at 95%
            corrected_prob_short = 1.0 - corrected_prob_long
            
            # Determine final prediction
            if corrected_prob_long > corrected_prob_short:
                final_prediction = 1
                final_probability = corrected_prob_long
            else:
                final_prediction = 0
                final_probability = corrected_prob_short
            
            # Ensure minimum confidence for any signal
            if final_probability < 0.1:
                final_probability = 0.1
            
            logger.debug(f"Bias correction: Original={prob_long:.3f}, Boosted={corrected_prob_long:.3f}, "
                        f"Final={final_prediction}({final_probability:.3f})")
            
            return final_prediction, final_probability
            
        except Exception as e:
            logger.error(f"Error in bias correction: {e}")
            # Fallback to original with minimal boost
            return (1 if raw_probabilities[1] > 0.4 else 0), max(max(raw_probabilities), 0.1)
    
    def _analyze_momentum_features(self, features_df: pd.DataFrame) -> dict:
        """Analyze momentum-related features"""
        try:
            features = features_df.iloc[0]  # Single row
            
            # Price momentum indicators
            rsi_bullish = features.get('rsi_14', 50) > 50
            macd_bullish = features.get('macd_hist', 0) > 0
            momentum_positive = features.get('mom_10', 0) > 0
            
            # Moving average trends
            sma_trend = features.get('close_sma_20_ratio', 1.0) > 1.0
            ema_trend = features.get('close_ema_20_ratio', 1.0) > 1.0
            
            positive_momentum = sum([rsi_bullish, macd_bullish, momentum_positive, sma_trend, ema_trend]) >= 3
            
            return {
                'positive_momentum': positive_momentum,
                'rsi_bullish': rsi_bullish,
                'macd_bullish': macd_bullish,
                'trend_bullish': sma_trend and ema_trend
            }
        except:
            return {'positive_momentum': False, 'rsi_bullish': False, 'macd_bullish': False, 'trend_bullish': False}
    
    def _analyze_volatility_features(self, features_df: pd.DataFrame) -> dict:
        """Analyze volatility-related features"""
        try:
            features = features_df.iloc[0]
            
            atr_pct = features.get('atr_pct', 2.0)
            bb_position = features.get('bb_position', 0.5)
            
            # Moderate volatility is good for trading
            moderate_volatility = 1.0 <= atr_pct <= 10.0
            bb_favorable = 0.2 <= bb_position <= 0.8
            
            return {
                'moderate_volatility': moderate_volatility,
                'bb_favorable': bb_favorable,
                'atr_pct': atr_pct
            }
        except:
            return {'moderate_volatility': True, 'bb_favorable': True, 'atr_pct': 2.0}
    
    def _analyze_trend_features(self, features_df: pd.DataFrame) -> dict:
        """Analyze trend strength features"""
        try:
            features = features_df.iloc[0]
            
            # Bullish indicators
            bullish_count = 0
            if features.get('sma_5_20_cross', 0) == 1:
                bullish_count += 1
            if features.get('ema_12_26_cross', 0) == 1:
                bullish_count += 1  
            if features.get('sar_trend', 0) == 1:
                bullish_count += 1
            if features.get('total_bullish_patterns', 0) > features.get('total_bearish_patterns', 0):
                bullish_count += 1
            if features.get('aroon_osc', 0) > 0:
                bullish_count += 1
            
            # Bearish indicators
            bearish_count = 0
            if features.get('rsi_overbought', 0) == 1:
                bearish_count += 1
            if features.get('total_bearish_patterns', 0) > features.get('total_bullish_patterns', 0):
                bearish_count += 1
            if features.get('dist_to_resistance_20', 0.1) < 0.02:  # Near resistance
                bearish_count += 1
            
            return {
                'bullish_indicators': bullish_count,
                'bearish_indicators': bearish_count,
                'net_bullish': bullish_count - bearish_count
            }
        except:
            return {'bullish_indicators': 0, 'bearish_indicators': 0, 'net_bullish': 0}
    
    def predict(self, features_df: pd.DataFrame) -> Tuple[int, float]:
        """
        Backward compatibility method for predict
        """
        return self.predict_breakout(features_df)
    
    def predict_breakout(self, features_df: pd.DataFrame) -> Tuple[int, float]:
        """
        Predict breakout probability with bias correction
        
        Args:
            features_df: DataFrame with features (single row)
            
        Returns:
            Tuple of (prediction, probability)
        """
        if self.model is None:
            logger.error("❌ Model not loaded")
            return 0, 0.0
        
        try:
            # Validate and prepare features
            if not self.validate_features(features_df):
                logger.error("❌ Feature validation failed")
                return 0, 0.0
            
            prepared_features = self.prepare_features(features_df)
            if prepared_features.empty:
                logger.error("❌ Feature preparation failed")
                return 0, 0.0
            
            # Get raw model prediction
            raw_prediction = self.model.predict(prepared_features)[0]
            
            # Get raw probabilities
            if hasattr(self.model, 'predict_proba'):
                raw_probabilities = self.model.predict_proba(prepared_features)[0]
            else:
                # Fallback for models without probability support
                raw_probabilities = np.array([1-float(raw_prediction), float(raw_prediction)])
                logger.warning("⚠️ Model doesn't support probability prediction")
            
            # Apply bias correction if enabled
            if self.bias_correction_enabled:
                final_prediction, final_probability = self._apply_bias_correction(raw_probabilities, prepared_features)
            else:
                final_prediction = int(raw_prediction)
                final_probability = float(np.clip(raw_probabilities[1] if raw_prediction == 1 else raw_probabilities[0], 0.0, 1.0))
            
            logger.debug(f"🎯 Raw: {raw_prediction}({raw_probabilities[1]:.3f}), "
                        f"Final: {final_prediction}({final_probability:.3f})")
            
            return final_prediction, final_probability
            
        except Exception as e:
            logger.error(f"❌ Prediction failed: {e}")
            return 0, 0.0
    
    def predict_batch(self, features_df: pd.DataFrame) -> Tuple[List[int], List[float]]:
        """
        Predict for multiple samples with bias correction
        """
        if self.model is None:
            logger.error("❌ Model not loaded")
            return [], []
        
        try:
            if not self.validate_features(features_df):
                logger.error("❌ Feature validation failed")
                return [], []
            
            prepared_features = self.prepare_features(features_df)
            if prepared_features.empty:
                logger.error("❌ Feature preparation failed")
                return [], []
            
            predictions = []
            probabilities = []
            
            # Process each row individually for bias correction
            for idx in range(len(prepared_features)):
                single_row = prepared_features.iloc[idx:idx+1]
                pred, prob = self.predict_breakout(single_row)
                predictions.append(pred)
                probabilities.append(prob)
            
            logger.info(f"🎯 Batch prediction: {len(predictions)} samples")
            return predictions, probabilities
            
        except Exception as e:
            logger.error(f"❌ Batch prediction failed: {e}")
            return [], []
    
    def set_bias_correction(self, enabled: bool, long_multiplier: float = 1.8):
        """Enable/disable bias correction"""
        self.bias_correction_enabled = enabled
        self.long_bias_multiplier = long_multiplier
        logger.info(f"Bias correction: {'enabled' if enabled else 'disabled'}, "
                   f"LONG multiplier: {long_multiplier}")
    
    def get_model_info(self) -> dict:
        """Get information about the loaded model"""
        return self.model_info.copy()
    
    def is_loaded(self) -> bool:
        """Check if model is loaded and ready"""
        return self.model is not None and self.feature_names is not None

# Global instance
model_predictor = ModelPredictor()

# Convenience functions for backward compatibility
def load_model():
    """Load model - backward compatibility function"""
    success = model_predictor.load_model()
    if success:
        return model_predictor.model, model_predictor.feature_names
    else:
        raise FileNotFoundError("Failed to load model")

def predict_breakout(features_df, model):
    """Predict breakout - backward compatibility function"""
    if not model_predictor.is_loaded():
        model_predictor.load_model()
    
    return model_predictor.predict_breakout(features_df)