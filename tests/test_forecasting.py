"""Automated Test Suite for RetailPulse DI Time-Series Forecasting & Uncensoring.

Verifies:
1. Leak-Free Feature Matrix Generation (Zero Lookahead Bias).
2. Demand Uncensoring Logic & Historical Imputation Integrity.
3. Monotonic Quantile Predictions (P10 <= P50 <= P90).
4. Non-Negative Prediction Bounds.
5. Accuracy Superiority: LightGBM WAPE < Baseline WAPE.
6. Bias Mitigation: Uncensored model mitigates raw under-forecasting bias.
"""
import numpy as np
import pandas as pd
import pytest

from src.ml.uncensoring import DemandUncensorer, uncensor_retail_dataset
from src.ml.features import FeaturePipeline
from src.ml.models import (
    SeasonalNaiveForecaster,
    RollingMeanForecaster,
    LightGBMPointForecaster,
    LightGBMQuantileForecaster,
)
from src.ml.evaluate import (
    ForecastingEvaluationSuite,
    calculate_wape,
    calculate_mae,
    calculate_bias_pct,
    calculate_pinball_loss,
)


@pytest.fixture(scope="module")
def sample_timeseries():
    """Generates a small deterministic 100-day single-item time series for feature verification."""
    dates = pd.date_range("2024-01-01", periods=100)
    date_keys = [int(d.strftime("%Y%m%d")) for d in dates]
    np.random.seed(42)
    demand = np.random.poisson(lam=10, size=100).astype(float)
    # Inject stockout at day 40 and 41
    stock = np.full(100, 25)
    stock[40:42] = 0
    sales = demand.copy()
    sales[40:42] = 0.0

    df = pd.DataFrame(
        {
            "date_key": date_keys,
            "store_id": "STR01",
            "product_id": "PRD01",
            "quantity_sold": sales,
            "ending_on_hand_qty": stock,
            "is_stockout": (stock == 0).astype(int),
            "is_promotional": np.zeros(100, dtype=int),
            "day_of_week": [d.isoweekday() for d in dates],
            "month_num": [d.month for d in dates],
            "day_of_month": [d.day for d in dates],
            "is_weekend": [1 if d.isoweekday() in (6, 7) else 0 for d in dates],
            "category": "Groceries",
        }
    )
    return df


def test_feature_matrix_no_lookahead_leakage(sample_timeseries):
    """
    Test 1: Verify that features at step t strictly depend on historical steps tau < t.
    Mutating target values in the future MUST NOT change feature values at prior or current step t.
    """
    pipeline = FeaturePipeline(target_col="quantity_sold", drop_na_lags=False)

    df1 = sample_timeseries.copy()
    feat1 = pipeline.build_features(df1)

    # Mutate future observations at step 70..100
    df2 = sample_timeseries.copy()
    df2.loc[70:, "quantity_sold"] = df2.loc[70:, "quantity_sold"] + 500.0
    feat2 = pipeline.build_features(df2)

    # For steps 0..69, all lag and rolling features must be 100% IDENTICAL
    check_cols = [
        "lag_1",
        "lag_7",
        "lag_14",
        "lag_28",
        "rolling_mean_7",
        "rolling_std_7",
        "rolling_mean_14",
        "rolling_std_14",
        "rolling_mean_28",
    ]

    for col in check_cols:
        val1 = feat1.loc[30:69, col].values
        val2 = feat2.loc[30:69, col].values
        np.testing.assert_allclose(
            val1,
            val2,
            rtol=1e-5,
            err_msg=f"Lookahead leakage detected in feature '{col}' when future data was modified!",
        )

    # Specifically verify lag_1 matches shifted target
    np.testing.assert_allclose(
        feat1.loc[1:50, "lag_1"].values,
        sample_timeseries.loc[0:49, "quantity_sold"].values,
    )


