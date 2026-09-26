"""Tests for cohort construction and sepsis labelling."""

import pandas as pd
import pytest

from preprocessing.load_eicu import data_dir
from preprocessing.sepsis_labelling import (
    build_cohort,
    build_labelled_cohort,
    label_sepsis,
)


@pytest.fixture
def patient() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "patientunitstayid": [1, 2, 3, 4],
            "uniquepid": ["a", "b", "b", "c"],
            "hospitalid": [10, 10, 20, 30],
            "unitdischargeoffset": [2000, 1440, 1439, 100],
        }
    )


@pytest.fixture
def diagnosis() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "patientunitstayid": [1, 2, 3, 4, 4],
            "diagnosisstring": [
                "infectious diseases|systemic/other infections|Sepsis",
                "cardiovascular|shock / hypotension|septic shock",
                "pulmonary|respiratory failure",
                "infectious diseases|skin, bone and joint infections|septic arthritis",
                "renal|electrolyte imbalance",
            ],
        }
    )


PATTERNS = ["sepsis", "septic shock"]


def test_build_cohort_filters_short_stays(patient):
    cohort = build_cohort(patient, min_unit_stay_minutes=1440)
    assert cohort["patientunitstayid"].tolist() == [1, 2]


def test_label_sepsis_matches_patterns_case_insensitively(patient, diagnosis):
    labelled = label_sepsis(patient, diagnosis, PATTERNS)
    by_stay = labelled.set_index("patientunitstayid")["sepsis"]
    assert by_stay[1] == 1  # "Sepsis" (capitalised)
    assert by_stay[2] == 1  # "septic shock"
    assert by_stay[3] == 0  # no infection diagnosis


def test_septic_arthritis_is_not_sepsis(patient, diagnosis):
    labelled = label_sepsis(patient, diagnosis, PATTERNS)
    assert labelled.set_index("patientunitstayid")["sepsis"][4] == 0


def test_label_sepsis_does_not_mutate_input(patient, diagnosis):
    before = patient.copy()
    label_sepsis(patient, diagnosis, PATTERNS)
    pd.testing.assert_frame_equal(patient, before)


@pytest.mark.skipif(
    not data_dir().exists(), reason="eICU demo dataset not present"
)
def test_real_cohort_matches_known_statistics():
    """Integration check against figures verified on 2026-07-31."""
    labelled = build_labelled_cohort()
    assert len(labelled) == 1627  # stays with >=24h unit data
    prevalence = labelled["sepsis"].mean()
    # ~15.5% with the sepsis + septic-shock label set (bare "sepsis"
    # alone gives 13.9%; the wider set adds septic-shock-only stays).
    assert 0.13 <= prevalence <= 0.17
    assert labelled["hospitalid"].nunique() > 100  # many small hospitals
