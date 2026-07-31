"""
Enhanced utility functions for the AI Crypto Trading Bot
Common utilities, data validation, and helper functions
"""

import pandas as pd
import numpy as np
import logging
import os
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Union, Any
import hashlib
import time

from config.settings import config

logger = logging.getLogger(__name__)

class DataValidator:
    """Data validation utilities"""
    
    @staticmethod
    def validate_ohlcv_data(df: pd.DataFrame) -> Dict[str, Any]:
        """Validate OHLCV data quality"""
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'stats': {}
        }
        
        try:
            # Check required columns
            required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                validation_result['is_valid'] = False
                validation_result['errors'].append(f"Missing columns: {missing_cols}")
                return validation_result
            
            # Check data length
            if len(df) < 10:
                validation_result['is_valid'] = False
                validation_result['errors'].append(f"Insufficient data: {len(df)} rows")
                return validation_result
            
            # Check for null values
            null_counts = df[required_cols].isnull().sum()
            if null_counts.any():
                validation_result['warnings'].append(f"Null values found: {null_counts.to_dict()}")
            
            # Check price relationships (high >= max(open,close), low <= min(open,close))
            invalid_highs = (df['high'] < df[['open', 'close']].max(axis=1)).sum()
            invalid_lows = (df['low'] > df[['open', 'close']].min(axis=1)).sum()
            
            if invalid_highs > 0:
                validation_result['warnings'].append(f"Invalid high prices: {invalid_highs} candles")
            if invalid_lows > 0:
                validation_result['warnings'].append(f"Invalid low prices: {invalid_lows} candles")
            
            # Check for negative prices or volumes
            negative_prices = (df[['open', 'high', 'low', 'close']] <= 0).any().any()
            negative_volumes = (df['volume'] < 0).any()
            
            if negative_prices:
                validation_result['warnings'].append("Negative or zero prices found")
            if negative_volumes:
                validation_result['warnings'].append("Negative volumes found")
            
            # Calculate statistics
            validation_result['stats'] = {
                'rows': len(df),
                'start_time': df['timestamp'].iloc[0] if 'timestamp' in df.columns else None,
                'end_time': df['timestamp'].iloc[-1] if 'timestamp' in df.columns else None,
                'avg_volume': df['volume'].mean(),
                'price_range': {
                    'min': df[['open', 'high', 'low', 'close']].min().min(),
                    'max': df[['open', 'high', 'low', 'close']].max().max()
                }
            }
            
        except Exception as e:
            validation_result['is_valid'] = False
            validation_result['errors'].append(f"Validation error: {str(e)}")
        
        return validation_result
    
    @staticmethod
    def validate_trade_parameters(entry: float, stoploss: float, tp1: float, 
                                tp2: float, tp3: float, direction: str) -> Dict[str, Any]:
        """Validate trade parameters"""
        validation_result = {
            'is_valid': True,
            'errors': []
        }
        
        try:
            # Check for positive prices
            prices = [entry, stoploss, tp1, tp2, tp3]
            if any(p <= 0 for p in prices):
                validation_result['is_valid'] = False
                validation_result['errors'].append("All prices must be positive")
            
            # Check direction-specific relationships
            direction = direction.upper()
            
            if direction == "LONG":
                if stoploss >= entry:
                    validation_result['is_valid'] = False
                    validation_result['errors'].append("LONG: Stop loss must be below entry")
                
                if tp1 <= entry:
                    validation_result['is_valid'] = False
                    validation_result['errors'].append("LONG: Take profit must be above entry")
                
                if not (tp1 <= tp2 <= tp3):
                    validation_result['is_valid'] = False
                    validation_result['errors'].append("LONG: Take profits must be in ascending order")
            
            elif direction == "SHORT":
                if stoploss <= entry:
                    validation_result['is_valid'] = False
                    validation_result['errors'].append("SHORT: Stop loss must be above entry")
                
                if tp1 >= entry:
                    validation_result['is_valid'] = False
                    validation_result['errors'].append("SHORT: Take profit must be below entry")
                
                if not (tp1 >= tp2 >= tp3):
                    validation_result['is_valid'] = False
                    validation_result['errors'].append("SHORT: Take profits must be in descending order")
            
            else:
                validation_result['is_valid'] = False
                validation_result['errors'].append(f"Invalid direction: {direction}")
        
        except Exception as e:
            validation_result['is_valid'] = False
            validation_result['errors'].append(f"Validation error: {str(e)}")
        
        return validation_result

