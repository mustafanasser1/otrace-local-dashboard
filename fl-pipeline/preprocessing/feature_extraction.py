"""Feature extraction for the eICU sepsis prediction task.

Turns the raw time-series tables into one fixed-width numeric row per
ICU stay, following spec section 7:

* vital signs   - min / max / mean / last per signal (``vitalPeriodic``)
* blood pressure - the same statistics over non-invasive cuff readings
  (``vitalAperiodic``), which cover the cohort far better than the
  arterial-line columns in ``vitalPeriodic``
* severity      - APACHE worst-value physiology (``apacheApsVar``)
* laboratory    - min / max / last per test (``lab``)
* demographics  - age, gender, admission weight, unit type (``patient``)

Missing values are median-imputed and features standard-scaled. Both
are fitted on the training split only and applied to test data, so no
test-set statistics leak into training.
"""

import logging
import warnings

import numpy as np
import pandas as pd

from preprocessing.load_eicu import load_config, load_table

logger = logging.getLogger(__name__)

#: Identifier columns carried alongside the feature matrix.
ID_COLUMNS = ["patientunitstayid", "uniquepid", "hospitalid"]


def _aggregate(
    frame: pd.DataFrame, value_column: str, statistics: list[str], prefix: str
) -> pd.DataFrame:
    """Aggregate one long-format signal into per-stay summary statistics.

    Args:
        frame: rows for a single signal, with ``patientunitstayid``, an
            offset column already sorted, and ``value_column``.
        value_column: the numeric column to summarise.
        statistics: any of min / max / mean / last.
        prefix: feature name prefix, e.g. ``heartrate`` or ``lab_lactate``.

    Returns:
        One row per stay, indexed by ``patientunitstayid``.
    """
    grouped = frame.groupby("patientunitstayid")[value_column]
    named = {stat: getattr(grouped, stat)() for stat in statistics if stat != "last"}
    if "last" in statistics:
        named["last"] = grouped.last()
    out = pd.DataFrame(named)
    out.columns = [f"{prefix}_{stat}" for stat in out.columns]
    return out


def extract_vitals(stay_ids: pd.Index, config: dict) -> pd.DataFrame:
    """Summary statistics for each configured vital sign."""
    spec = config["features"]
    columns = ["patientunitstayid", "observationoffset", *spec["vitals"]]
    vitals = load_table("vitalPeriodic", usecols=columns)
    vitals = vitals[vitals["patientunitstayid"].isin(stay_ids)]
    vitals = vitals.sort_values(["patientunitstayid", "observationoffset"])

    parts = []
    for signal in spec["vitals"]:
        present = vitals[["patientunitstayid", signal]].dropna(subset=[signal])
        parts.append(
            _aggregate(present, signal, spec["vital_statistics"], signal)
        )
    logger.info("Extracted %d vital signals", len(parts))
    return pd.concat(parts, axis=1)


def extract_aperiodic_vitals(stay_ids: pd.Index, config: dict) -> pd.DataFrame:
    """Summary statistics for non-invasive blood pressure.

    ``vitalAperiodic`` holds cuff measurements, recorded for nearly
    every stay, whereas the ``vitalPeriodic`` systemic columns require
    an arterial line and are mostly absent.
    """
    spec = config["features"]
    columns = ["patientunitstayid", "observationoffset", *spec["aperiodic_vitals"]]
    aperiodic = load_table("vitalAperiodic", usecols=columns)
    aperiodic = aperiodic[aperiodic["patientunitstayid"].isin(stay_ids)]
    aperiodic = aperiodic.sort_values(["patientunitstayid", "observationoffset"])

    parts = []
    for signal in spec["aperiodic_vitals"]:
        present = aperiodic[["patientunitstayid", signal]].dropna(subset=[signal])
        parts.append(
            _aggregate(present, signal, spec["vital_statistics"], signal)
        )
    logger.info("Extracted %d aperiodic vital signals", len(parts))
    return pd.concat(parts, axis=1)


def extract_apache(stay_ids: pd.Index, config: dict) -> pd.DataFrame:
    """APACHE severity variables - one worst value per stay.

    These are single values rather than time series, so they are taken
    as-is with no aggregation. The APACHE missing sentinel becomes NaN
    so that imputation treats it as absent rather than as a real value.
    """
    spec = config["features"]
    apache = load_table(
        "apacheApsVar", usecols=["patientunitstayid", *spec["apache_variables"]]
    )
    apache = apache[apache["patientunitstayid"].isin(stay_ids)]
    apache = apache.set_index("patientunitstayid")
    apache = apache.mask(apache <= spec["apache_missing_sentinel"])
    apache.columns = [f"apache_{c}" for c in apache.columns]
    logger.info("Extracted %d APACHE variables", apache.shape[1])
    return apache[~apache.index.duplicated(keep="first")]


