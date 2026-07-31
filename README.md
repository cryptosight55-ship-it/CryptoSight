# 🤖 CryptoSight v2.0 - AI Crypto Trading Bot

A professional-grade, AI-powered cryptocurrency trading bot with advanced signal generation, comprehensive market analysis, and real-time performance tracking.

## ✨ What's New in v2.0

- **🏗️ Complete Architecture Rebuild**: Clean modular structure with proper imports
- **🧠 Enhanced AI Model System**: Improved feature engineering and model management
- **🎯 Advanced Signal Generation**: Multi-timeframe analysis with dynamic risk management  
- **📊 Comprehensive Analytics**: Real-time performance tracking and reporting
- **🌐 Modern Web Interface**: Streamlit dashboard with interactive controls
- **⚡ Command-Line Interface**: Easy-to-use CLI for automated scanning
- **🔧 Professional Setup**: Proper package structure with setup.py

## 🌟 Core Features

### 🧠 AI-Powered Signal Generation
- **RandomForest Classifier** with probability calibration
- **40+ Technical Indicators**: Trend, momentum, volatility, and volume analysis
- **Multi-Timeframe Support**: 6h, 12h, 1d, 3d strategies
- **Dynamic Risk Management**: Volatility-adjusted stop losses and targets
- **Market Filtering**: Volume, momentum, and trend strength requirements

### 📊 Comprehensive Market Analysis
- **Technical Indicators**: SMA, EMA, RSI, MACD, ADX, ATR, Bollinger Bands, Stochastic
- **Candlestick Patterns**: Hammer, Doji, Engulfing, Morning Star, and more
- **Volume Analysis**: OBV, MFI, A/D Line, volume ratio confirmation
- **Market Structure**: Support/resistance levels, gap analysis

### 🎯 Advanced Filtering & Risk Management
- **Volume Filter**: Recent vs average volume ratio analysis
- **Volatility Filter**: ATR-based market condition screening  
- **Momentum Filter**: Multi-period momentum requirements
- **Dynamic Targets**: Volatility-adjusted profit and stop levels

### 🔔 Alert & Monitoring System
- **Discord Integration**: Rich embed notifications with trade details
- **Real-Time Tracking**: Automated trade monitoring and verification
- **Performance Analytics**: Win rate, P&L, and risk metrics
- **Status Updates**: Live trade status and result notifications

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/samannazir55/ai-crypto-trading-bot.git
cd ai-crypto-trading-bot

# Install dependencies
pip install -r requirements.txt

# Install the package (optional)
pip install -e .
```

### 2. Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit configuration (optional - defaults work for signals-only mode)
nano .env
```

### 3. Quick Test

```bash
# Run performance summary
python -m src.main performance

# Scan for signals
python -m src.main scan --timeframes 1d --threshold 0.6

# Launch web dashboard
python -m src.main dashboard
# or
streamlit run app.py
```

## 📁 Project Structure

```
/
├── src/                          # Core modules
│   ├── config.py                 # Centralized configuration
│   ├── data_fetcher.py          # Exchange data fetching
│   ├── feature_engineer.py     # Technical analysis
│   ├── model_predictor.py       # AI model interface
│   ├── signal_generator.py     # Trading signal logic
│   ├── trade_monitor.py         # Trade tracking
│   ├── alert_manager.py         # Discord notifications
│   ├── performance_tracker.py   # Analytics
│   ├── utils.py                 # Helper functions
│   └── main.py                  # CLI entry point
├── models/                      # AI model storage
├── data/                        # Data files
├── logs/                        # Log files
├── app.py                       # Streamlit dashboard
├── requirements.txt             # Dependencies
├── setup.py                     # Package setup
├── .env.example                 # Environment template
└── README.md                    # Documentation
```

## 🔧 Usage

### Command Line Interface

```bash
# Show help
python -m src.main --help

# Scan for trading signals
python -m src.main scan \
  --timeframes 1d 12h \
  --symbols BTC/USDT ETH/USDT SOL/USDT \
  --threshold 0.7 \
  --max-signals 5

# View performance analytics
python -m src.main performance --days 30

# Launch web dashboard
python -m src.main dashboard
```

### Web Dashboard

```bash
# Start Streamlit dashboard
streamlit run app.py

# Open in browser
# http://localhost:8501
```

The dashboard provides:
- **🔍 Signal Scanner**: Interactive scanning with real-time results
- **📊 Performance Analytics**: Comprehensive statistics and charts
- **⚙️ Configuration**: Settings and system status

### Python API

```python
from src.signal_generator import signal_generator
from src.performance_tracker import performance_tracker

# Initialize signal generator
signal_generator.initialize()

# Generate signals
signals = signal_generator.scan_multiple_symbols(
    symbols=['BTC/USDT', 'ETH/USDT'],
    timeframes=['1d'],
    probability_threshold=0.6
)

# View performance
summary = performance_tracker.get_performance_summary(30)
print(f"Win Rate: {summary['win_rate']:.1f}%")
```

## ⚙️ Configuration

### Environment Variables

