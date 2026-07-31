"""
Enhanced data fetcher for cryptocurrency market data
Supports multiple exchanges, robust error handling, and rate limiting
"""

import ccxt
import pandas as pd
import time
import logging
from typing import List, Optional, Tuple
from config.settings import config

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataFetcher:
    """Enhanced data fetcher with robust error handling"""
    
    def __init__(self, exchange_name='binance', rate_limit_delay=0.1):
        self.rate_limit_delay = rate_limit_delay
        self.exchange = self._initialize_exchange(exchange_name)
        self._markets_cache = None
        self._last_markets_update = 0
        self.markets_cache_ttl = 3600  # 1 hour
        
    def _initialize_exchange(self, exchange_name):
        """Initialize exchange with proper error handling"""
        try:
            exchange_class = getattr(ccxt, exchange_name)
            exchange = exchange_class(config.EXCHANGE_OPTIONS)
            exchange.load_markets()
            logger.info(f"✅ Initialized {exchange_name} exchange")
            return exchange
        except Exception as e:
            logger.error(f"❌ Failed to initialize {exchange_name}: {e}")
            raise
    
    def _rate_limit(self):
        """Simple rate limiting"""
        time.sleep(self.rate_limit_delay)
    
    def _get_markets(self, force_refresh=False):
        """Get markets with caching"""
        current_time = time.time()
        
        if (force_refresh or 
            self._markets_cache is None or 
            current_time - self._last_markets_update > self.markets_cache_ttl):
            
            try:
                self._markets_cache = self.exchange.load_markets()
                self._last_markets_update = current_time
                logger.debug(f"🔄 Refreshed markets cache: {len(self._markets_cache)} markets")
            except Exception as e:
                logger.error(f"❌ Failed to refresh markets: {e}")
                if self._markets_cache is None:
                    self._markets_cache = {}
        
        return self._markets_cache
    
    def get_top_coins(self, limit=100, min_volume=100000):  # Changed from 1000000
        """Get top coins by volume with enhanced filtering"""
        try:
            markets = self._get_markets()
            usdt_symbols = []
            
            for symbol, market in markets.items():
                if (symbol.endswith('/USDT') and 
                    market.get('active', True) and 
                    market.get('type') == 'spot'):
                    usdt_symbols.append(symbol)
            
            # Get 24h tickers for volume filtering
            try:
                self._rate_limit()
                tickers = self.exchange.fetch_tickers(usdt_symbols[:200])  # Limit API calls
                
                # Filter by volume and sort
                volume_data = []
                for symbol, ticker in tickers.items():
                    volume = ticker.get('quoteVolume', 0) or 0
                    if volume >= min_volume:
                        volume_data.append((symbol, volume))
                
                # Sort by volume and return top coins
                volume_data.sort(key=lambda x: x[1], reverse=True)
                top_coins = [symbol for symbol, _ in volume_data[:limit]]
                
                logger.info(f"📊 Found {len(top_coins)} coins with volume >= ${min_volume:,}")
                return top_coins
                
            except Exception as e:
                logger.warning(f"⚠️ Volume filtering failed: {e}")
                # Fallback to static list
                fallback = [s for s in usdt_symbols if any(coin in s for coin in 
                           ['BTC', 'ETH', 'BNB', 'ADA', 'SOL', 'XRP', 'DOT', 'MATIC', 'LINK', 'AVAX'])]
                logger.warning(f"⚠️ Using fallback coin list: {len(fallback)} coins")
                return fallback[:limit]
                
        except Exception as e:
            logger.error(f"❌ Failed to get top coins: {e}")
            # Ultimate fallback
            fallback = [
                'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'ADA/USDT', 'SOL/USDT',
                'XRP/USDT', 'DOT/USDT', 'MATIC/USDT', 'LINK/USDT', 'AVAX/USDT'
            ]
            logger.warning(f"⚠️ Using ultimate fallback: {len(fallback)} coins")
            return fallback[:limit]
    
    def fetch_live_data(self, symbol: str, timeframe='1h', limit=500) -> Optional[pd.DataFrame]:
        """
        Fetch live OHLCV data with enhanced error handling
        
        Args:
            symbol: Trading symbol (e.g., 'BTC/USDT')
            timeframe: Timeframe string (e.g., '1h', '1d')
            limit: Number of candles to fetch
            
        Returns:
            DataFrame with OHLCV data or None if failed
        """
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                self._rate_limit()
                
                ohlcv = self.exchange.fetch_ohlcv(
                    symbol, 
                    timeframe=timeframe, 
                    limit=limit
                )
                
                if not ohlcv:
                    logger.warning(f"⚠️ No data returned for {symbol} {timeframe}")
                    return None
                
                df = pd.DataFrame(
                    ohlcv, 
                    columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
                )
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
                
                # Validate data
                if len(df) < 10:
                    logger.warning(f"⚠️ Insufficient data for {symbol}: {len(df)} candles")
                    return None
                
                # Check for data quality issues
                if df[['open', 'high', 'low', 'close']].isnull().any().any():
                    logger.warning(f"⚠️ Data quality issues for {symbol}: contains NaN values")
                    df = df.dropna()
                
                logger.debug(f"✅ Fetched {len(df)} candles for {symbol} {timeframe}")
                return df
                
            except ccxt.NetworkError as e:
                logger.warning(f"🌐 Network error for {symbol} (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                    
            except ccxt.RateLimitExceeded as e:
                logger.warning(f"⏰ Rate limit exceeded for {symbol} (attempt {attempt + 1})")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * 5)  # Longer delay for rate limits
                    continue
                    
            except Exception as e:
                logger.error(f"❌ Unexpected error fetching {symbol}: {e}")
                break
        
        logger.error(f"❌ Failed to fetch data for {symbol} after {max_retries} attempts")
        return None
    
    def fetch_historical_data(self, symbol: str, timeframe: str, days_back: int = 365) -> Optional[pd.DataFrame]:
        """
        Fetch historical data for model training
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe string
            days_back: Number of days to fetch
            
        Returns:
            DataFrame with historical OHLCV data
        """
        try:
            # Calculate how many candles we need based on timeframe
            timeframe_minutes = {
                '1m': 1, '5m': 5, '15m': 15, '30m': 30, '1h': 60, 
                '2h': 120, '4h': 240, '6h': 360, '12h': 720, '1d': 1440, '3d': 4320
            }
            
            minutes = timeframe_minutes.get(timeframe, 60)
            total_candles = (days_back * 24 * 60) // minutes
            
            # Binance has a limit of 1000 candles per request
            limit_per_request = 1000
            all_data = []
            
            end_time = None
            remaining_candles = total_candles
            
            while remaining_candles > 0:
                current_limit = min(limit_per_request, remaining_candles)
                
                self._rate_limit()
                
                if end_time:
                    ohlcv = self.exchange.fetch_ohlcv(
                        symbol, timeframe, since=None, limit=current_limit, 
                        params={'endTime': end_time}
                    )
                else:
                    ohlcv = self.exchange.fetch_ohlcv(
                        symbol, timeframe, limit=current_limit
                    )
                
                if not ohlcv:
                    break
                
                all_data = ohlcv + all_data  # Prepend to get chronological order
                end_time = ohlcv[0][0] - 1  # Get timestamp before first candle
                remaining_candles -= len(ohlcv)
                
                logger.info(f"📊 Fetched {len(ohlcv)} candles for {symbol}, remaining: {remaining_candles}")
                
                if len(ohlcv) < current_limit:
                    # No more data available
                    break
            
            if all_data:
                df = pd.DataFrame(
                    all_data, 
                    columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
                )
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
                df = df.drop_duplicates(subset=['timestamp']).reset_index(drop=True)
                
                logger.info(f"✅ Historical data for {symbol}: {len(df)} candles over {days_back} days")
                return df
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Failed to fetch historical data for {symbol}: {e}")
            return None
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for a symbol"""
        try:
            self._rate_limit()
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker.get('last') or ticker.get('close')
        except Exception as e:
            logger.error(f"❌ Failed to get price for {symbol}: {e}")
            return None

# Global instance - lazy initialization
data_fetcher = None

def get_data_fetcher():
    """Get data fetcher instance with lazy initialization"""
    global data_fetcher
    if data_fetcher is None:
        data_fetcher = DataFetcher()
    return data_fetcher