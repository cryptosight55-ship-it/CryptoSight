"""
Configuration management for CryptoSight.
Centralized settings for all components.

NOTE (migration): this is the relocated `src/config.py`. Two things were
fixed here as part of the structural move, not as strategy-logic changes:
  1. A second, dead `ensure_directories`/`setup_logging` pair used to live
     at module level (outside any class, decorated with a stray
     `@classmethod`). It never ran and shadowed nothing -- it's merged
     into the one real `Config` class below.
  2. The Discord webhook URL used to be hardcoded here and committed to
     git history. It's now read from the `DISCORD_WEBHOOK` environment
     variable. If you're inheriting this repo, treat the old webhook as
     compromised and regenerate it in Discord.
"""

import os
import logging
from datetime import datetime


class Config:
    """Main configuration class"""

    # API Settings
    EXCHANGE = 'binance'
    EXCHANGE_OPTIONS = {'enableRateLimit': True, 'options': {'defaultType': 'spot'}}

    # Data Paths
    DATA_DIR = "data"
    MODELS_DIR = "models"
    LOGS_DIR = "logs"
    TRADE_LOG_FILE = os.path.join(DATA_DIR, "trade_signals.csv")
    WINRATE_FILE = os.path.join(DATA_DIR, "winrate_log.csv")

    # Scanning Settings
    DEFAULT_NUM_COINS = 50
    MAX_COINS = 200
    DEFAULT_TIMEFRAME = "1d"
    SUPPORTED_TIMEFRAMES = ["6h", "12h", "1d", "3d"]
    DEFAULT_PROB_THRESHOLD = 0.6
    MAX_SIGNALS_PER_SCAN = 3

    # Filtering Thresholds
    MIN_VOLUME_RATIO = 0.8
    MIN_VOLATILITY_PCT = 0.5
    MAX_VOLATILITY_PCT = 25.0
    MIN_MOMENTUM_PCT = 1.5

    # Timeframe-specific settings
    TIMEFRAME_SETTINGS = {
        '6h': {
            'profit_target_pct': 2.0,
            'stop_loss_pct': 1.0,
            'duration_hours': 6,
            'grace_hours': 6
        },
        '12h': {
            'profit_target_pct': 4.0,
            'stop_loss_pct': 2.0,
            'duration_hours': 12,
            'grace_hours': 12
        },
        '1d': {
            'profit_target_pct': 8.0,
            'stop_loss_pct': 4.0,
            'duration_hours': 24,
            'grace_hours': 12
        },
        '3d': {
            'profit_target_pct': 15.0,
            'stop_loss_pct': 8.0,
            'duration_hours': 72,
            'grace_hours': 24
        }
    }

    # Model Settings
    MODEL_FILE = os.getenv("MODEL_FILE", "latest_model.pkl")
    FEATURE_NAMES_FILE = "feature_names.pkl"
    FALLBACK_MODEL_FILE = os.getenv(
        "FALLBACK_MODEL_FILE", "cryptosight_v2_model_20250828_203611.pkl"
    )
    SCALER_FILE = "scaler.pkl"

    # Alert Settings -- pulled from the environment, never hardcoded.
    DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK", "")

    # Monitoring Settings
    VERIFICATION_INTERVAL_MINUTES = 5
    TRADE_TIMEOUT_HOURS = 48

    # Performance Settings
    NEAR_MISS_THRESHOLD_PCT = 0.2
    MIN_TRADES_FOR_STATS = 5

    # Logging Settings
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # Database (Render provides DATABASE_URL for its managed Postgres;
    # falls back to a local SQLite file so the app still runs without one)
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./cryptosight.db")

    # AI (OpenRouter) -- free models rotate constantly (an entire free
    # tier can get delisted with no warning, as happened to
    # llama-3.3-70b-instruct:free in July 2026). Default to OpenRouter's
    # own auto-router, which exists specifically to survive that: it
    # picks a currently-free model for you. Override with a specific
    # model ID via OPENROUTER_MODEL if you want to pin one deliberately.
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")
    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
    AI_SITE_URL = os.getenv("AI_SITE_URL", "https://cryptosight.example.com")
    AI_SITE_NAME = os.getenv("AI_SITE_NAME", "CryptoSight")

    # AI weight-tuning guardrails -- deliberately conservative. See
    # ai/accuracy_reviewer.py for how these are used.
    AI_MIN_SAMPLES_FOR_ADJUSTMENT = int(os.getenv("AI_MIN_SAMPLES_FOR_ADJUSTMENT", "20"))
    AI_MAX_WEIGHT_STEP_PCT = float(os.getenv("AI_MAX_WEIGHT_STEP_PCT", "0.20"))  # max +/-20% per run
    AI_MIN_STRATEGY_WEIGHT = float(os.getenv("AI_MIN_STRATEGY_WEIGHT", "0.1"))
    AI_MAX_STRATEGY_WEIGHT = float(os.getenv("AI_MAX_STRATEGY_WEIGHT", "5.0"))

    # Emergency kill switch: when true, every exchange call fails
    # immediately with no network attempt at all -- not even one. Set
    # this in Render's dashboard (no redeploy needed, just an env var
    # change) to test whether a persistent Binance ban is actually
    # self-perpetuating from ANY traffic reaching it, even the throttled,
    # once-per-cooldown-window traffic the app normally sends.
    EXCHANGE_PAUSED = os.getenv("EXCHANGE_PAUSED", "false").lower() == "true"

    # Admin panel
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
    SECRET_KEY = os.getenv("SECRET_KEY", "")

    @classmethod
    def get_timeframe_setting(cls, timeframe, key, default=None):
        """Get a specific setting for a timeframe"""
        return cls.TIMEFRAME_SETTINGS.get(timeframe, {}).get(key, default)

    @classmethod
    def ensure_directories(cls):
        """Ensure all required directories exist"""
        os.makedirs(cls.DATA_DIR, exist_ok=True)
        os.makedirs(cls.MODELS_DIR, exist_ok=True)
        os.makedirs(cls.LOGS_DIR, exist_ok=True)

    @classmethod
    def get_model_path(cls, filename=None):
        """Get full path to model file"""
        if filename is None:
            filename = cls.MODEL_FILE
        return os.path.join(cls.MODELS_DIR, filename)

    @classmethod
    def get_scaler_path(cls):
        """Get full path to scaler file"""
        return os.path.join(cls.MODELS_DIR, cls.SCALER_FILE)

    @classmethod
    def validate_timeframe(cls, timeframe):
        """Validate if timeframe is supported"""
        return timeframe in cls.SUPPORTED_TIMEFRAMES

    @classmethod
    def get_available_models(cls):
        """Get list of available model files"""
        model_files = []
        for filename in [cls.MODEL_FILE, cls.FALLBACK_MODEL_FILE]:
            model_path = cls.get_model_path(filename)
            if os.path.exists(model_path):
                model_files.append({
                    'name': filename,
                    'path': model_path,
                    'size': os.path.getsize(model_path)
                })
        return model_files

    @classmethod
    def setup_logging(cls):
        """Setup logging configuration"""
        os.makedirs(cls.LOGS_DIR, exist_ok=True)

        current_date = datetime.now().strftime("%Y%m%d")
        log_filename = os.path.join(cls.LOGS_DIR, f"cryptosight_{current_date}.log")

        logging.basicConfig(
            level=getattr(logging, cls.LOG_LEVEL),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_filename, encoding='utf-8'),
                logging.StreamHandler()
            ],
            force=True
        )

        logger = logging.getLogger(__name__)
        logger.info("Logging system initialized")
        logger.info(f"Log file: {log_filename}")


# Environment-specific overrides
class DevConfig(Config):
    """Development configuration"""
    MAX_SIGNALS_PER_SCAN = 1
    DEFAULT_NUM_COINS = 20


class ProdConfig(Config):
    """Production configuration"""
    pass


# Select configuration based on environment
config_mode = os.getenv('TRADING_BOT_MODE', 'prod').lower()
if config_mode == 'dev':
    config = DevConfig()
else:
    config = ProdConfig()
