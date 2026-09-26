"""Cohort construction and sepsis labelling for the eICU demo dataset.

Cohort: ICU stays with at least 24 hours of unit data (spec section 7).

Label: a stay is sepsis-positive when any of its diagnosis strings
contains one of the configured patterns ("sepsis", "septic shock").
This is a pragmatic simplification of the Sepsis-3 definition (SOFA
delta >= 2 plus suspected-infection window), appropriate for the demo
dataset where the classifier is deliberately not the contribution.

The unit of analysis is the ICU stay (``patientunitstayid``), the
standard unit in published eICU work. The GDPR data subject, relevant
for the DSR/erasure flow later, is the patient (``uniquepid``) - both
identifiers are kept on the cohort frame.
"""

import logging

import pandas as pd

from preprocessing.load_eicu import load_config, load_table

logger = logging.getLogger(__name__)

#: Columns carried on the labelled cohort frame.
COHORT_COLUMNS = ["patientunitstayid", "uniquepid", "hospitalid", "sepsis"]


def build_cohort(
    patient: pd.DataFrame, min_unit_stay_minutes: int
) -> pd.DataFrame:
    """Filter the patient table down to stays with enough unit data.

    Args:
        patient: the eICU ``patient`` table.
        min_unit_stay_minutes: minimum ``unitdischargeoffset`` (minutes
            from unit admission to discharge) for a stay to qualify.

    Returns:
        Filtered copy of ``patient``.
    """
    cohort = patient[
        patient["unitdischargeoffset"] >= min_unit_stay_minutes
    ].copy()
    logger.info(
        "Cohort: %d of %d stays have >=%d minutes of unit data",
        len(cohort),
        len(patient),
        min_unit_stay_minutes,
    )
    return cohort


def label_sepsis(
    cohort: pd.DataFrame, diagnosis: pd.DataFrame, patterns: list[str]
) -> pd.DataFrame:
    """Attach a binary ``sepsis`` column to the cohort.

    Args:
        cohort: output of :func:`build_cohort`.
        diagnosis: the eICU ``diagnosis`` table.
        patterns: case-insensitive substrings of ``diagnosisstring``
            that mark a stay sepsis-positive.

    Returns:
        Cohort copy with an added int column ``sepsis`` (1 = positive).
    """
    regex = "|".join(patterns)
    sepsis_stays = diagnosis.loc[
        diagnosis["diagnosisstring"].str.contains(regex, case=False, na=False),
        "patientunitstayid",
    ].unique()
    labelled = cohort.copy()
    labelled["sepsis"] = (
        labelled["patientunitstayid"].isin(sepsis_stays).astype(int)
    )
    logger.info(
        "Labels: %d of %d cohort stays sepsis-positive (%.1f%%)",
        labelled["sepsis"].sum(),
        len(labelled),
        100 * labelled["sepsis"].mean(),
    )
    return labelled


def build_labelled_cohort() -> pd.DataFrame:
    """Full task: load raw tables, filter cohort, attach labels.

    Returns:
        DataFrame with :data:`COHORT_COLUMNS` plus the remaining
        patient-table columns needed by feature extraction downstream.
    """
    cfg = load_config()
    patient = load_table("patient")
    diagnosis = load_table("diagnosis", usecols=["patientunitstayid", "diagnosisstring"])
    cohort = build_cohort(patient, cfg["cohort"]["min_unit_stay_minutes"])
    return label_sepsis(cohort, diagnosis, cfg["labels"]["sepsis_patterns"])
