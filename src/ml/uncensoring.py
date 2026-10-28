"""Demand Uncensoring & Imputation Module for RetailPulse DI Platform.

Identifies demand censoring during stockouts (ending_on_hand_qty == 0 or is_stockout == 1)
and imputes latent customer demand using historical rate-of-sale moving baselines.
Enforces strict chronological lookback (tau < t) to prevent lookahead bias.
"""
from typing import Optional, List, Dict, Tuple
import numpy as np
import pandas as pd
from config.logging_config import logger


class DemandUncensorer:
    """Reconstructs unconstrained latent demand from censored retail sales series."""

    def __init__(self, lookback_days: int = 28, min_samples: int = 2):
        self.lookback_days = lookback_days
        self.min_samples = min_samples

    def uncensor_dataframe(
        self,
        df: pd.DataFrame,
        store_col: str = "store_id",
        product_col: str = "product_id",
        date_col: str = "date_key",
        sales_col: str = "quantity_sold",
        stock_col: str = "ending_on_hand_qty",
        stockout_col: str = "is_stockout",
        promo_col: str = "is_promotional",
        dow_col: str = "day_of_week",
    ) -> pd.DataFrame:
        """
        Processes a full multi-item, multi-store panel dataset and appends uncensored demand.

        Returns DataFrame with additional columns:
        - censored_sales: float
        - is_censored: int (1 if stockout/zero inventory, 0 otherwise)
        - uncensored_demand: float (estimated latent demand D_t)
        """
        logger.info("Starting demand uncensoring on %d records (lookback=%d days)...", len(df), self.lookback_days)
        df_out = df.copy()

        # Sort chronologically
        df_out = df_out.sort_values(by=[store_col, product_col, date_col]).reset_index(drop=True)

        # Flag censored observations: physical stockout flag or zero on-hand stock
        censored_mask = (df_out[stockout_col] == 1) | (df_out[stock_col] <= 0)
        df_out["is_censored"] = censored_mask.astype(int)
        df_out["censored_sales"] = df_out[sales_col].astype(float)
        df_out["uncensored_demand"] = df_out[sales_col].astype(float)

        grouped = df_out.groupby([store_col, product_col])
        processed_chunks: List[pd.DataFrame] = []

        for (store_id, product_id), group in grouped:
            uncensored_series = self._uncensor_single_series(
                sales=group[sales_col].values,
                is_censored=group["is_censored"].values,
                dow=group[dow_col].values,
                promo=group[promo_col].values,
            )
            group_copy = group.copy()
            group_copy["uncensored_demand"] = uncensored_series
            processed_chunks.append(group_copy)

        result_df = pd.concat(processed_chunks, axis=0).sort_index()

        censored_count = result_df["is_censored"].sum()
        censored_pct = (censored_count / len(result_df)) * 100.0
        avg_raw_sales = result_df["censored_sales"].mean()
        avg_uncensored = result_df["uncensored_demand"].mean()
        uplift_pct = ((avg_uncensored - avg_raw_sales) / avg_raw_sales) * 100.0 if avg_raw_sales > 0 else 0.0

        logger.info(
            "Demand uncensoring complete: %d censored rows (%.2f%%). Mean sales: %.2f -> Mean uncensored: %.2f (+%.2f%% uplift)",
            censored_count,
            censored_pct,
            avg_raw_sales,
            avg_uncensored,
            uplift_pct,
        )

        return result_df

    def _uncensor_single_series(
        self,
        sales: np.ndarray,
        is_censored: np.ndarray,
        dow: np.ndarray,
        promo: np.ndarray,
    ) -> np.ndarray:
        """
        Fast chronological uncensoring for a single contiguous SKU-store series.
        Strictly enforces tau < t to ensure zero future data leakage.
        """
        n = len(sales)
        uncensored = sales.astype(float).copy()

        # Running history of valid non-censored sales
        for t in range(n):
            if is_censored[t] == 1:
                # Historical window: tau in [max(0, t - lookback_days), t - 1]
                t_start = max(0, t - self.lookback_days)
                if t == 0 or t_start >= t:
                    # No history at the very first day
                    uncensored[t] = max(sales[t], 1.0)
                    continue

                hist_indices = np.arange(t_start, t)
                hist_valid_mask = is_censored[hist_indices] == 0

                if not np.any(hist_valid_mask):
                    # No non-stockout days in recent window; check all prior history
                    all_prior_valid = is_censored[:t] == 0
                    if np.any(all_prior_valid):
                        imputed = np.median(sales[:t][all_prior_valid])
                    else:
                        imputed = max(sales[t], 1.0)
                    uncensored[t] = max(sales[t], float(imputed))
                    continue

                valid_indices = hist_indices[hist_valid_mask]
                valid_sales = sales[valid_indices]
                valid_dow = dow[valid_indices]
                valid_promo = promo[valid_indices]

                # Priority 1: Match both day-of-week and promotional flag
                match_dow_promo = (valid_dow == dow[t]) & (valid_promo == promo[t])
                if np.sum(match_dow_promo) >= self.min_samples:
                    imputed = np.median(valid_sales[match_dow_promo])
                else:
                    # Priority 2: Match promotional status
                    match_promo = valid_promo == promo[t]
                    if np.sum(match_promo) >= self.min_samples:
                        imputed = np.median(valid_sales[match_promo])
                    else:
                        # Priority 3: All recent non-stockout days
                        imputed = np.median(valid_sales)

                # Latent demand can never be less than realized sales
                uncensored[t] = max(float(sales[t]), round(float(imputed), 2))

        return uncensored


def uncensor_retail_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """Convenience functional wrapper."""
    uncensorer = DemandUncensorer(lookback_days=28, min_samples=2)
    return uncensorer.uncensor_dataframe(df)

