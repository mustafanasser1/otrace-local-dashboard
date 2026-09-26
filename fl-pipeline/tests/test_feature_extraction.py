"""Tests for per-stay feature extraction."""

import numpy as np
import pandas as pd
import pytest

from preprocessing.feature_extraction import (
    _aggregate,
    build_feature_matrix,
    extract_demographics,
    feature_columns,
    impute_and_scale,
)
from preprocessing.load_eicu import data_dir, load_config
from preprocessing.sepsis_labelling import build_labelled_cohort


def test_aggregate_computes_statistics_in_offset_order():
    frame = pd.DataFrame(
        {
            "patientunitstayid": [1, 1, 1, 2],
            "heartrate": [80.0, 120.0, 100.0, 60.0],
        }
    )
    out = _aggregate(frame, "heartrate", ["min", "max", "mean", "last"], "heartrate")
    assert out.loc[1, "heartrate_min"] == 80.0
    assert out.loc[1, "heartrate_max"] == 120.0
    assert out.loc[1, "heartrate_mean"] == 100.0
    assert out.loc[1, "heartrate_last"] == 100.0  # row order = offset order
    assert out.loc[2, "heartrate_last"] == 60.0


def test_extract_demographics_handles_deidentified_age():
    cohort = pd.DataFrame(
        {
            "patientunitstayid": [1, 2, 3],
            "age": ["45", "> 89", None],
            "gender": ["Male", "Female", "Male"],
            "admissionweight": [70.0, 80.0, None],
            "unittype": ["MICU", "SICU", "MICU"],
        }
    )
    demo = extract_demographics(cohort, load_config())
    assert demo.loc[1, "age"] == 45
    assert demo.loc[2, "age"] == 90  # "> 89" mapped to the sentinel
    assert np.isnan(demo.loc[3, "age"])
    assert demo.loc[1, "gender"] == 1 and demo.loc[2, "gender"] == 0
    assert demo.loc[1, "unittype_MICU"] == 1
    assert demo.loc[1, "unittype_SICU"] == 0


def test_impute_and_scale_fits_on_train_only():
    train = np.array([[1.0, 10.0], [3.0, np.nan], [5.0, 30.0]])
    test = np.array([[np.nan, 20.0]])
    train_out, test_out = impute_and_scale(train, test)

    assert not np.isnan(train_out).any()
    assert not np.isnan(test_out).any()
    # Train column 0 (1,3,5) standardises to mean 0.
    assert train_out[:, 0].mean() == pytest.approx(0.0)
    assert train_out[:, 0].std() == pytest.approx(1.0)
    # Test NaN filled with the TRAIN median (3.0) = train mean -> 0 after scaling.
    assert test_out[0, 0] == pytest.approx(0.0)


def test_impute_and_scale_survives_constant_and_all_nan_columns():
    train = np.array([[np.nan, 7.0], [np.nan, 7.0]])
    test = np.array([[np.nan, 7.0]])
    train_out, test_out = impute_and_scale(train, test)
    assert np.isfinite(train_out).all()
    assert np.isfinite(test_out).all()


@pytest.mark.skipif(
    not data_dir().exists(), reason="eICU demo dataset not present"
)
def test_real_feature_matrix_shape_and_coverage():
    """Integration check on the real dataset."""
    matrix = build_feature_matrix(build_labelled_cohort())
    assert len(matrix) == 1627
    # 9 vitals x 4 stats + 8 APACHE + 6 labs x 3 stats + demographics
    assert len(feature_columns(matrix)) >= 70
    assert matrix["sepsis"].isin([0, 1]).all()
    # Core vitals should be present for the large majority of stays.
    assert matrix["heartrate_mean"].notna().mean() > 0.9
    # The two coverage rescues: cuff BP and APACHE temperature.
    assert matrix["noninvasivesystolic_mean"].notna().mean() > 0.9
    assert matrix["apache_temperature"].notna().mean() > 0.8
