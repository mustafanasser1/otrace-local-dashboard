"""Shared plumbing for the streamed experiment pipeline.

The stream carries *facts* - which group trained, in which round, with
what result - not finished attestations. Enrichment into GDPR
attestations (consent references, legal basis, roles) happens on the
consumer side, which is the plan's trace-enrichment shape: raw event
flows in, accountability records out.
"""

import json
import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "streaming_config.yaml"


def load_streaming_config() -> dict:
    """Parsed streaming configuration."""
    with open(CONFIG_PATH) as handle:
        return yaml.safe_load(handle)["streaming"]


def serialize(event: dict) -> bytes:
    return json.dumps(event, sort_keys=True).encode("utf-8")


def deserialize(raw: bytes) -> dict:
    return json.loads(raw.decode("utf-8"))