def extract_labs(stay_ids: pd.Index, config: dict) -> pd.DataFrame:
    """Summary statistics for each configured laboratory test."""
    spec = config["features"]
    labs = load_table(
        "lab",
        usecols=["patientunitstayid", "labresultoffset", "labname", "labresult"],
    )
    labs = labs[labs["patientunitstayid"].isin(stay_ids)]
    labs = labs.sort_values(["patientunitstayid", "labresultoffset"])

    parts = []
    for short_name, lab_name in spec["labs"].items():
        rows = labs[labs["labname"] == lab_name].dropna(subset=["labresult"])
        parts.append(
            _aggregate(rows, "labresult", spec["lab_statistics"], f"lab_{short_name}")
        )
    logger.info("Extracted %d laboratory tests", len(parts))
    return pd.concat(parts, axis=1)


def extract_demographics(cohort: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Numeric demographic features from the patient table.

    Age arrives as a string because eICU de-identifies ages above 89 as
    ``"> 89"``; that becomes a configured numeric sentinel. Gender is
    binarised and unit type one-hot encoded.
    """
    spec = config["features"]
    demo = cohort.set_index("patientunitstayid")[spec["demographics"]].copy()

    age = demo["age"].replace("> 89", str(spec["age_over_89_value"]))
    demo["age"] = pd.to_numeric(age, errors="coerce")
    demo["gender"] = (demo["gender"] == "Male").astype(int)
    demo["admissionweight"] = pd.to_numeric(demo["admissionweight"], errors="coerce")
    unit_type = pd.get_dummies(demo.pop("unittype"), prefix="unittype", dtype=int)
    return pd.concat([demo, unit_type], axis=1)


def build_feature_matrix(labelled_cohort: pd.DataFrame) -> pd.DataFrame:
    """Assemble the full per-stay feature table.

    Args:
        labelled_cohort: output of
            :func:`preprocessing.sepsis_labelling.build_labelled_cohort`.

    Returns:
        DataFrame with :data:`ID_COLUMNS`, one column per feature, and
        the ``sepsis`` label. Missing values are left as NaN - imputation
        happens after the train/test split.
    """
    config = load_config()
    stay_ids = pd.Index(labelled_cohort["patientunitstayid"].unique())

    features = pd.concat(
        [
            extract_vitals(stay_ids, config),
            extract_aperiodic_vitals(stay_ids, config),
            extract_apache(stay_ids, config),
            extract_labs(stay_ids, config),
            extract_demographics(labelled_cohort, config),
        ],
        axis=1,
    ).reindex(stay_ids)

    identifiers = labelled_cohort.set_index("patientunitstayid")[
        ["uniquepid", "hospitalid", "sepsis"]
    ]
    matrix = features.join(identifiers).reset_index()
    logger.info(
        "Feature matrix: %d stays x %d features",
        len(matrix),
        len(feature_columns(matrix)),
    )
    return matrix


def feature_columns(matrix: pd.DataFrame) -> list[str]:
    """Names of the model input columns (everything but ids and label)."""
    return [c for c in matrix.columns if c not in {*ID_COLUMNS, "sepsis"}]


def impute_and_scale(
    train: np.ndarray, test: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Median-impute then standard-scale, fitting on training data only.

    Args:
        train: training feature matrix, may contain NaN.
        test: test feature matrix, may contain NaN.

    Returns:
        The transformed ``(train, test)`` pair.
    """
    with warnings.catch_warnings():
        # A feature absent for every training stay yields an all-NaN
        # slice; the median is then meaningless and we fall back to 0.
        warnings.simplefilter("ignore", RuntimeWarning)
        medians = np.nanmedian(train, axis=0)
    medians = np.where(np.isnan(medians), 0.0, medians)

    train_filled = np.where(np.isnan(train), medians, train)
    test_filled = np.where(np.isnan(test), medians, test)

    mean = train_filled.mean(axis=0)
    std = train_filled.std(axis=0)
    std[std == 0] = 1.0  # constant columns carry no signal

    return (train_filled - mean) / std, (test_filled - mean) / std