```bash
# Trading mode
TRADING_BOT_MODE=prod           # dev/prod

# Discord alerts (optional)
DISCORD_WEBHOOK=your_webhook_url

# Model settings
MODEL_FILE=BTC_USDT_rf_improved.pkl
DEFAULT_PROBABILITY_THRESHOLD=0.6

# Risk management
MIN_VOLUME_RATIO=0.8
MIN_VOLATILITY_PCT=0.5
MAX_VOLATILITY_PCT=25.0

# Logging
LOG_LEVEL=INFO
```

### Timeframe Settings

Each timeframe has specific risk/reward parameters:

- **6h**: 2% profit target, 1% stop loss
- **12h**: 4% profit target, 2% stop loss  
- **1d**: 8% profit target, 4% stop loss
- **3d**: 15% profit target, 8% stop loss

## 📊 AI Model Details

### Feature Engineering (40+ Indicators)

**Trend Indicators:**
- Simple/Exponential Moving Averages (5, 10, 20, 50)
- MACD (Line, Signal, Histogram)
- ADX (Trend Strength)
- Parabolic SAR
- Aroon Oscillator

**Momentum Indicators:**
- RSI (14, 21 periods)
- Stochastic Oscillator
- Williams %R
- Rate of Change
- Money Flow Index

**Volatility Indicators:**
- Average True Range (ATR)
- Bollinger Bands
- Keltner Channels
- Standard Deviation

**Volume Indicators:**
- On-Balance Volume (OBV)
- Accumulation/Distribution Line
- Volume Rate of Change
- Volume Moving Averages

**Pattern Recognition:**
- Candlestick patterns (Hammer, Doji, Engulfing, etc.)
- Price action signals
- Support/resistance breaks

### Model Training

```python
# Model: RandomForestClassifier
# - n_estimators: 100
# - max_depth: 10
# - Probability calibration enabled
# - SMOTE for class balancing
# - Feature importance analysis
```

## 🔔 Discord Integration

Configure Discord alerts for real-time notifications:

1. Create a Discord webhook in your server
2. Add webhook URL to `.env` file:
   ```
   DISCORD_WEBHOOK=https://discord.com/api/webhooks/YOUR_WEBHOOK
   ```
3. Alerts include:
   - 🎯 New trading signals with full details
   - ✅ Trade completions and results
   - 📊 Daily performance summaries

## 📈 Performance Analytics

The system tracks comprehensive metrics:

- **Win Rate**: Overall and by timeframe/confidence
- **P&L Analysis**: Total returns and risk-adjusted metrics
- **Target Analysis**: TP1/TP2/TP3 hit rates
- **Risk Metrics**: Maximum drawdown, Sharpe ratio
- **Duration Analysis**: Average trade duration
- **Confidence Correlation**: Performance vs AI confidence

## 🔧 Advanced Configuration

### Custom Symbol Lists

```python
# In your scanning script
symbols = [
    'BTC/USDT', 'ETH/USDT', 'BNB/USDT',
    'ADA/USDT', 'SOL/USDT', 'MATIC/USDT',
    'DOT/USDT', 'LINK/USDT', 'AVAX/USDT'
]
```

### Model Customization

```python
# Load custom model
from src.model_predictor import ModelPredictor

predictor = ModelPredictor()
predictor.load_model('path/to/your/model.pkl')
```

### Custom Filters

```python
# Modify filtering parameters in src/config.py
MIN_VOLUME_RATIO = 0.8      # 80% of average volume
MIN_VOLATILITY_PCT = 0.5    # Minimum 0.5% volatility
MAX_VOLATILITY_PCT = 25.0   # Maximum 25% volatility
MIN_MOMENTUM_PCT = 1.5      # Minimum 1.5% momentum
```

## 🚨 Important Notes

### Risk Disclaimer
- This is an educational/analysis tool, not financial advice
- Past performance doesn't guarantee future results
- Always do your own research before trading
- Start with small amounts and paper trading

### Usage Recommendations
- Monitor signals manually before trusting them
- Verify signals with additional analysis
- Use proper risk management (position sizing, diversification)
- Keep detailed trade logs for performance analysis

## 🔍 Troubleshooting

### Common Issues

**Import Errors:**
```bash
# Ensure you're in the project directory
cd ai-crypto-trading-bot

# Try running with module syntax
python -m src.main --help
```

**Network Errors:**
- Check internet connection for Binance API access
- Consider using VPN if API access is restricted

**Model Loading Issues:**
- Ensure `models/` directory exists
- Check that model files are present
- Verify model compatibility

**Performance Issues:**
- Reduce number of symbols for faster scanning
- Use higher probability thresholds for fewer signals
- Consider running on more powerful hardware

### Logs and Debugging

```bash
# Enable debug logging
python -m src.main scan --log-level DEBUG

# Check log files
tail -f logs/cryptosight.log
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/samannazir55/ai-crypto-trading-bot/issues)
- **Discussions**: [GitHub Discussions](https://github.com/samannazir55/ai-crypto-trading-bot/discussions)
- **Email**: Contact repository owner

---

**⚠️ Disclaimer**: This software is for educational and research purposes only. Cryptocurrency trading involves substantial risk of loss. The authors are not responsible for any financial losses incurred through the use of this software.