def test_demand_uncensoring_logic(sample_timeseries):
    """
    Test 2: Verify that stockouts (ending_on_hand_qty == 0) are identified
    and imputed with positive latent demand strictly greater than 0.
    """
    uncensorer = DemandUncensorer(lookback_days=28, min_samples=2)
    uncensored_df = uncensorer.uncensor_dataframe(sample_timeseries)

    # Check non-stockout days remain untouched
    non_stockout = uncensored_df["is_stockout"] == 0
    np.testing.assert_array_equal(
        uncensored_df.loc[non_stockout, "uncensored_demand"].values,
        uncensored_df.loc[non_stockout, "quantity_sold"].values,
    )

    # Check stockout days (days 40 and 41) have imputed latent demand > 0
    stockout = uncensored_df["is_stockout"] == 1
    assert np.all(uncensored_df.loc[stockout, "uncensored_demand"].values > 0.0)
    assert np.all(uncensored_df.loc[stockout, "is_censored"].values == 1)


def test_quantile_forecaster_monotonicity_and_bounds():
    """
    Test 3: Verify that quantile predictions strictly satisfy:
    0.0 <= P10 <= P50 <= P90 across 100% of samples.
    """
    np.random.seed(42)
    X = pd.DataFrame(np.random.randn(200, 5), columns=[f"f_{i}" for i in range(5)])
    y = np.maximum(0.0, np.random.poisson(10, 200).astype(float))

    q_model = LightGBMQuantileForecaster(quantiles=(0.10, 0.50, 0.90), n_estimators=30, random_state=42)
    q_model.fit(X, y)

    preds = q_model.predict(X)

    p10 = preds["P10"]
    p50 = preds["P50"]
    p90 = preds["P90"]

    # Non-negativity
    assert np.all(p10 >= 0.0), "P10 has negative values"
    assert np.all(p50 >= 0.0), "P50 has negative values"
    assert np.all(p90 >= 0.0), "P90 has negative values"

    # Monotonicity
    assert np.all(p10 <= p50), "Quantile crossing: P10 > P50 detected!"
    assert np.all(p50 <= p90), "Quantile crossing: P50 > P90 detected!"


def test_point_forecaster_non_negativity():
    """
    Test 4: Verify that LightGBMPointForecaster enforces non-negative predictions.
    """
    np.random.seed(42)
    X = pd.DataFrame(np.random.randn(100, 4), columns=[f"feat_{i}" for i in range(4)])
    y = np.maximum(0.0, np.random.normal(5, 3, 100))

    model = LightGBMPointForecaster(n_estimators=30, random_state=42)
    model.fit(X, y)
    preds = model.predict(X)

    assert np.all(preds >= 0.0), f"Negative predictions found: {preds[preds < 0]}"


def test_comparative_experiment_benchmarks():
    """
    Test 5 & 6: Run full evaluation suite on RetailPulseDB and verify:
    - LightGBM (Uncensored Demand) achieves lower WAPE than Seasonal Naive baseline.
    - Uncensored training eliminates the negative under-forecasting bias (< 5% vs -17% raw).
    - Pinball loss is strictly positive and finite.
    """
    suite = ForecastingEvaluationSuite()
    results = suite.run_comparative_experiment()

    metrics = results["metrics"]
    wape_naive = metrics["Seasonal Naive"]["WAPE"]
    wape_unc = metrics["LightGBM (Uncensored Demand)"]["WAPE"]
    wape_raw = metrics["LightGBM (Raw Censored Sales)"]["WAPE"]

    bias_raw = metrics["LightGBM (Raw Censored Sales)"]["Bias %"]
    bias_unc = metrics["LightGBM (Uncensored Demand)"]["Bias %"]

    # Assert ML outperforms naive baseline
    assert wape_unc < wape_naive, f"LightGBM WAPE ({wape_unc}%) should be lower than Naive ({wape_naive}%)"
    assert wape_unc < wape_raw, f"Uncensored LightGBM ({wape_unc}%) should be more accurate than Raw ({wape_raw}%)"

    # Assert uncensored model fixes under-forecasting bias
    assert bias_raw < -10.0, f"Raw model should suffer from under-forecasting bias (< -10%), got {bias_raw}%"
    assert abs(bias_unc) < 5.0, f"Uncensored model should eliminate bias to within +/-5%, got {bias_unc}%"

    # Assert zero quantile inversions
    assert results["monotonic_violations"] == 0, "Quantile inversions detected in benchmark"

    # Assert pinball losses are positive
    for q_name, loss in results["pinball_losses"].items():
        assert loss > 0.0, f"Pinball loss for {q_name} must be positive, got {loss}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

