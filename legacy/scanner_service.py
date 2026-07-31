"""
Real-time Market Scanner Service
Continuously scans for trading opportunities
"""

import asyncio
import logging
from datetime import datetime, timezone
from predictor import model_predictor
from data_fetcher import DataFetcher
from utils import ConfigManager

logger = logging.getLogger(__name__)

class ScannerService:
    def __init__(self):
        self.predictor = model_predictor()
        self.market_data = DataFetcher()
        self.notifications = ConfigManager()
        self.running = False
    
    async def run_scanner(self):
        """Continuous scanning loop"""
        logger.info("🔍 Starting Scanner Service...")
        self.running = True
        
        # Extended symbol list for scanning
        symbols = [
            'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'ADA/USDT', 'MATIC/USDT',
            'DOT/USDT', 'LINK/USDT', 'AVAX/USDT', 'UNI/USDT', 'LTC/USDT',
            'ATOM/USDT', 'FTM/USDT', 'ALGO/USDT', 'XLM/USDT', 'VET/USDT'
        ]
        
        while self.running:
            try:
                opportunities = []
                
                for symbol in symbols:
                    # Get market data
                    data = await self.market_data.get_recent_data(symbol, '1h', 100)
                    
                    if data is not None:
                        # Get AI prediction
                        prediction = self.predictor.predict_signal(data)
                        
                        # Check if it's a strong opportunity
                        if prediction['confidence'] > 0.8:
                            opportunities.append({
                                'symbol': symbol,
                                'signal': prediction['signal'],
                                'confidence': prediction['confidence'],
                                'timestamp': datetime.now(timezone.utc)
                            })
                
                # Send notifications for strong opportunities
                if opportunities:
                    await self.notifications.send_opportunities(opportunities)
                
                logger.info(f"📊 Scanned {len(symbols)} symbols, found {len(opportunities)} opportunities")
                
                # Wait 10 minutes before next scan
                await asyncio.sleep(600)
                
            except Exception as e:
                logger.error(f"❌ Scanner error: {e}")
                await asyncio.sleep(300)

if __name__ == "__main__":
    scanner = ScannerService()
    asyncio.run(scanner.run_scanner())