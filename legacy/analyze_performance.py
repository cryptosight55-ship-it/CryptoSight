"""
Enhanced performance analysis script for the AI Crypto Trading Bot
Comprehensive analysis with detailed reporting and recommendations
"""

import sys
import os
from typing import Dict, List
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timezone, timedelta
import logging

from src.config import config
from winrate import winrate_analyzer
from trade_verifier import trade_verifier
from src.utils import performance_utils, time_utils

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PerformanceAnalyzer:
    """Enhanced performance analyzer with comprehensive reporting"""
    
    def __init__(self):
        self.trade_file = config.TRADE_LOG_FILE
        self.winrate_file = config.WINRATE_FILE
        self.report_data = {}
    
    def analyze_current_performance(self) -> Dict:
        """Comprehensive analysis of current bot performance"""
        logger.info("🔍 ANALYZING CURRENT BOT PERFORMANCE")
        logger.info("=" * 50)
        
        try:
            # Get comprehensive stats
            stats = winrate_analyzer.calculate_comprehensive_stats()
            
            if stats['total'] == 0:
                logger.warning("⚠️ No trade data found!")
                return {'error': 'No trade data available'}
            
            logger.info(f"📊 Total trades analyzed: {stats['total']}")
            
            # Basic performance metrics
            self._analyze_basic_metrics(stats)
            
            # Timeframe analysis
            self._analyze_timeframe_performance(stats)
            
            # Probability analysis
            self._analyze_probability_performance(stats)
            
            # Recent performance trends
            self._analyze_recent_trends(stats)
            
            # Risk analysis
            self._analyze_risk_metrics()
            
            self.report_data = stats
            return stats
            
        except Exception as e:
            logger.error(f"❌ Analysis failed: {e}")
            return {'error': str(e)}
    
    def _analyze_basic_metrics(self, stats: Dict):
        """Analyze basic performance metrics"""
        logger.info(f"\n📈 BASIC PERFORMANCE METRICS:")
        logger.info(f"   Win Rate: {stats['winrate']:.1f}%")
        logger.info(f"   Total Trades: {stats['total']}")
        logger.info(f"   Wins: {stats['wins']}")
        logger.info(f"   Losses: {stats['losses']}")
        logger.info(f"   Ties: {stats['ties']}")
        
        # Target breakdown
        logger.info(f"\n🎯 TARGET BREAKDOWN:")
        logger.info(f"   TP1 Hits: {stats['tp1_hits']}")
        logger.info(f"   TP2 Hits: {stats['tp2_hits']}")
        logger.info(f"   TP3 Hits: {stats['tp3_hits']}")
        
        # Calculate ratios
        if stats['total'] > 0:
            tie_rate = (stats['ties'] / stats['total']) * 100
            loss_rate = (stats['losses'] / stats['total']) * 100
            
            logger.info(f"\n📊 PERFORMANCE RATIOS:")
            logger.info(f"   Tie Rate: {tie_rate:.1f}%")
            logger.info(f"   Loss Rate: {loss_rate:.1f}%")
            
            # Performance assessment
            if stats['winrate'] >= 60:
                logger.info("✅ EXCELLENT: Win rate above 60%")
            elif stats['winrate'] >= 40:
                logger.info("⚠️ GOOD: Win rate between 40-60%")
            elif stats['winrate'] >= 25:
                logger.info("⚠️ FAIR: Win rate between 25-40%")
            else:
                logger.info("❌ POOR: Win rate below 25%")
    
    def _analyze_timeframe_performance(self, stats: Dict):
        """Analyze performance by timeframe"""
        timeframe_stats = stats.get('timeframe_stats', {})
        
        if timeframe_stats:
            logger.info(f"\n⏰ PERFORMANCE BY TIMEFRAME:")
            
            best_tf = None
            best_winrate = 0
            
            for tf, tf_data in timeframe_stats.items():
                logger.info(f"   {tf}: {tf_data['wins']}/{tf_data['total']} = {tf_data['winrate']:.1f}%")
                
                if tf_data['winrate'] > best_winrate and tf_data['total'] >= 5:
                    best_winrate = tf_data['winrate']
                    best_tf = tf
            
            if best_tf:
                logger.info(f"🏆 BEST TIMEFRAME: {best_tf} ({best_winrate:.1f}%)")
        else:
            logger.info("\n⏰ No timeframe data available")
    
    def _analyze_probability_performance(self, stats: Dict):
        """Analyze performance by AI confidence levels"""
        prob_stats = stats.get('probability_stats', {})
        
        if prob_stats:
            logger.info(f"\n🎲 PERFORMANCE BY AI CONFIDENCE:")
            
            for bucket, bucket_data in prob_stats.items():
                logger.info(f"   {bucket}: {bucket_data['wins']}/{bucket_data['total']} = {bucket_data['winrate']:.1f}%")
            
            # Find optimal threshold
            high_conf_buckets = [k for k in prob_stats.keys() if '80-' in k or '90-' in k]
            if high_conf_buckets:
                high_conf_winrate = np.mean([prob_stats[bucket]['winrate'] for bucket in high_conf_buckets])
                logger.info(f"💎 HIGH CONFIDENCE (80%+) WIN RATE: {high_conf_winrate:.1f}%")
        else:
            logger.info("\n🎲 No probability data available")
    
    def _analyze_recent_trends(self, stats: Dict):
        """Analyze recent performance trends"""
        recent_stats = stats.get('recent_stats', {})
        
        if recent_stats:
            logger.info(f"\n📅 RECENT PERFORMANCE (30 days):")
            logger.info(f"   Recent Trades: {recent_stats['total']}")
            logger.info(f"   Recent Win Rate: {recent_stats['winrate']:.1f}%")
            logger.info(f"   Recent Wins: {recent_stats['wins']}")
            
            # Compare with overall performance
            if recent_stats['total'] >= 10:
                trend = recent_stats['winrate'] - stats['winrate']
                if trend > 5:
                    logger.info("📈 IMPROVING: Recent performance is better")
                elif trend < -5:
                    logger.info("📉 DECLINING: Recent performance is worse")
                else:
                    logger.info("➡️ STABLE: Recent performance is consistent")
        else:
            logger.info("\n📅 No recent performance data available")
    
    def _analyze_risk_metrics(self):
        """Analyze risk-related metrics"""
        try:
            if not os.path.exists(self.winrate_file):
                return
            
            df = pd.read_csv(self.winrate_file)
            
            if df.empty or 'exit_price' not in df.columns:
                return
            
            # Calculate P&L for finished trades with exit prices
            finished_df = df.dropna(subset=['exit_price', 'entry', 'direction'])
            
            if finished_df.empty:
                return
            
            logger.info(f"\n💰 RISK ANALYSIS:")
            
            pnl_values = []
            for _, trade in finished_df.iterrows():
                pnl = performance_utils.calculate_pnl_percentage(
                    trade['entry'], trade['exit_price'], trade['direction']
                )
                pnl_values.append(pnl)
            
            if pnl_values:
                avg_pnl = np.mean(pnl_values)
                max_gain = max(pnl_values)
                max_loss = min(pnl_values)
                volatility = np.std(pnl_values)
                
                logger.info(f"   Average P&L: {avg_pnl:+.2f}%")
                logger.info(f"   Max Gain: {max_gain:+.2f}%")
                logger.info(f"   Max Loss: {max_loss:+.2f}%")
                logger.info(f"   P&L Volatility: {volatility:.2f}%")
                
                # Risk assessment
                if avg_pnl > 2:
                    logger.info("✅ POSITIVE: Average P&L is profitable")
                elif avg_pnl > -1:
                    logger.info("⚠️ NEUTRAL: Average P&L is near breakeven")
                else:
                    logger.info("❌ NEGATIVE: Average P&L is losing")
                    
        except Exception as e:
            logger.error(f"❌ Risk analysis failed: {e}")
    
    def generate_recommendations(self, stats: Dict) -> List[Dict]:
        """Generate specific improvement recommendations"""
        recommendations = []
        
        try:
            # Win rate recommendations
            if stats['winrate'] < 30:
                recommendations.append({
                    'priority': 'HIGH',
                    'category': 'Model Performance',
                    'issue': f'Low win rate ({stats["winrate"]:.1f}%)',
                    'solutions': [
                        'Retrain AI model with more recent data',
                        'Increase confidence threshold to 0.7+',
                        'Focus on 1d timeframe with proven performance',
                        'Reduce profit targets to more realistic levels'
                    ]
                })
            
            # Tie rate recommendations
            if stats['total'] > 0:
                tie_rate = (stats['ties'] / stats['total']) * 100
                if tie_rate > 60:
                    recommendations.append({
                        'priority': 'HIGH',
                        'category': 'Trade Parameters',
                        'issue': f'High tie rate ({tie_rate:.1f}%)',
                        'solutions': [
                            'Reduce profit targets by 20-30%',
                            'Increase trade duration',
                            'Use volatility-based targets instead of fixed percentages',
                            'Focus on trending markets'
                        ]
                    })
            
            # Timeframe recommendations
            timeframe_stats = stats.get('timeframe_stats', {})
            if timeframe_stats:
                best_tf = max(timeframe_stats.items(), 
                            key=lambda x: x[1]['winrate'] if x[1]['total'] >= 5 else 0)
                if best_tf[1]['total'] >= 5:
                    recommendations.append({
                        'priority': 'MEDIUM',
                        'category': 'Strategy Optimization',
                        'issue': f'Timeframe performance varies significantly',
                        'solutions': [
                            f'Focus on {best_tf[0]} timeframe (best performer)',
                            'Disable poorly performing timeframes',
                            'Adjust parameters per timeframe',
                            'Use timeframe-specific models'
                        ]
                    })
            
            # Data quality recommendations
            if stats['total'] < 50:
                recommendations.append({
                    'priority': 'MEDIUM',
                    'category': 'Data Collection',
                    'issue': 'Insufficient trade data for reliable analysis',
                    'solutions': [
                        'Run more frequent scans',
                        'Lower confidence threshold temporarily',
                        'Expand coin universe',
                        'Collect at least 100 trades before major changes'
                    ]
                })
            
        except Exception as e:
            logger.error(f"❌ Error generating recommendations: {e}")
        
        return recommendations
    
    def print_recommendations(self, recommendations: List[Dict]):
        """Print formatted recommendations"""
        if not recommendations:
            logger.info("\n💡 RECOMMENDATIONS:")
            logger.info("✅ No major issues detected! Continue current strategy.")
            return
        
        logger.info("\n💡 IMPROVEMENT RECOMMENDATIONS:")
        logger.info("=" * 50)
        
        for i, rec in enumerate(recommendations, 1):
            logger.info(f"\n{i}. 🔥 {rec['priority']} PRIORITY - {rec['category']}")
            logger.info(f"   Issue: {rec['issue']}")
            logger.info(f"   Solutions:")
            for solution in rec['solutions']:
                logger.info(f"     • {solution}")
    
    def generate_action_plan(self) -> List[Dict]:
        """Generate immediate action plan"""
        actions = [
            {
                'step': 1,
                'title': 'Data Quality Check',
                'description': 'Ensure data integrity and migrate recent trades',
                'commands': [
                    'python -c "from src.winrate import winrate_analyzer; winrate_analyzer.migrate_completed_trades()"',
                    'python -c "from src.winrate import winrate_analyzer; winrate_analyzer.clean_invalid_data()"'
                ],
                'time': '5 minutes'
            },
            {
                'step': 2,
                'title': 'Model Status Check',
                'description': 'Verify AI model is loaded and up to date',
                'actions': [
                    'Check if improved model exists',
                    'Retrain if model is over 30 days old',
                    'Validate model performance on recent data'
                ],
                'time': '10 minutes'
            },
            {
                'step': 3,
                'title': 'Parameter Optimization',
                'description': 'Adjust trading parameters based on analysis',
                'settings': {
                    'confidence_threshold': '0.65-0.7',
                    'profit_targets': 'Reduce by 20% if tie rate > 60%',
                    'timeframe': 'Focus on best performing timeframe',
                    'max_signals': 'Keep at 3 for quality control'
                },
                'time': '15 minutes'
            },
            {
                'step': 4,
                'title': 'Test New Settings',
                'description': 'Run limited test with optimized parameters',
                'actions': [
                    'Scan 50 coins with new settings',
                    'Accept maximum 2 signals',
                    'Monitor closely for 1 week',
                    'Document results for comparison'
                ],
                'time': '1 week monitoring'
            },
            {
                'step': 5,
                'title': 'Continuous Monitoring',
                'description': 'Establish regular monitoring routine',
                'actions': [
                    'Run this analysis weekly',
                    'Update model monthly',
                    'Adjust parameters based on market conditions',
                    'Maintain performance logs'
                ],
                'time': 'Ongoing'
            }
        ]
        
        return actions
    
    def print_action_plan(self, actions: List[Dict]):
        """Print formatted action plan"""
        logger.info("\n🎯 IMMEDIATE ACTION PLAN:")
        logger.info("=" * 50)
        
        for action in actions:
            logger.info(f"\n{action['step']}. {action['title']} ({action['time']})")
            logger.info(f"   📋 {action['description']}")
            
            if 'commands' in action:
                logger.info("   💻 Commands:")
                for cmd in action['commands']:
                    logger.info(f"      {cmd}")
            
            if 'settings' in action:
                logger.info("   ⚙️ Recommended Settings:")
                for key, value in action['settings'].items():
                    logger.info(f"      {key}: {value}")
            
            if 'actions' in action:
                logger.info("   📝 Steps:")
                for step in action['actions']:
                    logger.info(f"      • {step}")
    
    def create_performance_plots(self, stats: Dict):
        """Create performance visualization plots"""
        try:
            import matplotlib.pyplot as plt
            import seaborn as sns
            
            # Set style
            plt.style.use('seaborn-v0_8')
            sns.set_palette("husl")
            
            # Create subplots
            fig, axes = plt.subplots(2, 2, figsize=(15, 10))
            fig.suptitle('AI Crypto Trading Bot - Performance Analysis', fontsize=16)
            
            # 1. Win Rate Pie Chart
            if stats['total'] > 0:
                labels = ['Wins', 'Losses', 'Ties']
                sizes = [stats['wins'], stats['losses'], stats['ties']]
                colors = ['#2ecc71', '#e74c3c', '#f39c12']
                
                axes[0, 0].pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
                axes[0, 0].set_title('Trade Results Distribution')
            
            # 2. Timeframe Performance
            timeframe_stats = stats.get('timeframe_stats', {})
            if timeframe_stats:
                timeframes = list(timeframe_stats.keys())
                winrates = [timeframe_stats[tf]['winrate'] for tf in timeframes]
                
                axes[0, 1].bar(timeframes, winrates, color='#3498db')
                axes[0, 1].set_title('Win Rate by Timeframe')
                axes[0, 1].set_ylabel('Win Rate (%)')
                axes[0, 1].set_ylim(0, 100)
            
            # 3. Target Hit Distribution
            target_labels = ['TP1', 'TP2', 'TP3']
            target_values = [stats['tp1_hits'], stats['tp2_hits'], stats['tp3_hits']]
            
            axes[1, 0].bar(target_labels, target_values, color=['#27ae60', '#16a085', '#2c3e50'])
            axes[1, 0].set_title('Take Profit Hits Distribution')
            axes[1, 0].set_ylabel('Number of Hits')
            
            # 4. Probability Performance
            prob_stats = stats.get('probability_stats', {})
            if prob_stats:
                prob_buckets = list(prob_stats.keys())
                prob_winrates = [prob_stats[bucket]['winrate'] for bucket in prob_buckets]
                
                axes[1, 1].bar(prob_buckets, prob_winrates, color='#e67e22')
                axes[1, 1].set_title('Win Rate by AI Confidence')
                axes[1, 1].set_ylabel('Win Rate (%)')
                axes[1, 1].set_xticklabels(prob_buckets, rotation=45)
                axes[1, 1].set_ylim(0, 100)
            
            plt.tight_layout()
            
            # Save plot
            plot_filename = f"performance_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            plt.savefig(plot_filename, dpi=300, bbox_inches='tight')
            logger.info(f"📊 Performance plots saved: {plot_filename}")
            
            plt.show()
            
        except Exception as e:
            logger.error(f"❌ Failed to create plots: {e}")
    
    def run_complete_analysis(self):
        """Run complete performance analysis"""
        logger.info("🤖 AI CRYPTO TRADING BOT - PERFORMANCE ANALYZER")
        logger.info("🕐 " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"))
        logger.info("👤 User: samannazir55")
        logger.info("=" * 60)
        
        try:
            # Main analysis
            stats = self.analyze_current_performance()
            
            if 'error' in stats:
                logger.error(f"❌ Analysis failed: {stats['error']}")
                return
            
            # Generate recommendations
            recommendations = self.generate_recommendations(stats)
            self.print_recommendations(recommendations)
            
            # Generate action plan
            actions = self.generate_action_plan()
            self.print_action_plan(actions)
            
            # Create visualizations
            self.create_performance_plots(stats)
            
            logger.info(f"\n" + "=" * 60)
            logger.info("📊 Analysis complete! Follow the action plan to improve performance.")
            logger.info("🔄 Run this script again after implementing changes.")
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Complete analysis failed: {e}")
            return None

def main():
    """Main function"""
    analyzer = PerformanceAnalyzer()
    analyzer.run_complete_analysis()

if __name__ == "__main__":
    main()