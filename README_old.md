# 🤖 AI-Powered Cryptocurrency Trading Bot

A sophisticated, production-ready cryptocurrency trading bot powered by machine learning, featuring comprehensive market analysis, real-time monitoring, and intelligent signal generation.

## 🌟 Features

### 🧠 AI-Powered Signal Generation
- **Machine Learning Model**: RandomForestClassifier with calibrated probabilities
- **Multi-Timeframe Analysis**: 6h, 12h, 1d, 3d trading strategies
- **SMOTE Oversampling**: Balanced training data for better predictions
- **Dynamic Thresholds**: Configurable confidence levels (0.5-0.9)

### 📊 Comprehensive Market Analysis
- **Technical Indicators**: 40+ indicators including RSI, MACD, ADX, Bollinger Bands
- **Candlestick Patterns**: 15+ pattern recognition (Hammer, Doji, Engulfing, etc.)
- **Volume Analysis**: Volume confirmation and ratio filtering
- **Volatility Screening**: ATR-based volatility filtering

### 🎯 Advanced Filtering System
- **Volume Ratio Filter**: Recent vs average volume analysis
- **Volatility Filter**: ATR-based market conditions
- **Momentum Filter**: Multi-period momentum requirements
- **Trend Strength**: ADX-based trend confirmation

### 📈 Real-Time Monitoring
- **Live Trade Tracking**: Real-time P&L monitoring
- **Automated Verification**: Background trade result verification
- **Grace Period Management**: Configurable grace periods for trade completion
- **Status Updates**: Automatic trade status transitions

### 🎨 Enhanced Dashboard
- **Streamlit Interface**: Modern, responsive web interface
- **Real-Time Charts**: Interactive performance visualizations
- **Live Scanning**: Progress tracking with real-time updates
- **Performance Analytics**: Comprehensive statistics and trends

### 🔔 Alert System
- **Discord Integration**: Rich embed notifications
- **Trade Signals**: Detailed trade parameters and analysis
- **Result Updates**: Automatic trade completion notifications
- **Daily Summaries**: Performance overview alerts

### 📊 Performance Analytics
- **Win Rate Analysis**: Overall and segmented performance
- **Timeframe Breakdown**: Performance by trading timeframe
- **Confidence Analysis**: Results by AI confidence levels
- **Risk Metrics**: P&L analysis and volatility tracking

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- TA-Lib library
- Binance account (for data access)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/samannazir55/ai-crypto-trading-bot.git
cd ai-crypto-trading-bot
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Install TA-Lib**
```bash
# On Ubuntu/Debian
sudo apt-get install libta-lib-dev
pip install TA-Lib

# On macOS
brew install ta-lib
pip install TA-Lib

# On Windows
# Download TA-Lib from https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib
pip install TA_Lib-0.4.24-cp39-cp39-win_amd64.whl
```

4. **Set up configuration**
```bash
# Edit src/config.py to customize settings
# Add your Discord webhook URL (optional)
```

5. **Train the AI model**
```bash
# Run the training notebooks in order:
jupyter notebook notebooks/01_download_data.ipynb
jupyter notebook notebooks/02_feature_extraction.ipynb
jupyter notebook notebooks/03_label_targets.ipynb
jupyter notebook notebooks/04_improved_training.ipynb

# Or use the automated trainer:
python auto_train_models.py
```

6. **Launch the dashboard**
```bash
streamlit run app.py
```

## 📁 Project Structure

```
ai-crypto-trading-bot/
├── src/                          # Core source code
│   ├── config.py                 # Configuration management
│   ├── data_fetcher.py          # Market data acquisition
│   ├── feature_engineer.py     # Technical analysis
│   ├── predictor.py             # AI model interface
│   ├── trade_scanner.py         # Signal generation
│   ├── trade_monitor.py         # Trade tracking
│   ├── trade_verifier.py        # Result verification
│   ├── winrate.py               # Performance analytics
│   ├── alert.py                 # Notification system
│   └── utils.py                 # Utility functions
├── notebooks/                    # Jupyter notebooks
│   ├── 01_download_data.ipynb   # Data collection
│   ├── 02_feature_extraction.ipynb  # Feature engineering
│   ├── 03_label_targets.ipynb   # Target labeling
│   └── 04_improved_training.ipynb   # Model training
├── scripts/                      # Utility scripts
│   ├── analyze_performance.py   # Performance analysis
│   ├── quick_fix.py            # Quick fixes
│   └── auto_train_models.py    # Automated training
├── data/                        # Data storage
├── models/                      # Trained models
├── backups/                     # Data backups
├── app.py                       # Streamlit dashboard
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

## ⚙️ Configuration

### Core Settings (`src/config.py`)

```python
# Scanner Settings
DEFAULT_NUM_COINS = 50           # Coins to scan
DEFAULT_TIMEFRAME = "1d"         # Default timeframe
DEFAULT_PROB_THRESHOLD = 0.6     # AI confidence threshold
MAX_SIGNALS_PER_SCAN = 3         # Quality control

