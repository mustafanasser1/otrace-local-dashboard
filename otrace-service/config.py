"""Configuration for the OTrace service.

Values come from ``config.yaml``, and any of them can be overridden by
an environment variable. The override exists so the test suite can point
the service at a throwaway database instead of the real one.
"""

import os
from pathlib import Path

import yaml

SERVICE_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = SERVICE_ROOT / "config.yaml"


def load_config(path: str | Path = CONFIG_PATH) -> dict:
    """Read the service configuration file."""
    with open(path) as fh:
        return yaml.safe_load(fh)


def database_path() -> str:
    """Absolute path to the SQLite database.

    ``OTRACE_DB_PATH`` wins if set. A relative path from the config file
    resolves against the service directory rather than the current
    working directory, so running uvicorn from elsewhere still uses the
    same database.
    """
    override = os.environ.get("OTRACE_DB_PATH")
    if override:
        return override

    configured = Path(load_config()["database"]["path"])
    if configured.is_absolute():
        return str(configured)
    return str(SERVICE_ROOT / configured)


def host() -> str:
    """Interface the service binds to."""
    return os.environ.get("OTRACE_HOST") or load_config()["service"]["host"]


def port() -> int:
    """Port the service listens on."""
    return int(os.environ.get("OTRACE_PORT") or load_config()["service"]["port"])
