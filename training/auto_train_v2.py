"""
CryptoSight 2.0 - Auto Training Script
Updated to handle multiple labeled files from the new data structure
"""

import pandas as pd
import numpy as np
import joblib
import os
import sys
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import warnings
import glob

# ML imports
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import RobustScaler
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
from sklearn.calibration import CalibratedClassifierCV
from imblearn.over_sampling import SMOTE

# Add project paths
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, 'ai-crypto-trading-bot', 'src'))

warnings.filterwarnings('ignore')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('auto_training_v2.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration for CryptoSight 2.0
LABELED_FOLDER = 'data/labeled'
MODELS_FOLDER = 'models'
FEATURES_FOLDER = 'data/features'

class CryptoSightAutoTrainer:
    """Auto trainer for CryptoSight 2.0 multi-file structure"""
    
    def __init__(self):
        self.feature_names = None
        self.scaler = None
        self.training_stats = {}
        
        # Ensure folders exist
        os.makedirs(MODELS_FOLDER, exist_ok=True)
        os.makedirs(LABELED_FOLDER, exist_ok=True)
    
    def discover_labeled_files(self) -> List[str]:
        """Discover all labeled CSV files in the labeled folder"""
        try:
            pattern = os.path.join(LABELED_FOLDER, 'labeled_*.csv')
            labeled_files = glob.glob(pattern)
            
            logger.info(f"Discovered {len(labeled_files)} labeled files:")
            for file in labeled_files:
                filename = os.path.basename(file)
                file_size = os.path.getsize(file)
                logger.info(f"  {filename} ({file_size:,} bytes)")
            
            return labeled_files
            
        except Exception as e:
            logger.error(f"Error discovering labeled files: {e}")
            return []
    
    def load_and_combine_labeled_data(self, max_samples_per_file: int = 1000) -> Optional[pd.DataFrame]:
        """Load and intelligently combine all labeled data files"""
        try:
            labeled_files = self.discover_labeled_files()
            
            if not labeled_files:
                logger.error("No labeled files found!")
                return None
            
            all_data = []
            file_stats = {}
            
            for file_path in labeled_files:
                filename = os.path.basename(file_path)
                try:
                    logger.info(f"Loading {filename}...")
                    
                    # Load file
                    df = pd.read_csv(file_path, parse_dates=['timestamp'])
                    
                    # Sample data if file is too large (for speed)
                    original_size = len(df)
                    if len(df) > max_samples_per_file:
                        df = df.sample(n=max_samples_per_file, random_state=42)
                        logger.info(f"  Sampled {max_samples_per_file} from {original_size} rows")
                    
                    # Add metadata columns for tracking
                    parts = filename.replace('labeled_', '').replace('.csv', '').split('_')
                    if len(parts) >= 3:
                        df['source_symbol'] = parts[0] + '_' + parts[1]  # BTC_USDT
                        df['source_timeframe'] = parts[2]  # 12h
                    else:
                        df['source_symbol'] = filename
                        df['source_timeframe'] = 'unknown'
                    
                    all_data.append(df)
                    
                    # Track stats
                    file_stats[filename] = {
                        'original_rows': original_size,
                        'used_rows': len(df),
                        'target_distribution': df['target'].value_counts().to_dict()
                    }
                    
                    logger.info(f"  [OK] Loaded {len(df)} rows")
                    
                except Exception as e:
                    logger.error(f"  ❌ Error loading {filename}: {e}")
                    continue
            
            if not all_data:
                logger.error("No data successfully loaded!")
                return None
            
            # Combine all data
            combined_df = pd.concat(all_data, ignore_index=True)
            logger.info(f"Combined dataset: {len(combined_df)} total samples from {len(all_data)} files")
            
            # Show overall target distribution
            target_counts = combined_df['target'].value_counts()
            for target, count in target_counts.items():
                logger.info(f"  Class {target}: {count} samples ({count/len(combined_df)*100:.1f}%)")
            
            # Store stats
            self.training_stats['file_stats'] = file_stats
            self.training_stats['combined_stats'] = {
                'total_files': len(all_data),
                'total_samples': len(combined_df),
                'target_distribution': target_counts.to_dict()
            }
            
            return combined_df
            
        except Exception as e:
            logger.error(f"Error loading and combining labeled data: {e}")
            return None
    
    def prepare_features_and_targets(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """Prepare features and targets from combined dataset"""
        try:
            # Identify columns to exclude from features
            exclude_columns = [
                'timestamp', 'target', 'target_result', 'target_profit_pct', 
                'target_stop_pct', 'target_hit_period', 'target_exit_price',
                'source_symbol', 'source_timeframe'
            ]
            
            # Get feature columns
            feature_columns = [col for col in df.columns if col not in exclude_columns]
            
            # Extract features and targets
            X = df[feature_columns].copy()
            y = df['target'].copy()
            
            # Handle missing values
            X = X.fillna(0)
            X = X.replace([np.inf, -np.inf], 0)
            
            # Store feature names
            self.feature_names = feature_columns
            
            logger.info(f"Prepared features: {len(feature_columns)} features, {len(X)} samples")
            logger.info(f"Feature examples: {feature_columns[:5]}")
            
            return (X, y)
            
        except Exception as e:
            logger.error(f"Error preparing features and targets: {e}")
            return (pd.DataFrame(), pd.Series())
    
    def train_model(self, X: pd.DataFrame, y: pd.Series) -> Optional[object]:
        """Train the AI model with optimized parameters"""
        try:
            logger.info("Starting CryptoSight 2.0 model training...")
            
            # 1. Split data
            logger.info("Splitting data...")
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
            
            logger.info(f"Training samples: {len(X_train)}, Test samples: {len(X_test)}")
            
            # 2. Scale features
            logger.info("Scaling features...")
            self.scaler = RobustScaler()
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            # 3. Apply SMOTE for class balance
            logger.info("Applying SMOTE for class balancing...")
            smote = SMOTE(random_state=42)
            smote_result = smote.fit_resample(X_train_scaled, y_train)
            X_train_balanced = smote_result[0]
            y_train_balanced = smote_result[1]
            
            logger.info(f"After SMOTE: {len(X_train_balanced)} training samples")
            
            # 4. Train Random Forest
            logger.info("Training Random Forest model...")
            rf_model = RandomForestClassifier(
                n_estimators=150,          # Good balance of accuracy and speed
                max_depth=20,              # Allow deeper trees for complex patterns
                min_samples_split=5,       # Prevent overfitting
                min_samples_leaf=2,        # Prevent overfitting
                max_features='sqrt',       # Good default
                class_weight='balanced',   # Handle imbalance
                random_state=42,
                n_jobs=-1                  # Use all CPU cores
            )
            
            rf_model.fit(X_train_balanced, y_train_balanced)
            logger.info("Random Forest training completed")
            
            # 5. Calibrate probabilities
            logger.info("Calibrating probabilities...")
            calibrated_model = CalibratedClassifierCV(rf_model, method='sigmoid', cv=3)
            calibrated_model.fit(X_train_scaled, y_train)
            logger.info("Probability calibration completed")
            
            # 6. Evaluate model
            logger.info("Evaluating model...")
            y_pred = calibrated_model.predict(X_test_scaled)
            y_proba = calibrated_model.predict_proba(X_test_scaled)[:, 1]
            
            # Calculate metrics
            from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
            
            accuracy = accuracy_score(y_test, y_pred)
            precision = precision_score(y_test, y_pred, zero_division=0)
            recall = recall_score(y_test, y_pred, zero_division=0)
            f1 = f1_score(y_test, y_pred, zero_division=0)
            auc = roc_auc_score(y_test, y_proba)
            
            logger.info(f"Model Performance:")
            logger.info(f"  Accuracy: {accuracy:.4f}")
            logger.info(f"  Precision: {precision:.4f}")
            logger.info(f"  Recall: {recall:.4f}")
            logger.info(f"  F1 Score: {f1:.4f}")
            logger.info(f"  AUC Score: {auc:.4f}")
            
            # Feature importance
            logger.info("Top 10 most important features:")
            feature_importance = rf_model.feature_importances_
            feature_df = pd.DataFrame({
                'feature': self.feature_names,
                'importance': feature_importance
            }).sort_values('importance', ascending=False)
            
            for i, row in feature_df.head(10).iterrows():
                logger.info(f"  {row['feature']}: {row['importance']:.4f}")
            
            # Store evaluation results
            evaluation_results = {
                'accuracy': accuracy,
                'precision': precision,
                'recall': recall,
                'f1_score': f1,
                'auc_score': auc,
                'test_samples': len(y_test),
                'feature_importance': feature_df.to_dict('records')
            }
            
            # Save model
            self.save_model_artifacts(calibrated_model, evaluation_results)
            
            return calibrated_model
            
        except Exception as e:
            logger.error(f"Error in model training: {e}")
            return None
    
    def save_model_artifacts(self, model, evaluation_results: Dict):
        """Save all model artifacts"""
        try:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            
            # Save main model
            model_filename = f"cryptosight_v2_model_{timestamp}.pkl"
            model_path = os.path.join(MODELS_FOLDER, model_filename)
            joblib.dump(model, model_path)
            
            # Save scaler
            scaler_path = os.path.join(MODELS_FOLDER, "scaler.pkl")
            joblib.dump(self.scaler, scaler_path)
            
            # Save feature names
            feature_names_path = os.path.join(MODELS_FOLDER, "feature_names.pkl")
            joblib.dump(self.feature_names, feature_names_path)
            
            # Save comprehensive metadata
            metadata = {
                'model_filename': model_filename,
                'model_type': 'CalibratedRandomForestClassifier',
                'training_timestamp': timestamp,
                'cryptosight_version': '2.0',
                'num_features': len(self.feature_names or []),
                'feature_names': self.feature_names or [],
                'evaluation_results': evaluation_results,
                'training_stats': self.training_stats,
                'model_path': model_path
            }
            
            metadata_path = os.path.join(MODELS_FOLDER, f"model_metadata_{timestamp}.json")
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2, default=str)
            
            # Create latest model links
            latest_model_path = os.path.join(MODELS_FOLDER, "latest_model.pkl")
            latest_metadata_path = os.path.join(MODELS_FOLDER, "latest_metadata.json")
            
            import shutil
            shutil.copy2(model_path, latest_model_path)
            shutil.copy2(metadata_path, latest_metadata_path)
            
            logger.info(f"Model artifacts saved:")
            logger.info(f"  Model: {model_path}")
            logger.info(f"  Metadata: {metadata_path}")
            logger.info(f"  Scaler: {scaler_path}")
            logger.info(f"  Features: {feature_names_path}")
            
        except Exception as e:
            logger.error(f"Error saving model artifacts: {e}")

def main():
    """Main training function for CryptoSight 2.0"""
    logger.info("CRYPTOSIGHT 2.0 - AUTO TRAINING")
    logger.info(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    logger.info(f"User: samannazir55")
    logger.info("=" * 60)
    
    try:
        # Initialize trainer
        trainer = CryptoSightAutoTrainer()
        
        # Load and combine all labeled data
        logger.info("Loading CryptoSight 2.0 multi-file dataset...")
        combined_data = trainer.load_and_combine_labeled_data(max_samples_per_file=1000)
        
        if combined_data is None or len(combined_data) < 100:
            logger.error("Insufficient labeled data for training!")
            return False
        
        # Prepare features
        logger.info("Preparing features and targets...")
        X, y = trainer.prepare_features_and_targets(combined_data)
        
        if X.empty:
            logger.error("Failed to prepare features!")
            return False
        
        # Train model
        logger.info("Training CryptoSight 2.0 AI model...")
        model = trainer.train_model(X, y)
        
        if model is not None:
            logger.info("CryptoSight 2.0 model training completed successfully!")
            logger.info(f"Model saved to: {MODELS_FOLDER}/")
            logger.info("Ready for trading with CryptoSight 2.0!")
            
            # Show summary
            stats = trainer.training_stats
            if 'combined_stats' in stats:
                cs = stats['combined_stats']
                logger.info(f"Training Summary:")
                logger.info(f"  Files processed: {cs['total_files']}")
                logger.info(f"  Total samples: {cs['total_samples']}")
                logger.info(f"  Features: {len(trainer.feature_names or [])}")
        else:
            logger.error("Model training failed!")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Auto training failed: {e}")
        return False

if __name__ == "__main__":
    logger.info("Starting CryptoSight 2.0 Auto Training...")
    
    success = main()
    if not success:
        exit(1)
    
    logger.info("Auto training completed successfully!")