class FileManager:
    """File management utilities"""
    
    @staticmethod
    def ensure_directory(path: str) -> bool:
        """Ensure directory exists"""
        try:
            os.makedirs(path, exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"❌ Failed to create directory {path}: {e}")
            return False
    
    @staticmethod
    def backup_file(filepath: str, backup_dir: str = "backups") -> Optional[str]:
        """Create backup of a file"""
        try:
            if not os.path.exists(filepath):
                return None
            
            # Ensure backup directory exists
            FileManager.ensure_directory(backup_dir)
            
            # Create backup filename with timestamp
            filename = os.path.basename(filepath)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup_filename = f"{timestamp}_{filename}"
            backup_path = os.path.join(backup_dir, backup_filename)
            
            # Copy file
            import shutil
            shutil.copy2(filepath, backup_path)
            
            logger.info(f"✅ Backup created: {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"❌ Failed to backup {filepath}: {e}")
            return None
    
    @staticmethod
    def get_file_hash(filepath: str) -> Optional[str]:
        """Get MD5 hash of file"""
        try:
            hash_md5 = hashlib.md5()
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"❌ Failed to hash {filepath}: {e}")
            return None
    
    @staticmethod
    def clean_old_backups(backup_dir: str = "backups", keep_days: int = 30) -> int:
        """Clean old backup files"""
        try:
            if not os.path.exists(backup_dir):
                return 0
            
            cutoff_time = time.time() - (keep_days * 24 * 3600)
            removed_count = 0
            
            for filename in os.listdir(backup_dir):
                filepath = os.path.join(backup_dir, filename)
                if os.path.isfile(filepath) and os.path.getmtime(filepath) < cutoff_time:
                    os.remove(filepath)
                    removed_count += 1
            
            logger.info(f"🧹 Cleaned {removed_count} old backup files")
            return removed_count
            
        except Exception as e:
            logger.error(f"❌ Failed to clean backups: {e}")
            return 0

