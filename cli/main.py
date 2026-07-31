"""
Main entry point for CryptoSight v2.0
Command-line interface for the AI crypto trading bot
"""

import argparse
import logging
import sys
import asyncio
from datetime import datetime
from config.settings import config
from signals.generator import signal_generator
from database.performance_tracker import performance_tracker
from utils.helpers import logging_utils

def setup_logging(level: str = "INFO"):
    """Setup logging configuration"""
    logging_utils.setup_logging(level, "logs/cryptosight.log")

def run_scanner(timeframes: list, symbols: list, threshold: float, max_signals: int):
    """Run the signal scanner"""
    logger = logging.getLogger(__name__)
    
    try:
        # Initialize signal generator
        if not signal_generator.initialize():
            logger.error("❌ Failed to initialize signal generator")
            return False
        
        logger.info(f"🔍 Starting scan for {len(symbols)} symbols on {timeframes}")
        logger.info(f"🎯 Threshold: {threshold:.2f}, Max signals: {max_signals}")
        
        # Run scan
        signals = signal_generator.scan_multiple_symbols(
            symbols=symbols,
            timeframes=timeframes, 
            max_signals=max_signals,
            probability_threshold=threshold
        )
        
        if signals:
            logger.info(f"✅ Found {len(signals)} trading signals:")
            for signal in signals:
                logger.info(f"  📊 {signal['symbol']} {signal['timeframe']} {signal['direction']} "
                          f"(P: {signal['probability']:.3f})")
                
                # Log to performance tracker
                performance_tracker.log_signal(signal)
        else:
            logger.info("📝 No signals found in current scan")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Scanner error: {e}")
        return False

def show_performance(days: int):
    """Show performance summary"""
    logger = logging.getLogger(__name__)
    
    try:
        summary = performance_tracker.get_performance_summary(days)
        
        print(f"\n📊 Performance Summary (Last {days} days)")
        print("=" * 50)
        print(f"Total Trades: {summary['total_trades']}")
        print(f"Win Rate: {summary['win_rate']:.2f}%")
        print(f"Total P&L: {summary['total_pnl_pct']:+.2f}%")
        print(f"Avg Win: {summary['avg_win_pct']:+.2f}%")
        print(f"Avg Loss: {summary['avg_loss_pct']:+.2f}%")
        print(f"Profit Factor: {summary['profit_factor']:.2f}")
        print(f"Max Drawdown: {summary['max_drawdown_pct']:.2f}%")
        print(f"Sharpe Ratio: {summary['sharpe_ratio']:.2f}")
        
        if summary['timeframe_performance']:
            print("\n📈 Performance by Timeframe:")
            for tf, stats in summary['timeframe_performance'].items():
                print(f"  {tf}: {stats['trades']} trades, {stats['win_rate']:.1f}% win rate")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Performance analysis error: {e}")
        return False

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="CryptoSight v2.0 - AI Crypto Trading Bot")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="Logging level")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Scanner command
    scan_parser = subparsers.add_parser("scan", help="Run signal scanner")
    scan_parser.add_argument("--timeframes", nargs="+", default=["1d"], 
                           choices=config.SUPPORTED_TIMEFRAMES,
                           help="Timeframes to scan")
    scan_parser.add_argument("--symbols", nargs="+", 
                           default=["BTC/USDT", "ETH/USDT", "SOL/USDT", "ADA/USDT"],
                           help="Symbols to scan")
    scan_parser.add_argument("--threshold", type=float, default=0.6,
                           help="Minimum probability threshold")
    scan_parser.add_argument("--max-signals", type=int, default=3,
                           help="Maximum signals to return")
    
    # Performance command
    perf_parser = subparsers.add_parser("performance", help="Show performance summary")
    perf_parser.add_argument("--days", type=int, default=30,
                           help="Number of days to analyze")
    
    # Dashboard command
    subparsers.add_parser("dashboard", help="Launch Streamlit dashboard")
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    # Create directories
    config.ensure_directories()
    
    try:
        if args.command == "scan":
            success = run_scanner(args.timeframes, args.symbols, args.threshold, args.max_signals)
            sys.exit(0 if success else 1)
            
        elif args.command == "performance":
            success = show_performance(args.days)
            sys.exit(0 if success else 1)
            
        elif args.command == "dashboard":
            import subprocess
            subprocess.run(["streamlit", "run", "app.py"])
            
        else:
            parser.print_help()
            
    except KeyboardInterrupt:
        logger.info("👋 Shutdown requested by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()