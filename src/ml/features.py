"""Leak-Free Time-Series Feature Engineering for RetailPulse DI Platform.

Constructs strictly chronological lag features and trailing rolling statistics
to prevent contemporaneous and lookahead data leakage in demand forecasting.
"""
from typing import List, Tuple, Optional
import numpy as np
import pandas as pd
from config.logging_config import logger


class FeaturePipeline:
    """Transforms raw and uncensored time-series records into leak-free feature matrices."""

    FEATURE_COLS: List[str] = [
        "lag_1",
        "lag_7",
        "lag_14",
        "lag_28",
        "rolling_mean_7",
        "rolling_std_7",
        "rolling_mean_14",
        "rolling_std_14",
        "rolling_mean_28",
        "rolling_std_28",
        "day_of_week",
        "month_num",
        "day_of_month",
        "is_weekend",
        "is_promotional",
        "store_id_code",
        "product_id_code",
        "category_code",
    ]

    def __init__(self, target_col: str = "uncensored_demand", drop_na_lags: bool = True):
        self.target_col = target_col
        self.drop_na_lags = drop_na_lags

    def build_features(
        self,
        df: pd.DataFrame,
        store_col: str = "store_id",
        product_col: str = "product_id",
        date_col: str = "date_key",
    ) -> pd.DataFrame:
        """
        Generates leak-free features for every (store, product) time series.
        """
        logger.info("Building leak-free features using target '%s' (%d input records)...", self.target_col, len(df))
        df_sorted = df.sort_values(by=[store_col, product_col, date_col]).copy()

        # Target variable
        target_series = df_sorted[self.target_col]

        # 1. Strictly Lagged Features (shift k >= 1)
        # Shift(1) guarantees target y_t is never in the feature set at step t
        grouped_target = df_sorted.groupby([store_col, product_col])[self.target_col]

        df_sorted["lag_1"] = grouped_target.shift(1)
        df_sorted["lag_7"] = grouped_target.shift(7)
        df_sorted["lag_14"] = grouped_target.shift(14)
        df_sorted["lag_28"] = grouped_target.shift(28)

        # 2. Trailing Rolling Statistics (strictly lagged by 1 day)
        # We compute rolling windows on shift(1) to avoid including today's target y_t
        lagged_1 = grouped_target.shift(1)
        df_sorted["rolling_mean_7"] = (
            df_sorted.groupby([store_col, product_col])[self.target_col]
            .transform(lambda s: s.shift(1).rolling(7, min_periods=3).mean())
        )
        df_sorted["rolling_std_7"] = (
            df_sorted.groupby([store_col, product_col])[self.target_col]
            .transform(lambda s: s.shift(1).rolling(7, min_periods=3).std().fillna(0.0))
        )
        df_sorted["rolling_mean_14"] = (
            df_sorted.groupby([store_col, product_col])[self.target_col]
            .transform(lambda s: s.shift(1).rolling(14, min_periods=7).mean())
        )
        df_sorted["rolling_std_14"] = (
            df_sorted.groupby([store_col, product_col])[self.target_col]
            .transform(lambda s: s.shift(1).rolling(14, min_periods=7).std().fillna(0.0))
        )
        df_sorted["rolling_mean_28"] = (
            df_sorted.groupby([store_col, product_col])[self.target_col]
            .transform(lambda s: s.shift(1).rolling(28, min_periods=14).mean())
        )
        df_sorted["rolling_std_28"] = (
            df_sorted.groupby([store_col, product_col])[self.target_col]
            .transform(lambda s: s.shift(1).rolling(28, min_periods=14).std().fillna(0.0))
        )

        # 3. Categorical Encodings (numeric codes for tree models)
        df_sorted["store_id_code"] = df_sorted[store_col].astype("category").cat.codes
        df_sorted["product_id_code"] = df_sorted[product_col].astype("category").cat.codes
        if "category" in df_sorted.columns:
            df_sorted["category_code"] = df_sorted["category"].astype("category").cat.codes
        else:
            df_sorted["category_code"] = 0

        # Fill calendar columns if missing
        if "day_of_week" not in df_sorted.columns and "date_key" in df_sorted.columns:
            dt_series = pd.to_datetime(df_sorted["date_key"].astype(str), format="%Y%m%d")
            df_sorted["day_of_week"] = dt_series.dt.dayofweek + 1
            df_sorted["month_num"] = dt_series.dt.month
            df_sorted["day_of_month"] = dt_series.dt.day
            df_sorted["is_weekend"] = df_sorted["day_of_week"].isin([6, 7]).astype(int)

        # 4. Warm-up Period Filtering (drop rows where lag_28 is NaN)
        initial_len = len(df_sorted)
        if self.drop_na_lags:
            df_sorted = df_sorted.dropna(subset=["lag_28", "rolling_mean_28"]).reset_index(drop=True)
            logger.info("Filtered %d warm-up rows (first 28 days); %d modeling rows remaining.", initial_len - len(df_sorted), len(df_sorted))

        return df_sorted

    def get_feature_and_target_matrices(
        self,
        df: pd.DataFrame,
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """Splits feature matrix X and target vector y."""
        X = df[self.FEATURE_COLS].copy()
        y = df[self.target_col].copy()
        return X, y


def generate_forecasting_dataset(
    df: pd.DataFrame,
    target_col: str = "uncensored_demand",
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """Generates processed DataFrame, feature matrix X, and target vector y."""
    pipeline = FeaturePipeline(target_col=target_col, drop_na_lags=True)
    df_feat = pipeline.build_features(df)
    X, y = pipeline.get_feature_and_target_matrices(df_feat)
    return df_feat, X, y