class TimeUtils:
    """Time and date utilities"""
    
    @staticmethod
    def parse_timestamp(timestamp_str: str) -> Optional[datetime]:
        """Parse timestamp string to UTC datetime"""
        try:
            # Try different formats
            formats = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S.%fZ"
            ]
            
            for fmt in formats:
                try:
                    dt = datetime.strptime(timestamp_str, fmt)
                    # Assume UTC if no timezone info
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
                except ValueError:
                    continue
            
            # Try pandas to_datetime as fallback
            dt = pd.to_datetime(timestamp_str, utc=True)
            return dt.to_pydatetime()
            
        except Exception as e:
            logger.error(f"❌ Failed to parse timestamp {timestamp_str}: {e}")
            return None
    
    @staticmethod
    def format_duration(seconds: float) -> str:
        """Format duration in human-readable format"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            return f"{seconds/60:.1f}m"
        elif seconds < 86400:
            return f"{seconds/3600:.1f}h"
        else:
            return f"{seconds/86400:.1f}d"
    
    @staticmethod
    def get_timeframe_duration(timeframe: str) -> timedelta:
        """Get duration for a timeframe string"""
        timeframe_map = {
            '1m': timedelta(minutes=1),
            '5m': timedelta(minutes=5),
            '15m': timedelta(minutes=15),
            '30m': timedelta(minutes=30),
            '1h': timedelta(hours=1),
            '2h': timedelta(hours=2),
            '4h': timedelta(hours=4),
            '6h': timedelta(hours=6),
            '8h': timedelta(hours=8),
            '12h': timedelta(hours=12),
            '1d': timedelta(days=1),
            '3d': timedelta(days=3),
            '1w': timedelta(weeks=1)
        }
        
        return timeframe_map.get(timeframe, timedelta(hours=1))

class PerformanceUtils:
    """Performance calculation utilities"""
    
    @staticmethod
    def calculate_pnl_percentage(entry_price: float, exit_price: float, direction: str) -> float:
        """Calculate P&L percentage"""
        try:
            direction = direction.upper()
            
            if direction == "LONG":
                return ((exit_price - entry_price) / entry_price) * 100
            elif direction == "SHORT":
                return ((entry_price - exit_price) / entry_price) * 100
            else:
                return 0.0
                
        except Exception as e:
            logger.error(f"❌ Error calculating P&L: {e}")
            return 0.0
    
    @staticmethod
    def calculate_risk_reward_ratio(entry: float, stoploss: float, take_profit: float, direction: str) -> float:
        """Calculate risk/reward ratio"""
        try:
            direction = direction.upper()
            
            if direction == "LONG":
                risk = abs(entry - stoploss)
                reward = abs(take_profit - entry)
            elif direction == "SHORT":
                risk = abs(stoploss - entry)
                reward = abs(entry - take_profit)
            else:
                return 0.0
            
            return reward / risk if risk > 0 else 0.0
            
        except Exception as e:
            logger.error(f"❌ Error calculating R/R ratio: {e}")
            return 0.0
    
    @staticmethod
    def calculate_win_rate(results: List[str]) -> Dict[str, float]:
        """Calculate comprehensive win rate statistics"""
        try:
            total = len(results)
            if total == 0:
                return {'win_rate': 0.0, 'tp1_rate': 0.0, 'tp2_rate': 0.0, 'tp3_rate': 0.0, 'loss_rate': 0.0, 'tie_rate': 0.0}
            
            tp1_count = sum(1 for r in results if r == 'TP1')
            tp2_count = sum(1 for r in results if r == 'TP2')
            tp3_count = sum(1 for r in results if r == 'TP3')
            loss_count = sum(1 for r in results if r in ['Loss', 'SL'])
            tie_count = sum(1 for r in results if r in ['Tie', 'TIMEOUT'])
            
            win_count = tp1_count + tp2_count + tp3_count
            
            return {
                'win_rate': (win_count / total) * 100,
                'tp1_rate': (tp1_count / total) * 100,
                'tp2_rate': (tp2_count / total) * 100,
                'tp3_rate': (tp3_count / total) * 100,
                'loss_rate': (loss_count / total) * 100,
                'tie_rate': (tie_count / total) * 100
            }
            
        except Exception as e:
            logger.error(f"❌ Error calculating win rate: {e}")
            return {'win_rate': 0.0, 'tp1_rate': 0.0, 'tp2_rate': 0.0, 'tp3_rate': 0.0, 'loss_rate': 0.0, 'tie_rate': 0.0}

class LoggingUtils:
    """Logging configuration utilities"""
    
    @staticmethod
    def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None) -> None:
        """Setup comprehensive logging"""
        try:
            # Create logs directory
            if log_file:
                log_dir = os.path.dirname(log_file)
                if log_dir:
                    os.makedirs(log_dir, exist_ok=True)
            
            # Configure logging format
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            
            # Setup root logger
            root_logger = logging.getLogger()
            root_logger.setLevel(getattr(logging, log_level.upper()))
            
            # Clear existing handlers
            root_logger.handlers.clear()
            
            # Console handler
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)
            
            # File handler if specified
            if log_file:
                file_handler = logging.FileHandler(log_file)
                file_handler.setFormatter(formatter)
                root_logger.addHandler(file_handler)
            
            logger.info(f"✅ Logging configured: level={log_level}, file={log_file}")
            
        except Exception as e:
            print(f"❌ Failed to setup logging: {e}")

class ConfigManager:
    """Configuration management utilities"""
    
    @staticmethod
    def load_user_config(config_file: str = "user_config.json") -> Dict[str, Any]:
        """Load user configuration from JSON file"""
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    user_config = json.load(f)
                logger.info(f"✅ Loaded user config from {config_file}")
                return user_config
            else:
                logger.info(f"📝 No user config file found at {config_file}")
                return {}
        except Exception as e:
            logger.error(f"❌ Failed to load user config: {e}")
            return {}
    
    @staticmethod
    def save_user_config(config_data: Dict[str, Any], config_file: str = "user_config.json") -> bool:
        """Save user configuration to JSON file"""
        try:
            with open(config_file, 'w') as f:
                json.dump(config_data, f, indent=2, default=str)
            logger.info(f"✅ Saved user config to {config_file}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to save user config: {e}")
            return False
    
    @staticmethod
    def get_system_info() -> Dict[str, Any]:
        """Get system information"""
        try:
            import platform
            import psutil
            
            return {
                'platform': platform.system(),
                'platform_version': platform.version(),
                'python_version': platform.python_version(),
                'cpu_count': psutil.cpu_count(),
                'memory_total': psutil.virtual_memory().total,
                'memory_available': psutil.virtual_memory().available,
                'disk_free': psutil.disk_usage('.').free,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.error(f"❌ Failed to get system info: {e}")
            return {'error': str(e)}

# Global utility instances
data_validator = DataValidator()
file_manager = FileManager()
time_utils = TimeUtils()
performance_utils = PerformanceUtils()
logging_utils = LoggingUtils()
config_manager = ConfigManager()