"""
Enhanced feature engineering pipeline with robust technical analysis
Supports multiple timeframes and comprehensive indicator calculation
"""

import pandas as pd
import numpy as np
import talib
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class FeatureEngineer:
    """Enhanced feature engineering with comprehensive technical indicators"""
    
    def __init__(self):
        self.required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        
    def validate_data(self, df: pd.DataFrame) -> bool:
        """Validate input data format and quality"""
        try:
            # Check required columns
            missing_cols = set(self.required_columns) - set(df.columns)
            if missing_cols:
                logger.error(f"❌ Missing required columns: {missing_cols}")
                return False
            
            # Check data length
            if len(df) < 50:
                logger.error(f"❌ Insufficient data: {len(df)} rows (need at least 50)")
                return False
            
            # Check for data quality issues
            price_cols = ['open', 'high', 'low', 'close']
            if df[price_cols].isnull().any().any():
                logger.warning("⚠️ Price data contains NaN values")
            
            if (df[price_cols] <= 0).any().any():
                logger.warning("⚠️ Price data contains zero or negative values")
            
            # Validate price relationships
            invalid_highs = (df['high'] < df[['open', 'close']].max(axis=1)).sum()
            invalid_lows = (df['low'] > df[['open', 'close']].min(axis=1)).sum()
            
            if invalid_highs > 0 or invalid_lows > 0:
                logger.warning(f"⚠️ Invalid OHLC relationships: {invalid_highs} highs, {invalid_lows} lows")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Data validation error: {e}")
            return False
    
    def extract_basic_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract basic OHLCV and candlestick features"""
        features = pd.DataFrame(index=df.index)
        
        # Basic OHLCV
        features['open'] = df['open']
        features['high'] = df['high']
        features['low'] = df['low']
        features['close'] = df['close']
        features['volume'] = df['volume']
        
        # Price range and body features
        features['price_range'] = df['high'] - df['low']
        features['body_size'] = abs(df['close'] - df['open'])
        features['upper_shadow'] = df['high'] - np.maximum(df['open'], df['close'])
        features['lower_shadow'] = np.minimum(df['open'], df['close']) - df['low']
        
        # Percentage features
        features['range_pct'] = (features['price_range'] / df['close']) * 100
        features['body_pct'] = (features['body_size'] / df['close']) * 100
        features['upper_shadow_pct'] = (features['upper_shadow'] / df['close']) * 100
        features['lower_shadow_pct'] = (features['lower_shadow'] / df['close']) * 100
        features['close_position'] = (df['close'] - df['low']) / (df['high'] - df['low'])
        
        # Returns
        features['return_1'] = df['close'].pct_change(1)
        features['return_3'] = df['close'].pct_change(3)
        features['return_5'] = df['close'].pct_change(5)
        features['return_10'] = df['close'].pct_change(10)
        features['return_20'] = df['close'].pct_change(20)
        features['log_return'] = np.log(df['close'] / df['close'].shift(1))
        
        # Volume features
        features['volume_sma_10'] = df['volume'].rolling(10).mean()
        features['volume_sma_20'] = df['volume'].rolling(20).mean()
        features['volume_ratio'] = df['volume'] / features['volume_sma_20']
        features['volume_return'] = df['volume'].pct_change(1)
        features['price_volume'] = df['close'] * df['volume']
        
        # VWAP
        features['vwap_5'] = (df['close'] * df['volume']).rolling(5).sum() / df['volume'].rolling(5).sum()
        features['vwap_20'] = (df['close'] * df['volume']).rolling(20).sum() / df['volume'].rolling(20).sum()
        
        return features
    
    def extract_moving_averages(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract moving averages and ratios"""
        features = pd.DataFrame(index=df.index)
        
        # Simple Moving Averages
        features['sma_5'] = talib.SMA(df['close'].to_numpy(), timeperiod=5)
        features['sma_10'] = talib.SMA(df['close'].to_numpy(), timeperiod=10)
        features['sma_12'] = talib.SMA(df['close'].to_numpy(), timeperiod=12)
        features['sma_20'] = talib.SMA(df['close'].to_numpy(), timeperiod=20)
        features['sma_26'] = talib.SMA(df['close'].to_numpy(), timeperiod=26)
        features['sma_50'] = talib.SMA(df['close'].to_numpy(), timeperiod=50)
        features['sma_100'] = talib.SMA(df['close'].to_numpy(), timeperiod=100)
        features['sma_200'] = talib.SMA(df['close'].to_numpy(), timeperiod=200)
        
        # Exponential Moving Averages
        features['ema_5'] = talib.EMA(df['close'].to_numpy(), timeperiod=5)
        features['ema_10'] = talib.EMA(df['close'].to_numpy(), timeperiod=10)
        features['ema_12'] = talib.EMA(df['close'].to_numpy(), timeperiod=12)
        features['ema_20'] = talib.EMA(df['close'].to_numpy(), timeperiod=20)
        features['ema_26'] = talib.EMA(df['close'].to_numpy(), timeperiod=26)
        features['ema_50'] = talib.EMA(df['close'].to_numpy(), timeperiod=50)
        features['ema_100'] = talib.EMA(df['close'].to_numpy(), timeperiod=100)
        features['ema_200'] = talib.EMA(df['close'].to_numpy(), timeperiod=200)
        
        # Close to MA ratios
        features['close_sma_5_ratio'] = df['close'] / features['sma_5']
        features['close_ema_5_ratio'] = df['close'] / features['ema_5']
        features['close_sma_10_ratio'] = df['close'] / features['sma_10']
        features['close_ema_10_ratio'] = df['close'] / features['ema_10']
        features['close_sma_12_ratio'] = df['close'] / features['sma_12']
        features['close_ema_12_ratio'] = df['close'] / features['ema_12']
        features['close_sma_20_ratio'] = df['close'] / features['sma_20']
        features['close_ema_20_ratio'] = df['close'] / features['ema_20']
        features['close_sma_26_ratio'] = df['close'] / features['sma_26']
        features['close_ema_26_ratio'] = df['close'] / features['ema_26']
        features['close_sma_50_ratio'] = df['close'] / features['sma_50']
        features['close_ema_50_ratio'] = df['close'] / features['ema_50']
        features['close_sma_100_ratio'] = df['close'] / features['sma_100']
        features['close_ema_100_ratio'] = df['close'] / features['ema_100']
        features['close_sma_200_ratio'] = df['close'] / features['sma_200']
        features['close_ema_200_ratio'] = df['close'] / features['ema_200']
        
        # MA crosses
        features['sma_5_20_cross'] = (features['sma_5'] > features['sma_20']).astype(int)
        features['sma_10_50_cross'] = (features['sma_10'] > features['sma_50']).astype(int)
        features['ema_12_26_cross'] = (features['ema_12'] > features['ema_26']).astype(int)
        
        return features
    
    def extract_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract technical indicators"""
        features = pd.DataFrame(index=df.index)
        
        # MACD
        features['macd'], features['macd_signal'], features['macd_hist'] = talib.MACD(df['close'].to_numpy())
        features['macd_cross'] = (features['macd'] > features['macd_signal']).astype(int)
        
        # ADX and Directional Movement
        features['adx'] = talib.ADX(df['high'].to_numpy(), df['low'].to_numpy(), df['close'].to_numpy(), timeperiod=14)
        
        # Parabolic SAR
        features['sar'] = talib.SAR(df['high'].to_numpy(), df['low'].to_numpy())
        features['sar_trend'] = (df['close'] > features['sar']).astype(int)
        
        # Aroon
        features['aroon_up'], features['aroon_down'] = talib.AROON(df['high'].to_numpy(), df['low'].to_numpy(), timeperiod=14)
        features['aroon_osc'] = features['aroon_up'] - features['aroon_down']
        
        # RSI variants
        features['rsi_14'] = talib.RSI(df['close'].to_numpy(), timeperiod=14)
        features['rsi_7'] = talib.RSI(df['close'].to_numpy(), timeperiod=7)
        features['rsi_21'] = talib.RSI(df['close'].to_numpy(), timeperiod=21)
        features['rsi_oversold'] = (features['rsi_14'] < 30).astype(int)
        features['rsi_overbought'] = (features['rsi_14'] > 70).astype(int)
        features['rsi_neutral'] = ((features['rsi_14'] >= 30) & (features['rsi_14'] <= 70)).astype(int)
        
        # Stochastic
        features['stoch_k'], features['stoch_d'] = talib.STOCH(df['high'].to_numpy(), df['low'].to_numpy(), df['close'].to_numpy())
        features['stoch_cross'] = (features['stoch_k'] > features['stoch_d']).astype(int)
        
        # Williams %R
        features['willr'] = talib.WILLR(df['high'].to_numpy(), df['low'].to_numpy(), df['close'].to_numpy(), timeperiod=14)
        
        # Rate of Change and Momentum
        features['roc_5'] = talib.ROC(df['close'].to_numpy(), timeperiod=5)
        features['mom_5'] = talib.MOM(df['close'].to_numpy(), timeperiod=5)
        features['roc_10'] = talib.ROC(df['close'].to_numpy(), timeperiod=10)
        features['mom_10'] = talib.MOM(df['close'].to_numpy(), timeperiod=10)
        features['roc_20'] = talib.ROC(df['close'].to_numpy(), timeperiod=20)
        features['mom_20'] = talib.MOM(df['close'].to_numpy(), timeperiod=20)
        
        # CCI and Ultimate Oscillator
        features['cci'] = talib.CCI(df['high'].to_numpy(), df['low'].to_numpy(), df['close'].to_numpy(), timeperiod=14)
        features['ultosc'] = talib.ULTOSC(df['high'].to_numpy(), df['low'].to_numpy(), df['close'].to_numpy())
        
        return features
    
    def extract_volatility_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract volatility indicators"""
        features = pd.DataFrame(index=df.index)
        
        # ATR
        features['atr'] = talib.ATR(df['high'].to_numpy(), df['low'].to_numpy(), df['close'].to_numpy(), timeperiod=14)
        features['atr_pct'] = (features['atr'] / df['close']) * 100
        
        # Bollinger Bands
        features['bb_upper'], features['bb_middle'], features['bb_lower'] = talib.BBANDS(
            df['close'].to_numpy(), timeperiod=20, nbdevup=2, nbdevdn=2
        )
        features['bb_width'] = (features['bb_upper'] - features['bb_lower']) / features['bb_middle']
        features['bb_position'] = (df['close'] - features['bb_lower']) / (features['bb_upper'] - features['bb_lower'])
        features['bb_squeeze'] = (features['bb_width'] < features['bb_width'].rolling(20).mean()).astype(int)
        
        # Keltner Channels (approximation)
        ema_20 = talib.EMA(df['close'].to_numpy(), timeperiod=20)
        atr_10 = talib.ATR(df['high'].to_numpy(), df['low'].to_numpy(), df['close'].to_numpy(), timeperiod=10)
        features['kc_upper'] = ema_20 + (2 * atr_10)
        features['kc_lower'] = ema_20 - (2 * atr_10)
        features['kc_position'] = (df['close'] - features['kc_lower']) / (features['kc_upper'] - features['kc_lower'])
        
        return features
    
    def extract_volume_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract volume indicators"""
        features = pd.DataFrame(index=df.index)
        
        # Volume moving averages
        features['volume_sma_5'] = df['volume'].rolling(5).mean()
        features['volume_ratio_5'] = df['volume'] / features['volume_sma_5']
        features['volume_sma_10.1'] = df['volume'].rolling(10).mean()  # Note: .1 to match your feature names
        features['volume_ratio_10'] = df['volume'] / features['volume_sma_10.1']
        features['volume_sma_20.1'] = df['volume'].rolling(20).mean()
        features['volume_ratio_20'] = df['volume'] / features['volume_sma_20.1']
        features['volume_sma_50'] = df['volume'].rolling(50).mean()
        features['volume_ratio_50'] = df['volume'] / features['volume_sma_50']
        
        # Accumulation/Distribution and MFI
        features['ad'] = talib.AD(df['high'].to_numpy(), df['low'].to_numpy(), df['close'].to_numpy(), df['volume'].to_numpy())
        features['mfi'] = talib.MFI(df['high'].to_numpy(), df['low'].to_numpy(), df['close'].to_numpy(), df['volume'].to_numpy(), timeperiod=14)
        
        return features
    
    def extract_pattern_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract candlestick pattern features"""
        features = pd.DataFrame(index=df.index)
        
        # Basic patterns
        doji = talib.CDLDOJI(df['open'].to_numpy(), df['high'].to_numpy(), df['low'].to_numpy(), df['close'].to_numpy())
        hammer = talib.CDLHAMMER(df['open'].to_numpy(), df['high'].to_numpy(), df['low'].to_numpy(), df['close'].to_numpy())
        hanging_man = talib.CDLHANGINGMAN(df['open'].to_numpy(), df['high'].to_numpy(), df['low'].to_numpy(), df['close'].to_numpy())
        shooting_star = talib.CDLSHOOTINGSTAR(df['open'].to_numpy(), df['high'].to_numpy(), df['low'].to_numpy(), df['close'].to_numpy())
        engulfing = talib.CDLENGULFING(df['open'].to_numpy(), df['high'].to_numpy(), df['low'].to_numpy(), df['close'].to_numpy())
        harami = talib.CDLHARAMI(df['open'].to_numpy(), df['high'].to_numpy(), df['low'].to_numpy(), df['close'].to_numpy())
        morning_star = talib.CDLMORNINGSTAR(df['open'].to_numpy(), df['high'].to_numpy(), df['low'].to_numpy(), df['close'].to_numpy())
        evening_star = talib.CDLEVENINGSTAR(df['open'].to_numpy(), df['high'].to_numpy(), df['low'].to_numpy(), df['close'].to_numpy())
        three_black_crows = talib.CDL3BLACKCROWS(df['open'].to_numpy(), df['high'].to_numpy(), df['low'].to_numpy(), df['close'].to_numpy())
        three_white_soldiers = talib.CDL3WHITESOLDIERS(df['open'].to_numpy(), df['high'].to_numpy(), df['low'].to_numpy(), df['close'].to_numpy())
        
        # Pattern features
        features['pattern_doji'] = (doji != 0).astype(int)
        features['pattern_doji_bullish'] = (doji > 0).astype(int)
        features['pattern_doji_bearish'] = (doji < 0).astype(int)
        
        features['pattern_hammer'] = (hammer != 0).astype(int)
        features['pattern_hammer_bullish'] = (hammer > 0).astype(int)
        features['pattern_hammer_bearish'] = (hammer < 0).astype(int)
        
        features['pattern_hanging_man'] = (hanging_man != 0).astype(int)
        features['pattern_hanging_man_bullish'] = (hanging_man > 0).astype(int)
        features['pattern_hanging_man_bearish'] = (hanging_man < 0).astype(int)
        
        features['pattern_shooting_star'] = (shooting_star != 0).astype(int)
        features['pattern_shooting_star_bullish'] = (shooting_star > 0).astype(int)
        features['pattern_shooting_star_bearish'] = (shooting_star < 0).astype(int)
        
        features['pattern_engulfing'] = (engulfing != 0).astype(int)
        features['pattern_engulfing_bullish'] = (engulfing > 0).astype(int)
        features['pattern_engulfing_bearish'] = (engulfing < 0).astype(int)
        
        features['pattern_harami'] = (harami != 0).astype(int)
        features['pattern_harami_bullish'] = (harami > 0).astype(int)
        features['pattern_harami_bearish'] = (harami < 0).astype(int)
        
        features['pattern_morning_star'] = (morning_star != 0).astype(int)
        features['pattern_morning_star_bullish'] = (morning_star > 0).astype(int)
        features['pattern_morning_star_bearish'] = (morning_star < 0).astype(int)
        
        features['pattern_evening_star'] = (evening_star != 0).astype(int)
        features['pattern_evening_star_bullish'] = (evening_star > 0).astype(int)
        features['pattern_evening_star_bearish'] = (evening_star < 0).astype(int)
        
        features['pattern_three_black_crows'] = (three_black_crows != 0).astype(int)
        features['pattern_three_black_crows_bullish'] = (three_black_crows > 0).astype(int)
        features['pattern_three_black_crows_bearish'] = (three_black_crows < 0).astype(int)
        
        features['pattern_three_white_soldiers'] = (three_white_soldiers != 0).astype(int)
        features['pattern_three_white_soldiers_bullish'] = (three_white_soldiers > 0).astype(int)
        features['pattern_three_white_soldiers_bearish'] = (three_white_soldiers < 0).astype(int)
        
        # Pattern summary
        bullish_patterns = [
            'pattern_doji_bullish', 'pattern_hammer_bullish', 'pattern_hanging_man_bullish',
            'pattern_shooting_star_bullish', 'pattern_engulfing_bullish', 'pattern_harami_bullish',
            'pattern_morning_star_bullish', 'pattern_evening_star_bullish', 'pattern_three_black_crows_bullish',
            'pattern_three_white_soldiers_bullish'
        ]
        bearish_patterns = [
            'pattern_doji_bearish', 'pattern_hammer_bearish', 'pattern_hanging_man_bearish',
            'pattern_shooting_star_bearish', 'pattern_engulfing_bearish', 'pattern_harami_bearish',
            'pattern_morning_star_bearish', 'pattern_evening_star_bearish', 'pattern_three_black_crows_bearish',
            'pattern_three_white_soldiers_bearish'
        ]
        
        features['total_bullish_patterns'] = features[bullish_patterns].sum(axis=1)
        features['total_bearish_patterns'] = features[bearish_patterns].sum(axis=1)
        features['pattern_sentiment'] = features['total_bullish_patterns'] - features['total_bearish_patterns']
        
        return features
    
    def extract_support_resistance(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract support and resistance levels"""
        features = pd.DataFrame(index=df.index)
        
        # Calculate support and resistance levels
        def get_support_resistance(prices, window):
            resistance = prices.rolling(window).max()
            support = prices.rolling(window).min()
            return support, resistance
        
        # Different timeframe support/resistance
        support_10, resistance_10 = get_support_resistance(df['high'], 10)
        support_20, resistance_20 = get_support_resistance(df['high'], 20)
        support_50, resistance_50 = get_support_resistance(df['high'], 50)
        
        features['resistance_10'] = resistance_10
        features['support_10'] = get_support_resistance(df['low'], 10)[0]
        features['dist_to_resistance_10'] = (features['resistance_10'] - df['close']) / df['close']
        features['dist_to_support_10'] = (df['close'] - features['support_10']) / df['close']
        
        features['resistance_20'] = resistance_20
        features['support_20'] = get_support_resistance(df['low'], 20)[0]
        features['dist_to_resistance_20'] = (features['resistance_20'] - df['close']) / df['close']
        features['dist_to_support_20'] = (df['close'] - features['support_20']) / df['close']
        
        features['resistance_50'] = resistance_50
        features['support_50'] = get_support_resistance(df['low'], 50)[0]
        features['dist_to_resistance_50'] = (features['resistance_50'] - df['close']) / df['close']
        features['dist_to_support_50'] = (df['close'] - features['support_50']) / df['close']
        
        return features
    
    def extract_market_structure(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract market structure features"""
        features = pd.DataFrame(index=df.index)
        
        # Higher highs, lower lows, etc.
        features['higher_high'] = (df['high'] > df['high'].shift(1)).astype(int)
        features['lower_low'] = (df['low'] < df['low'].shift(1)).astype(int)
        features['higher_low'] = (df['low'] > df['low'].shift(1)).astype(int)
        features['lower_high'] = (df['high'] < df['high'].shift(1)).astype(int)
        
        # Gaps
        features['gap_up'] = (df['low'] > df['high'].shift(1)).astype(int)
        features['gap_down'] = (df['high'] < df['low'].shift(1)).astype(int)
        
        return features
    
    def add_timeframe_features(self, features: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        """Add timeframe-specific one-hot encoded features"""
        supported_timeframes = ['6h', '12h', '1d', '3d']
        
        for tf in supported_timeframes:
            features[f'timeframe_{tf}'] = 1 if tf == timeframe else 0
        
        return features
    
    def extract_features(self, df: pd.DataFrame, timeframe: str = '1d') -> pd.DataFrame:
        """
        Main feature extraction method
        
        Args:
            df: OHLCV DataFrame
            timeframe: Trading timeframe
            
        Returns:
            DataFrame with all extracted features
        """
        try:
            # Validate input data
            if not self.validate_data(df):
                logger.error("❌ Data validation failed")
                return pd.DataFrame()
            
            logger.info(f"🔧 Extracting features for {len(df)} candles ({timeframe})")
            
            # Extract all feature categories
            basic_features = self.extract_basic_features(df)
            ma_features = self.extract_moving_averages(df)
            technical_features = self.extract_technical_indicators(df)
            volatility_features = self.extract_volatility_indicators(df)
            volume_features = self.extract_volume_indicators(df)
            pattern_features = self.extract_pattern_features(df)
            sr_features = self.extract_support_resistance(df)
            structure_features = self.extract_market_structure(df)
            
            # Combine all features
            all_feature_dfs = [
                basic_features,
                ma_features,
                technical_features,
                volatility_features,
                volume_features,
                pattern_features,
                sr_features,
                structure_features
            ]
            
            # Concatenate along columns
            combined_features = pd.concat([f for f in all_feature_dfs if not f.empty], axis=1)
            
            # Add timeframe encoding
            combined_features = self.add_timeframe_features(combined_features, timeframe)
            
            # Clean data
            combined_features = combined_features.replace([np.inf, -np.inf], np.nan)
            combined_features = combined_features.ffill().fillna(0)
            
            # Remove duplicate columns before reindexing
            combined_features = combined_features.loc[:, ~combined_features.columns.duplicated()]
            
            # Remove any remaining problematic rows
            initial_len = len(combined_features)
            combined_features = combined_features.dropna()
            final_len = len(combined_features)
            
            if initial_len != final_len:
                logger.warning(f"⚠️ Dropped {initial_len - final_len} rows due to NaN values")
            
            logger.info(f"✅ Extracted {len(combined_features.columns)} features for {final_len} candles")
            
            # Define the exact 166 features your model expects
            FEATURE_NAMES = [
                'open', 'high', 'low', 'close', 'volume', 'price_range', 'body_size', 'upper_shadow', 'lower_shadow', 'range_pct',
                'body_pct', 'upper_shadow_pct', 'lower_shadow_pct', 'close_position', 'return_1', 'return_3', 'return_5', 'return_10',
                'return_20', 'log_return', 'volume_sma_10', 'volume_sma_20', 'volume_ratio', 'volume_return', 'price_volume',
                'vwap_5', 'vwap_20', 'sma_5', 'ema_5', 'close_sma_5_ratio', 'close_ema_5_ratio', 'sma_10', 'ema_10', 'close_sma_10_ratio',
                'close_ema_10_ratio', 'sma_12', 'ema_12', 'close_sma_12_ratio', 'close_ema_12_ratio', 'sma_20', 'ema_20',
                'close_sma_20_ratio', 'close_ema_20_ratio', 'sma_26', 'ema_26', 'close_sma_26_ratio', 'close_ema_26_ratio',
                'sma_50', 'ema_50', 'close_sma_50_ratio', 'close_ema_50_ratio', 'sma_100', 'ema_100', 'close_sma_100_ratio',
                'close_ema_100_ratio', 'sma_200', 'ema_200', 'close_sma_200_ratio', 'close_ema_200_ratio', 'sma_5_20_cross',
                'sma_10_50_cross', 'ema_12_26_cross', 'macd', 'macd_signal', 'macd_hist', 'macd_cross', 'adx', 'sar', 'sar_trend',
                'aroon_up', 'aroon_down', 'aroon_osc', 'rsi_14', 'rsi_oversold', 'rsi_overbought', 'rsi_neutral', 'rsi_7',
                'rsi_21', 'stoch_k', 'stoch_d', 'stoch_cross', 'willr', 'roc_5', 'mom_5', 'roc_10', 'mom_10', 'roc_20', 'mom_20',
                'cci', 'ultosc', 'atr', 'atr_pct', 'bb_upper', 'bb_middle', 'bb_lower', 'bb_width', 'bb_position', 'bb_squeeze',
                'kc_upper', 'kc_lower', 'kc_position', 'volume_sma_5', 'volume_ratio_5', 'volume_sma_10.1', 'volume_ratio_10',
                'volume_sma_20.1', 'volume_ratio_20', 'volume_sma_50', 'volume_ratio_50', 'ad', 'mfi', 'pattern_doji',
                'pattern_doji_bullish', 'pattern_doji_bearish', 'pattern_hammer', 'pattern_hammer_bullish', 'pattern_hammer_bearish',
                'pattern_hanging_man', 'pattern_hanging_man_bullish', 'pattern_hanging_man_bearish', 'pattern_shooting_star',
                'pattern_shooting_star_bullish', 'pattern_shooting_star_bearish', 'pattern_engulfing', 'pattern_engulfing_bullish',
                'pattern_engulfing_bearish', 'pattern_harami', 'pattern_harami_bullish', 'pattern_harami_bearish', 'pattern_morning_star',
                'pattern_morning_star_bullish', 'pattern_morning_star_bearish', 'pattern_evening_star', 'pattern_evening_star_bullish',
                'pattern_evening_star_bearish', 'pattern_three_black_crows', 'pattern_three_black_crows_bullish',
                'pattern_three_black_crows_bearish', 'pattern_three_white_soldiers', 'pattern_three_white_soldiers_bullish',
                'pattern_three_white_soldiers_bearish', 'total_bullish_patterns', 'total_bearish_patterns', 'pattern_sentiment',
                'resistance_10', 'support_10', 'dist_to_resistance_10', 'dist_to_support_10', 'resistance_20', 'support_20',
                'dist_to_resistance_20', 'dist_to_support_20', 'resistance_50', 'support_50', 'dist_to_resistance_50',
                'dist_to_support_50', 'higher_high', 'lower_low', 'higher_low', 'lower_high', 'gap_up', 'gap_down',
                'timeframe_6h', 'timeframe_12h', 'timeframe_1d', 'timeframe_3d'
            ]

            # Ensure output DataFrame contains exactly these features, in this order
            combined_features = combined_features.reindex(columns=FEATURE_NAMES, fill_value=0)
            
            logger.info(f"✅ Final feature set: {len(combined_features.columns)} features matching model requirements")
            return combined_features
            
        except Exception as e:
            logger.error(f"❌ Feature extraction failed: {e}")
            return pd.DataFrame()

# Global instance
feature_engineer = FeatureEngineer()