# Filtering Thresholds
MIN_VOLUME_RATIO = 0.8           # Volume filter
MIN_VOLATILITY_PCT = 0.5         # Min volatility
MAX_VOLATILITY_PCT = 25.0        # Max volatility
MIN_MOMENTUM_PCT = 1.5           # Momentum requirement
```

### Timeframe-Specific Settings

```python
TIMEFRAME_SETTINGS = {
    '6h': {
        'profit_target_pct': 2.0,    # 2% profit target
        'stop_loss_pct': 1.0,        # 1% stop loss
        'duration_hours': 6,         # 6 hour duration
        'grace_hours': 6             # 6 hour grace period
    },
    '1d': {
        'profit_target_pct': 8.0,    # 8% profit target
        'stop_loss_pct': 4.0,        # 4% stop loss
        'duration_hours': 24,        # 24 hour duration
        'grace_hours': 12            # 12 hour grace period
    }
    # ... more timeframes
}
```

## 🎯 Trading Strategy

### Signal Generation Process

1. **Market Filtering**
   - Volume ratio > 0.8 (recent vs average)
   - Volatility between 0.5% and 25%
   - Momentum > 1.5%
   - Trend strength confirmation

2. **Technical Analysis**
   - Extract 40+ technical indicators
   - Calculate candlestick patterns
   - Multi-timeframe context (BTC, ETH, SOL)

3. **AI Prediction**
   - RandomForest with calibrated probabilities
   - Confidence threshold filtering
   - Multi-timeframe training data

4. **Risk Management**
   - Dynamic stop losses based on volatility
   - Multiple take profit levels (TP1, TP2, TP3)
   - Position sizing recommendations

### Trade Management

- **Entry**: Current market price at signal generation
- **Stop Loss**: ATR-based dynamic calculation
- **Take Profits**: Scaled targets (1x, 1.25x, 1.5x base target)
- **Duration**: Timeframe-specific (6h to 3 days)
- **Direction**: LONG/SHORT based on technical analysis

## 📊 Performance Monitoring

### Key Metrics

- **Win Rate**: Percentage of profitable trades
- **Target Breakdown**: TP1/TP2/TP3 hit distribution
- **Timeframe Analysis**: Performance by timeframe
- **Confidence Analysis**: Results by AI confidence
- **Risk Metrics**: P&L distribution and volatility

### Analysis Tools

```bash
# Run comprehensive performance analysis
python scripts/analyze_performance.py

# Quick performance fixes
python scripts/quick_fix.py

# Clean corrupted data
python -c "from src.winrate import winrate_analyzer; winrate_analyzer.clean_invalid_data()"
```

## 🔔 Alert Configuration

### Discord Webhook Setup

1. Create a Discord server and channel
2. Go to Channel Settings > Integrations > Webhooks
3. Create a new webhook and copy the URL
4. Update `src/config.py`:

```python
DISCORD_WEBHOOK = "your_webhook_url_here"
```

### Alert Types

- **Trade Signals**: New trading opportunities
- **Trade Updates**: Position exits and results
- **Daily Summaries**: Performance overviews
- **System Alerts**: Error notifications

## 🛠️ Advanced Usage

### Custom Model Training

```python
# Train with custom parameters
from notebooks.improved_training import train_improved_model

# Modify settings in the notebook
LOOKBACK_DAYS = 730  # 2 years of data
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'ADA/USDT']
TIMEFRAMES = ['6h', '12h', '1d', '3d']

# Run training
train_improved_model()
```

### Automated Monitoring

```python
# Start automated trade monitoring
from src.trade_monitor import trade_monitor

trade_monitor.start_monitoring(interval_minutes=5)
```

### Custom Scanning

```python
# Run custom scan
from src.trade_scanner import trade_scanner

results = trade_scanner.scan_trades(
    num_coins=100,
    timeframe="1d",
    prob_threshold=0.7,
    max_signals=5
)
```

## 🔧 Troubleshooting

### Common Issues

1. **Model Not Found**
   ```bash
   # Train the model first
   python auto_train_models.py
   ```

2. **TA-Lib Installation Issues**
   ```bash
   # On Ubuntu
   sudo apt-get install libta-lib-dev
   
   # On macOS
   brew install ta-lib
   ```

3. **Data Corruption**
   ```bash
   # Clean corrupted data
   python scripts/quick_fix.py
   ```

4. **Performance Issues**
   ```bash
   # Analyze performance and get recommendations
   python scripts/analyze_performance.py
   ```

### Log Files

- Application logs: `logs/trading_bot.log`
- Error logs: Check console output
- Performance logs: Generated by analysis scripts

## 📈 Best Practices

### Recommended Settings

- **Timeframe**: Start with 1d for better success rates
- **Confidence Threshold**: 0.65-0.7 for quality signals
- **Coin Universe**: 50-100 top coins by volume
- **Max Signals**: 3 per scan for quality control

### Risk Management

- Never risk more than you can afford to lose
- Use proper position sizing (1-2% per trade)
- Monitor trades regularly
- Adjust parameters based on market conditions

### Performance Optimization

1. **Regular Model Updates**: Retrain monthly
2. **Parameter Tuning**: Adjust based on performance
3. **Market Adaptation**: Monitor changing conditions
4. **Data Quality**: Keep clean, validated data

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## ⚠️ Disclaimer

This bot is for educational and research purposes only. Cryptocurrency trading involves significant risk of loss. The authors are not responsible for any financial losses incurred through the use of this software.

**Important Notes:**
- Past performance does not guarantee future results
- Always do your own research (DYOR)
- Never invest more than you can afford to lose
- Consider paper trading before live trading

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **ccxt**: Cryptocurrency exchange library
- **TA-Lib**: Technical analysis library
- **scikit-learn**: Machine learning framework
- **Streamlit**: Web application framework
- **Community**: Thanks to all contributors and users

## 📞 Support

- **GitHub Issues**: For bug reports and feature requests
- **Discord**: Join our community (webhook setup required)
- **Documentation**: Check the docs/ folder for detailed guides

---

**Happy Trading! 🚀📈**

*Built with ❤️ for the cryptocurrency community*