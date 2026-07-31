"""
CryptoSight v2.0 - Streamlit Dashboard
Modern web interface for the AI crypto trading bot
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timezone, timedelta
import time
import requests
import ccxt
import os
import sys
import logging
from datetime import datetime

# Ensure all directories exist first
def ensure_project_directories():
    """Ensure all required directories exist"""
    directories = ['data', 'models', 'logs']
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✅ Directory ensured: {directory}")

# Setup logging before importing other modules
def setup_logging():
    """Setup logging configuration"""
    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)
    
    # Create log filename with current date  
    current_date = datetime.now().strftime("%Y%m%d")
    log_filename = os.path.join('logs', f"cryptosight_{current_date}.log")
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),
            logging.StreamHandler()
        ],
        force=True
    )
    
    logger = logging.getLogger(__name__)
    logger.info("🚀 CryptoSight Application Started")
    logger.info(f"👤 User: samannazir55")
    logger.info(f"📅 Date: 2025-08-30 09:15:07 UTC")

# Initialize directories and logging
ensure_project_directories()
setup_logging()
# Import our modules
from config.settings import config
from signals.generator import signal_generator
from database.performance_tracker import performance_tracker
from alerts.discord_alerts import alert_manager
from data.fetcher import get_data_fetcher
from strategies.ml_model.predictor import model_predictor

# Configure Streamlit page
st.set_page_config(
    page_title="CryptoSight v2.0",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 5px solid #1f77b4;
    }
    .success-box {
        background-color: #d4edda;
        color: #155724;
        padding: 0.75rem;
        border-radius: 0.25rem;
        border: 1px solid #c3e6cb;
    }
    .warning-box {
        background-color: #fff3cd;
        color: #856404;
        padding: 0.75rem;
        border-radius: 0.25rem;
        border: 1px solid #ffeaa7;
    }
    .coin-selector {
        max-height: 300px;
        overflow-y: auto;
        border: 1px solid #ddd;
        border-radius: 5px;
        padding: 10px;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_top_coins_binance():
    """Fetch top coins from Binance by 24h volume"""
    try:
        exchange = ccxt.binance()
        tickers = exchange.fetch_tickers()
        
        # Filter USDT pairs and extract data
        usdt_pairs = []
        for symbol, ticker in tickers.items():
            if '/USDT' in symbol and ticker['quoteVolume']:
                usdt_pairs.append({
                    'symbol': symbol,
                    'base_currency': symbol.split('/')[0],
                    'volume_24h': ticker['quoteVolume'],
                    'price': ticker['last'],
                    'change_24h': ticker['percentage'] or 0,
                    'market_cap_rank': None  # Binance doesn't provide market cap directly
                })
        
        # Sort by 24h volume
        usdt_pairs.sort(key=lambda x: x['volume_24h'], reverse=True)
        return usdt_pairs[:200]  # Top 200
        
    except Exception as e:
        st.error(f"Error fetching Binance data: {e}")
        return get_fallback_coins()

@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_top_coins_coingecko():
    """Fetch top coins from CoinGecko API"""
    try:
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            'vs_currency': 'usd',
            'order': 'volume_desc',
            'per_page': 200,
            'page': 1,
            'sparkline': False
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        coins = []
        for coin in data:
            # Try to match with Binance USDT pairs
            symbol = f"{coin['symbol'].upper()}/USDT"
            coins.append({
                'symbol': symbol,
                'base_currency': coin['symbol'].upper(),
                'name': coin['name'],
                'volume_24h': coin['total_volume'] or 0,
                'market_cap': coin['market_cap'] or 0,
                'price': coin['current_price'] or 0,
                'change_24h': coin['price_change_percentage_24h'] or 0,
                'market_cap_rank': coin['market_cap_rank'] or 999
            })
        
        return coins
        
    except Exception as e:
        st.error(f"Error fetching CoinGecko data: {e}")
        return get_fallback_coins()

def get_fallback_coins():
    """Fallback list of popular coins"""
    popular_coins = [
        'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT',
        'SOL/USDT', 'DOGE/USDT', 'DOT/USDT', 'MATIC/USDT', 'SHIB/USDT',
        'LTC/USDT', 'AVAX/USDT', 'LINK/USDT', 'UNI/USDT', 'ATOM/USDT',
        'XLM/USDT', 'VET/USDT', 'FIL/USDT', 'TRX/USDT', 'ETC/USDT',
        'ALGO/USDT', 'MANA/USDT', 'SAND/USDT', 'AXS/USDT', 'THETA/USDT'
    ]
    
    return [{'symbol': coin, 'base_currency': coin.split('/')[0], 'volume_24h': 0, 
             'price': 0, 'change_24h': 0, 'market_cap_rank': i+1} 
            for i, coin in enumerate(popular_coins)]

def init_session_state():
    """Initialize session state variables"""
    if 'scan_in_progress' not in st.session_state:
        st.session_state.scan_in_progress = False
    if 'last_scan_time' not in st.session_state:
        st.session_state.last_scan_time = None
    if 'scan_results' not in st.session_state:
        st.session_state.scan_results = []
    if 'top_coins' not in st.session_state:
        st.session_state.top_coins = []

def render_header():
    """Render dashboard header"""
    col1, col2, col3 = st.columns([3, 1, 1])
    
    with col1:
        st.title("🤖 CryptoSight v2.0")
        st.caption("AI-Powered Cryptocurrency Trading Bot")
    
    with col2:
        current_time = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        st.metric("Current Time", current_time)
    
    with col3:
        # Model status indicator
        try:
            if signal_generator.is_initialized:
                st.success("✅ AI Model Ready")
            else:
                st.warning("⚠️ Model Loading...")
        except:
            st.error("❌ Model Error")

def render_coin_selector():
    """Render advanced coin selector"""
    st.sidebar.subheader("💰 Smart Coin Selector")
    
    # Data source selection
    data_source = st.sidebar.radio(
        "Data Source",
        ["Binance (Volume)", "CoinGecko (Market Cap)", "Manual Entry"],
        help="Choose how to fetch coin data"
    )
    
    selected_symbols = []
    
    if data_source == "Manual Entry":
        # Original manual input
        default_symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'ADA/USDT', 'MATIC/USDT']
        symbol_input = st.sidebar.text_area(
            "Symbols to scan (one per line)",
            value='\n'.join(default_symbols),
            height=150
        )
        selected_symbols = [s.strip() for s in symbol_input.split('\n') if s.strip()]
        
    else:
        # Fetch top coins
        with st.sidebar.container():
            if st.button("🔄 Refresh Coin Data", help="Fetch latest coin data"):
                st.cache_data.clear()
            
            with st.spinner("Fetching coin data..."):
                if data_source == "Binance (Volume)":
                    coins_data = fetch_top_coins_binance()
                else:
                    coins_data = fetch_top_coins_coingecko()
                
                st.session_state.top_coins = coins_data
        
        if st.session_state.top_coins:
            # Filters
            st.sidebar.subheader("🔍 Filters")
            
            # Number of coins to show
            num_coins = st.sidebar.slider(
                "Number of Top Coins",
                min_value=10,
                max_value=min(200, len(st.session_state.top_coins)),
                value=50,
                step=10
            )
            
            # Volume filter (if available)
            if data_source == "Binance (Volume)":
                min_volume = st.sidebar.number_input(
                    "Min 24h Volume (USDT)",
                    min_value=0,
                    value=1000000,
                    step=100000,
                    format="%d",
                    help="Minimum 24h trading volume in USDT"
                )
                
                filtered_coins = [
                    coin for coin in st.session_state.top_coins 
                    if coin['volume_24h'] >= min_volume
                ][:num_coins]
            else:
                filtered_coins = st.session_state.top_coins[:num_coins]
            
            # Market cap rank filter (for CoinGecko)
            if data_source == "CoinGecko (Market Cap)":
                max_rank = st.sidebar.slider(
                    "Max Market Cap Rank",
                    min_value=1,
                    max_value=200,
                    value=100,
                    help="Only include coins within this market cap rank"
                )
                filtered_coins = [
                    coin for coin in filtered_coins 
                    if coin.get('market_cap_rank', 999) <= max_rank
                ]
            
            # Selection method
            selection_method = st.sidebar.radio(
                "Selection Method",
                ["Select All", "Select Top N", "Custom Selection"]
            )
            
            if selection_method == "Select All":
                selected_symbols = [coin['symbol'] for coin in filtered_coins]
                st.sidebar.success(f"✅ Selected {len(selected_symbols)} coins")
                
            elif selection_method == "Select Top N":
                top_n = st.sidebar.slider(
                    "Select Top N Coins",
                    min_value=1,
                    max_value=min(50, len(filtered_coins)),
                    value=min(10, len(filtered_coins))
                )
                selected_symbols = [coin['symbol'] for coin in filtered_coins[:top_n]]
                st.sidebar.success(f"✅ Selected top {top_n} coins")
                
            else:  # Custom Selection
                st.sidebar.write("Select specific coins:")
                
                # Create a more compact selection interface
                with st.sidebar.container():
                    st.markdown('<div class="coin-selector">', unsafe_allow_html=True)
                    
                    selected_symbols = []
                    
                    # Show coins in groups of 10
                    for i in range(0, len(filtered_coins), 10):
                        group = filtered_coins[i:i+10]
                        
                        # Group selector
                        group_key = f"group_{i//10}"
                        select_group = st.checkbox(
                            f"Select coins {i+1}-{min(i+10, len(filtered_coins))}",
                            key=group_key
                        )
                        
                        # Individual coin selectors
                        for coin in group:
                            symbol = coin['symbol']
                            base_currency = coin['base_currency']
                            
                            # Format display text
                            if data_source == "Binance (Volume)":
                                volume_str = f"${coin['volume_24h']:,.0f}" if coin['volume_24h'] else "N/A"
                                display_text = f"{base_currency} - Vol: {volume_str}"
                            else:
                                rank = coin.get('market_cap_rank', 'N/A')
                                display_text = f"{base_currency} - Rank #{rank}"
                            
                            is_selected = st.checkbox(
                                display_text,
                                value=select_group,
                                key=f"coin_{symbol}"
                            )
                            
                            if is_selected:
                                selected_symbols.append(symbol)
                    
                    st.markdown('</div>', unsafe_allow_html=True)
                
                if selected_symbols:
                    st.sidebar.success(f"✅ Selected {len(selected_symbols)} coins")
                else:
                    st.sidebar.warning("⚠️ No coins selected")
        
        else:
            st.sidebar.error("❌ Failed to fetch coin data")
            selected_symbols = ['BTC/USDT', 'ETH/USDT']  # Fallback
    
    return selected_symbols

def render_sidebar():
    """Render sidebar controls"""
    st.sidebar.header("🎯 Trading Controls")
    
    # Scanning settings
    st.sidebar.subheader("🔍 Signal Scanner")
    
    timeframes = st.sidebar.multiselect(
        "Timeframes", 
        options=config.SUPPORTED_TIMEFRAMES,
        default=["1d"]
    )
    
    probability_threshold = st.sidebar.slider(
        "Confidence Threshold", 
        min_value=0.5, 
        max_value=0.9, 
        value=0.6, 
        step=0.05
    )
    
    max_signals = st.sidebar.number_input(
        "Max Signals", 
        min_value=1, 
        max_value=20, 
        value=5
    )
    
    # Get selected symbols
    symbols = render_coin_selector()
    
    return {
        'timeframes': timeframes,
        'probability_threshold': probability_threshold,
        'max_signals': max_signals,
        'symbols': symbols
    }

def run_signal_scan(settings):
    """Run signal scanning"""
    if not signal_generator.is_initialized:
        if not signal_generator.initialize():
            st.error("❌ Failed to initialize AI model")
            return []
    
    with st.spinner(f"🔍 Scanning {len(settings['symbols'])} symbols for trading signals..."):
        try:
            signals = signal_generator.scan_multiple_symbols(
                symbols=settings['symbols'],
                timeframes=settings['timeframes'],
                max_signals=settings['max_signals'],
                probability_threshold=settings['probability_threshold']
            )
            
            # Log signals to performance tracker
            for signal in signals:
                performance_tracker.log_signal(signal)
            
            return signals
            
        except Exception as e:
            st.error(f"❌ Scanning error: {str(e)}")
            return []

def display_signals(signals):
    """Display trading signals"""
    if not signals:
        st.info("📝 No trading signals found with current settings")
        return
    
    st.subheader(f"🎯 Trading Signals ({len(signals)} found)")
    
    for i, signal in enumerate(signals):
        with st.expander(f"📊 {signal['symbol']} {signal['timeframe']} - {signal['direction']} (Confidence: {signal['probability']:.1%})"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Entry Price", f"${signal['entry']:.4f}")
                st.metric("Direction", signal['direction'])
                
            with col2:
                st.metric("Stop Loss", f"${signal['stop_loss']:.4f}")
                st.metric("Confidence", f"{signal['probability']:.1%}")
                
            with col3:
                st.metric("Take Profit 1", f"${signal['take_profit_1']:.4f}")
                st.metric("Take Profit 2", f"${signal['take_profit_2']:.4f}")
                st.metric("Take Profit 3", f"${signal['take_profit_3']:.4f}")
            
            # Risk/Reward calculation
            if signal['direction'] == 'LONG':
                risk = signal['entry'] - signal['stop_loss']
                reward = signal['take_profit_3'] - signal['entry']
            else:
                risk = signal['stop_loss'] - signal['entry']
                reward = signal['entry'] - signal['take_profit_3']
            
            risk_reward = reward / risk if risk > 0 else 0
            
            st.info(f"💡 Risk/Reward Ratio: {risk_reward:.2f}")
            
            # Alert button
            if st.button(f"🚀 Send Alert for {signal['symbol']}", key=f"alert_{i}"):
                success = alert_manager.send_discord_alert(signal)
                if success:
                    st.success("✅ Alert sent to Discord!")
                else:
                    st.error("❌ Failed to send alert")
# Add this to your streamlit app
def show_performance_dashboard():
    """Display performance tracking dashboard"""
    st.header("📊 Performance Dashboard")
    
    # Get performance stats
    stats = performance_tracker.get_performance_stats()
    active_trades = performance_tracker.get_active_trades_summary()
    
    # Performance metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Trades", stats['total'])
        st.metric("Win Rate", f"{stats['winrate']:.1f}%")
    
    with col2:
        st.metric("Wins", stats['wins'])
        st.metric("Losses", stats['losses'])
    
    with col3:
        st.metric("TP1 Hits", stats['tp1_hits'])
        st.metric("TP2 Hits", stats['tp2_hits'])
    
    with col4:
        st.metric("TP3 Hits", stats['tp3_hits'])
        st.metric("Active Trades", active_trades['active_count'])
    
    # Active trades table
    if active_trades['trades']:
        st.subheader("🔄 Active Trades")
        df = pd.DataFrame(active_trades['trades'])
        st.dataframe(df, use_container_width=True)
    
    # Recent completed trades
    if stats['recent_trades']:
        st.subheader("📋 Recent Completed Trades")
        df = pd.DataFrame(stats['recent_trades'])
        st.dataframe(df, use_container_width=True)

# Add this to your main streamlit app
show_performance_dashboard()
def display_performance():
    """Display performance metrics"""
    st.subheader("📊 Performance Analytics")
    
    # Get performance summary
    try:
        # Try to get performance data using available methods
        recent_signals = getattr(performance_tracker, 'get_recent_signals', lambda x: [])(100)  # Get more signals for analysis
        
        if recent_signals:
            # Calculate metrics from recent signals
            completed_trades = [s for s in recent_signals if s.get('status') == 'completed']
            winning_trades = [s for s in completed_trades if s.get('result', 0) > 0]
            
            summary = {
                'total_trades': len(completed_trades),
                'win_rate': (len(winning_trades) / len(completed_trades) * 100) if completed_trades else 0.0,
                'total_pnl_pct': sum(s.get('result', 0) for s in completed_trades),
                'profit_factor': abs(sum(s.get('result', 0) for s in winning_trades) / 
                                   sum(s.get('result', 0) for s in completed_trades if s.get('result', 0) < 0)) 
                                   if any(s.get('result', 0) < 0 for s in completed_trades) else 0.0
            }
        else:
            summary = {
                'total_trades': 0,
                'win_rate': 0.0,
                'total_pnl_pct': 0.0,
                'profit_factor': 0.0
            }
    except (AttributeError, Exception):
        # Fallback if method doesn't exist or any other error
        summary = {
            'total_trades': 0,
            'win_rate': 0.0,
            'total_pnl_pct': 0.0,
            'profit_factor': 0.0
        }
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Trades", 
            summary['total_trades'],
            help="Total number of completed trades"
        )
        
    with col2:
        st.metric(
            "Win Rate", 
            f"{summary['win_rate']:.1f}%",
            help="Percentage of profitable trades"
        )
        
    with col3:
        st.metric(
            "Total P&L", 
            f"{summary['total_pnl_pct']:+.2f}%",
            delta=f"{summary['total_pnl_pct']:+.2f}%",
            help="Total profit/loss percentage"
        )
        
    with col4:
        st.metric(
            "Profit Factor", 
            f"{summary['profit_factor']:.2f}",
            help="Ratio of gross profit to gross loss"
        )
    
    # Recent signals
    st.subheader("📋 Recent Signals")
    try:
        # Try to get recent signals if method exists
        recent_signals = getattr(performance_tracker, 'get_recent_signals', lambda: [])()
        
        if recent_signals:
            df = pd.DataFrame(recent_signals)
            df['signal_time'] = pd.to_datetime(df['signal_time'])
            
            # Display as table
            display_df = df[['symbol', 'timeframe', 'direction', 'probability', 'status', 'result']].copy()
            display_df['probability'] = display_df['probability'].apply(lambda x: f"{x:.1%}")
            
            st.dataframe(
                display_df,
                use_container_width=True,
                height=300
            )
        else:
            st.info("📝 No recent signals found")
    except (AttributeError, Exception):
        st.info("📝 Signal history not available")

def main():
    """Main dashboard function"""
    init_session_state()
    render_header()
    
    # Sidebar settings
    settings = render_sidebar()
    
    # Main content tabs
    tab1, tab2, tab3 = st.tabs(["🔍 Signal Scanner", "📊 Performance", "⚙️ Settings"])
    
    with tab1:
        st.header("🔍 Trading Signal Scanner")
        
        # Display selected symbols info
        if settings['symbols']:
            st.info(f"🎯 Ready to scan {len(settings['symbols'])} symbols: {', '.join(settings['symbols'][:5])}{'...' if len(settings['symbols']) > 5 else ''}")
        
        # Scan button
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            if st.button("🚀 Run Scan", type="primary", disabled=st.session_state.scan_in_progress or not settings['symbols']):
                st.session_state.scan_in_progress = True
                signals = run_signal_scan(settings)
                st.session_state.scan_results = signals
                st.session_state.last_scan_time = datetime.now(timezone.utc)
                st.session_state.scan_in_progress = False
                st.rerun()
        
        with col2:
            if st.session_state.last_scan_time:
                time_since = datetime.now(timezone.utc) - st.session_state.last_scan_time
                st.info(f"⏰ Last scan: {time_since.seconds // 60}m ago")
        
        # Display results
        if st.session_state.scan_results:
            display_signals(st.session_state.scan_results)
    
    with tab2:
        display_performance()
    
    with tab3:
        st.header("⚙️ Configuration")
        
        st.subheader("🔧 Current Settings")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.json({
                "Supported Timeframes": config.SUPPORTED_TIMEFRAMES,
                "Default Coins": config.DEFAULT_NUM_COINS,
                "Max Signals": config.MAX_SIGNALS_PER_SCAN,
                "Min Volume Ratio": config.MIN_VOLUME_RATIO,
                "Min Volatility": f"{config.MIN_VOLATILITY_PCT}%"
            })
        
        with col2:
            st.json({
                "Max Volatility": f"{config.MAX_VOLATILITY_PCT}%",
                "Min Momentum": f"{config.MIN_MOMENTUM_PCT}%",
                "Discord Webhook": "Configured" if config.DISCORD_WEBHOOK else "Not Set",
                "Data Directory": config.DATA_DIR,
                "Models Directory": config.MODELS_DIR
            })
        
        st.subheader("📁 Directory Status")
        
        directories = [
            (config.DATA_DIR, "Data files"),
            (config.MODELS_DIR, "AI models"),
            ("logs", "Log files")
        ]
        
        for dir_path, description in directories:
            import os
            if os.path.exists(dir_path):
                st.success(f"✅ {description}: {dir_path}")
            else:
                st.warning(f"⚠️ {description}: {dir_path} (missing)")

if __name__ == "__main__":
    main()