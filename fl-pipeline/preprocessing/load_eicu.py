"""Loaders for the eICU Collaborative Research Database demo tables.

Every table lives as a gzipped CSV under the directory named in
``config/data_config.yaml``. This module is the single place that knows
where the raw data sits; everything downstream works on DataFrames.
"""

import logging
from functools import lru_cache
from pathlib import Path

import pandas as pd
import yaml

logger = logging.getLogger(__name__)

FL_PIPELINE_ROOT = Path(__file__).resolve().parents[1]
DATA_CONFIG_PATH = FL_PIPELINE_ROOT / "config" / "data_config.yaml"


@lru_cache(maxsize=1)
def load_config(config_path: str | Path = DATA_CONFIG_PATH) -> dict:
    """Read and cache the data pipeline configuration."""
    with open(config_path) as fh:
        return yaml.safe_load(fh)


def data_dir(config: dict | None = None) -> Path:
    """Absolute path to the raw eICU demo directory."""
    cfg = config or load_config()
    return FL_PIPELINE_ROOT / cfg["data"]["raw_dir"]


def load_table(name: str, usecols: list[str] | None = None) -> pd.DataFrame:
    """Load one eICU table by name (e.g. ``patient``, ``vitalPeriodic``).

    Args:
        name: table name without extension, matching the CSV file name.
        usecols: optional column subset - pass it for the large tables
            (vitalPeriodic is ~1.6M rows) to keep memory sane.

    Returns:
        The table as a DataFrame.
    """

    path = data_dir() / f"{name}.csv.gz"

    if not path.exists():
        path = data_dir() / f"{name}.csv"

    if not path.exists():
        raise FileNotFoundError(
            f"eICU table {name!r} not found."
        )  



    logger.info("Loading eICU table %s (usecols=%s)", name, usecols)
    return pd.read_csv(path, usecols=usecols)
