"""Forecasting Models & Quantile Uncertainty Estimation for RetailPulse DI Platform.

Implements:
1. Baselines: Seasonal Naive (7-day lag), 14-day Rolling Mean
2. Point Forecasting: LightGBM Regressor
3. Uncertainty Estimation: LightGBM Multi-Quantile Regressors (P10, P50, P90)
With post-processing enforcing non-negativity and monotonic quantile intervals.
"""
from typing import Dict, Any, Tuple, Optional
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from config.logging_config import logger


class SeasonalNaiveForecaster:
    """Predicts next period demand using identical day-of-week demand from prior week (lag_7)."""

    def fit(self, X: pd.DataFrame, y: pd.Series):
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if "lag_7" not in X.columns:
            raise ValueError("Feature matrix must contain 'lag_7' for Seasonal Naive forecast.")
        preds = np.maximum(0.0, X["lag_7"].fillna(0.0).values)
        return preds


class RollingMeanForecaster:
    """Predicts next period demand using trailing 14-day rolling average."""

    def fit(self, X: pd.DataFrame, y: pd.Series):
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if "rolling_mean_14" not in X.columns:
            raise ValueError("Feature matrix must contain 'rolling_mean_14' for Rolling Mean forecast.")
        preds = np.maximum(0.0, X["rolling_mean_14"].fillna(0.0).values)
        return preds


class LightGBMPointForecaster:
    """Gradient boosted decision tree model for point demand forecasting."""

    def __init__(
        self,
        n_estimators: int = 150,
        learning_rate: float = 0.05,
        num_leaves: int = 31,
        min_child_samples: int = 20,
        random_state: int = 42,
    ):
        self.model = LGBMRegressor(
            objective="regression",
            n_estimators=n_estimators,
            learning_rate=learning_rate,
            num_leaves=num_leaves,
            min_child_samples=min_child_samples,
            random_state=random_state,
            n_jobs=-1,
            verbose=-1,
        )

    def fit(self, X: pd.DataFrame, y: pd.Series):
        logger.info("Training LightGBM Point Forecaster on %d samples with %d features...", len(X), X.shape[1])
        self.model.fit(X, y)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        raw_preds = self.model.predict(X)
        # Enforce non-negative demand constraint
        return np.maximum(0.0, np.round(raw_preds, 2))


class LightGBMQuantileForecaster:
    """
    Trains quantile regressors at alpha = 0.10 (P10), alpha = 0.50 (P50), and alpha = 0.90 (P90)
    to estimate lead-time demand prediction intervals.
    Enforces non-negativity and monotonic ordering: P10 <= P50 <= P90.
    """

    def __init__(
        self,
        quantiles: Tuple[float, ...] = (0.10, 0.50, 0.90),
        n_estimators: int = 150,
        learning_rate: float = 0.05,
        num_leaves: int = 31,
        min_child_samples: int = 20,
        random_state: int = 42,
    ):
        self.quantiles = quantiles
        self.models: Dict[float, LGBMRegressor] = {
            q: LGBMRegressor(
                objective="quantile",
                alpha=q,
                n_estimators=n_estimators,
                learning_rate=learning_rate,
                num_leaves=num_leaves,
                min_child_samples=min_child_samples,
                random_state=random_state,
                n_jobs=-1,
                verbose=-1,
            )
            for q in quantiles
        }

    def fit(self, X: pd.DataFrame, y: pd.Series):
        logger.info("Training LightGBM Quantile Forecasters for quantiles %s on %d samples...", self.quantiles, len(X))
        for q, model in self.models.items():
            model.fit(X, y)
        return self

    def predict(self, X: pd.DataFrame) -> Dict[str, np.ndarray]:
        """
        Returns dictionary with keys 'P10', 'P50', 'P90'.
        Post-processes predictions to guarantee P10 <= P50 <= P90 and >= 0.0.
        """
        raw_q_preds = {}
        for q, model in self.models.items():
            key = f"P{int(q * 100)}"
            raw_q_preds[key] = np.maximum(0.0, model.predict(X))

        # Enforce monotonic quantile consistency: P10 <= P50 <= P90
        n_samples = len(X)
        p10 = raw_q_preds.get("P10", np.zeros(n_samples))
        p50 = raw_q_preds.get("P50", np.zeros(n_samples))
        p90 = raw_q_preds.get("P90", np.zeros(n_samples))

        stacked = np.stack([p10, p50, p90], axis=1)
        # Sort along the quantile axis to guarantee monotonicity
        sorted_quantiles = np.sort(stacked, axis=1)

        return {
            "P10": np.round(sorted_quantiles[:, 0], 2),
            "P50": np.round(sorted_quantiles[:, 1], 2),
            "P90": np.round(sorted_quantiles[:, 2], 2),
        }

