"""
Enhanced alert system with Discord webhook integration and multiple notification channels
Supports rich formatting, error handling, and notification preferences
"""

import requests
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, List
import json

from config.settings import config

logger = logging.getLogger(__name__)

class AlertManager:
    """Enhanced alert management with multiple channels and formatting"""
    
    def __init__(self):
        self.webhook_url = config.DISCORD_WEBHOOK
        self.enabled = bool(self.webhook_url)
        self.alert_history = []
        
    def format_price(self, price: float) -> str:
        """Format price with appropriate decimal places"""
        if price >= 1:
            return f"{price:.4f}"
        elif price >= 0.01:
            return f"{price:.6f}"
        else:
            return f"{price:.8f}"
    
    def format_percentage(self, percentage: float) -> str:
        """Format percentage with sign"""
        sign = "+" if percentage > 0 else ""
        return f"{sign}{percentage:.2f}%"
    
    def create_trade_alert_embed(self, signal_data: Dict) -> Dict:
        """Create rich Discord embed for trade signals"""
        try:
            direction = signal_data.get('direction', 'UNKNOWN')
            symbol = signal_data.get('symbol', 'UNKNOWN')
            probability = signal_data.get('probability', 0)
            timeframe = signal_data.get('timeframe', '1d')
            
            # Calculate risk/reward ratios
            entry = signal_data.get('entry', 0)
            tp1 = signal_data.get('tp1', 0)
            stoploss = signal_data.get('stoploss', 0)
            
            if direction == "LONG" and entry > 0:
                risk_pct = abs((entry - stoploss) / entry * 100)
                reward_pct = abs((tp1 - entry) / entry * 100)
                rr_ratio = reward_pct / risk_pct if risk_pct > 0 else 0
            elif direction == "SHORT" and entry > 0:
                risk_pct = abs((stoploss - entry) / entry * 100)
                reward_pct = abs((entry - tp1) / entry * 100)
                rr_ratio = reward_pct / risk_pct if risk_pct > 0 else 0
            else:
                risk_pct = reward_pct = rr_ratio = 0
            
            # Color based on probability
            if probability >= 0.8:
                color = 0x00ff00  # Green
            elif probability >= 0.7:
                color = 0xffff00  # Yellow
            else:
                color = 0xff9900  # Orange
            
            # Create embed
            embed = {
                "title": "🚨 **NEW TRADE SIGNAL** 🚨",
                "color": color,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "fields": [
                    {
                        "name": "📊 **Trade Details**",
                        "value": (
                            f"**Symbol:** {symbol}\n"
                            f"**Direction:** {direction} {'📈' if direction == 'LONG' else '📉'}\n"
                            f"**Timeframe:** {timeframe}\n"
                            f"**AI Confidence:** {probability:.1%}"
                        ),
                        "inline": True
                    },
                    {
                        "name": "💰 **Price Levels**",
                        "value": (
                            f"**Entry:** {self.format_price(entry)}\n"
                            f"**Stop Loss:** {self.format_price(stoploss)}\n"
                            f"**Take Profit 1:** {self.format_price(tp1)}"
                        ),
                        "inline": True
                    },
                    {
                        "name": "🎯 **Additional Targets**",
                        "value": (
                            f"**Take Profit 2:** {self.format_price(signal_data.get('tp2', 0))}\n"
                            f"**Take Profit 3:** {self.format_price(signal_data.get('tp3', 0))}\n"
                            f"**Risk/Reward:** 1:{rr_ratio:.1f}"
                        ),
                        "inline": True
                    },
                    {
                        "name": "📈 **Risk Management**",
                        "value": (
                            f"**Risk:** {self.format_percentage(risk_pct)}\n"
                            f"**Potential Reward:** {self.format_percentage(reward_pct)}\n"
                            f"**Duration:** {signal_data.get('duration_hours', 24)}h"
                        ),
                        "inline": True
                    }
                ],
                "footer": {
                    "text": f"AI Crypto Trading Bot • {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC"
                }
            }
            
            return embed
            
        except Exception as e:
            logger.error(f"❌ Error creating trade alert embed: {e}")
            return {}
    
    def create_simple_alert_message(self, signal_data: Dict) -> str:
        """Create simple text message for trade signals"""
        try:
            symbol = signal_data.get('symbol', 'UNKNOWN')
            direction = signal_data.get('direction', 'UNKNOWN')
            entry = signal_data.get('entry', 0)
            stoploss = signal_data.get('stoploss', 0)
            tp1 = signal_data.get('tp1', 0)
            tp2 = signal_data.get('tp2', 0)
            tp3 = signal_data.get('tp3', 0)
            probability = signal_data.get('probability', 0)
            timeframe = signal_data.get('timeframe', '1d')
            
            message = (
                f"🚨 **NEW TRADE SIGNAL** 🚨\n\n"
                f"**Coin:** {symbol}\n"
                f"**Direction:** {direction} {'📈' if direction == 'LONG' else '📉'}\n"
                f"**Timeframe:** {timeframe}\n"
                f"**AI Confidence:** {probability:.1%}\n\n"
                f"**📊 Price Levels:**\n"
                f"Entry: {self.format_price(entry)}\n"
                f"Stop Loss: {self.format_price(stoploss)}\n"
                f"TP1: {self.format_price(tp1)}\n"
                f"TP2: {self.format_price(tp2)}\n"
                f"TP3: {self.format_price(tp3)}\n\n"
                f"**⏰ Duration:** {signal_data.get('duration_hours', 24)} hours\n"
                f"**🤖 Generated by AI Crypto Trading Bot**"
            )
            
            return message
            
        except Exception as e:
            logger.error(f"❌ Error creating simple alert message: {e}")
            return "Error creating alert message"
    
    def send_discord_alert(self, signal_data: Dict, use_embed: bool = True) -> bool:
        """Send alert to Discord webhook"""
        if not self.enabled:
            logger.warning("⚠️ Discord alerts disabled (no webhook URL)")
            return False
        
        try:
            if use_embed:
                embed = self.create_trade_alert_embed(signal_data)
                if embed:
                    payload = {"embeds": [embed]}
                else:
                    # Fallback to simple message
                    payload = {"content": self.create_simple_alert_message(signal_data)}
            else:
                payload = {"content": self.create_simple_alert_message(signal_data)}
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            
            if response.status_code in (200, 204):
                logger.info(f"✅ Discord alert sent for {signal_data.get('symbol', 'UNKNOWN')}")
                
                # Store in history
                self.alert_history.append({
                    'timestamp': datetime.now(timezone.utc),
                    'symbol': signal_data.get('symbol'),
                    'type': 'trade_signal',
                    'status': 'sent'
                })
                
                return True
            else:
                logger.error(f"❌ Discord alert failed: HTTP {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            logger.error("❌ Discord alert timeout")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Discord alert network error: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Discord alert error: {e}")
            return False
    
    def send_trade_update_alert(self, symbol: str, result: str, 
                               entry_price: float, exit_price: float,
                               direction: str, timeframe: str) -> bool:
        """Send trade result update alert"""
        try:
            if direction == "LONG":
                pnl_pct = ((exit_price - entry_price) / entry_price) * 100
            else:
                pnl_pct = ((entry_price - exit_price) / entry_price) * 100
            
            # Result emoji mapping
            result_emoji = {
                'TP1': '🎯',
                'TP2': '🎯🎯',
                'TP3': '🎯🎯🎯',
                'Loss': '🛑',
                'Tie': '⚖️'
            }
            
            emoji = result_emoji.get(result, '📊')
            
            message = (
                f"{emoji} **TRADE UPDATE** {emoji}\n\n"
                f"**Symbol:** {symbol}\n"
                f"**Result:** {result}\n"
                f"**Direction:** {direction}\n"
                f"**Timeframe:** {timeframe}\n\n"
                f"**💰 Performance:**\n"
                f"Entry: {self.format_price(entry_price)}\n"
                f"Exit: {self.format_price(exit_price)}\n"
                f"P&L: {self.format_percentage(pnl_pct)}\n\n"
                f"**🤖 AI Crypto Trading Bot**"
            )
            
            payload = {"content": message}
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            
            if response.status_code in (200, 204):
                logger.info(f"✅ Trade update alert sent for {symbol}")
                return True
            else:
                logger.error(f"❌ Trade update alert failed: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Trade update alert error: {e}")
            return False
    
    def send_daily_summary_alert(self, stats: Dict) -> bool:
        """Send daily performance summary"""
        try:
            message = (
                f"📊 **DAILY TRADING SUMMARY** 📊\n\n"
                f"**Overall Performance:**\n"
                f"Win Rate: {stats.get('winrate', 0):.1f}%\n"
                f"Total Trades: {stats.get('total', 0)}\n"
                f"Wins: {stats.get('wins', 0)}\n"
                f"Losses: {stats.get('losses', 0)}\n"
                f"Ties: {stats.get('ties', 0)}\n\n"
                f"**Target Breakdown:**\n"
                f"TP1 Hits: {stats.get('tp1_hits', 0)}\n"
                f"TP2 Hits: {stats.get('tp2_hits', 0)}\n"
                f"TP3 Hits: {stats.get('tp3_hits', 0)}\n\n"
                f"**🤖 AI Crypto Trading Bot**"
            )
            
            payload = {"content": message}
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            
            if response.status_code in (200, 204):
                logger.info("✅ Daily summary alert sent")
                return True
            else:
                logger.error(f"❌ Daily summary alert failed: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Daily summary alert error: {e}")
            return False
    
    def test_webhook(self) -> bool:
        """Test Discord webhook connectivity"""
        try:
            test_message = {
                "content": "🧪 **Test Alert** - AI Crypto Trading Bot is online and ready!"
            }
            
            response = requests.post(
                self.webhook_url,
                json=test_message,
                timeout=10
            )
            
            if response.status_code in (200, 204):
                logger.info("✅ Discord webhook test successful")
                return True
            else:
                logger.error(f"❌ Discord webhook test failed: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Discord webhook test error: {e}")
            return False
    
    def get_alert_history(self, limit: int = 50) -> List[Dict]:
        """Get recent alert history"""
        return self.alert_history[-limit:] if self.alert_history else []
    
    def clear_alert_history(self):
        """Clear alert history"""
        self.alert_history.clear()
        logger.info("🧹 Alert history cleared")

# Global instance
alert_manager = AlertManager()

# Backward compatibility function
def send_alert(symbol, probability, entry, stoploss, tp1, tp2, tp3, direction, timeframe):
    """Backward compatibility wrapper"""
    signal_data = {
        'symbol': symbol,
        'probability': probability,
        'entry': entry,
        'stoploss': stoploss,
        'tp1': tp1,
        'tp2': tp2,
        'tp3': tp3,
        'direction': direction,
        'timeframe': timeframe,
        'duration_hours': config.get_timeframe_setting(timeframe, 'duration_hours', 24)
    }
    
    return alert_manager.send_discord_alert(signal_data)