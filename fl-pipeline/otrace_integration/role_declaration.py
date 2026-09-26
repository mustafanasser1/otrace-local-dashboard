"""GDPR role assignment for the federated sepsis scenario.

Three roles participate:

* **Hospitals** decide jointly why and how patient data is processed,
  making them joint controllers under Article 26.
* **The aggregation server** only averages updates on their
  instructions, making it a processor under Article 28.
* **The model deployer** controls the served model under Article 24.

Upstream OTrace's ``Party.data_controller`` field admits only
``consumer``, ``data_provider`` and ``data_recipient`` - none of which
expresses joint controllership or processorship (documented gap 2 of
five). The extended service adds ``joint_controller`` and ``processor``
as native values, and ``config/otrace_config.yaml`` maps each role onto
the vocabulary of whichever service is in use. The true GDPR role is
still carried in every attestation payload so traces stay
self-describing. The deployer remains ``consumer``: upstream has no
plain ``controller`` value, and the extension adds only the two roles
the FL scenario cannot express at all.
"""

import logging
from dataclasses import dataclass

from otrace_integration.otrace_client import load_otrace_config

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PartyRole:
    """A participant's identity and its two role descriptions.

    Attributes:
        party_name: the party's name in OTrace.
        otrace_data_controller: the closest value OTrace permits.
        gdpr_role: the role the party actually holds.
        gdpr_article: the article establishing that role.
    """

    party_name: str
    otrace_data_controller: str
    gdpr_role: str
    gdpr_article: str

    def as_metadata(self) -> dict[str, str]:
        """Role fields to embed in an attestation payload."""
        return {
            "data_controller_role": self.gdpr_role,
            "gdpr_article": self.gdpr_article,
            "otrace_data_controller": self.otrace_data_controller,
        }


def hospital_party_name(group_id: int) -> str:
    """OTrace party name for a hospital group."""
    return f"hospital-group-{group_id}"


#: Party name used by the aggregation server.
AGGREGATION_SERVER_PARTY = "aggregation-server"

#: Party name used by the model deployer.
MODEL_DEPLOYER_PARTY = "model-deployer"


def _role(config: dict, key: str, party_name: str) -> PartyRole:
    settings = config["roles"][key]
    return PartyRole(
        party_name=party_name,
        otrace_data_controller=settings["otrace_data_controller"],
        gdpr_role=settings["gdpr_role"],
        gdpr_article=settings["gdpr_article"],
    )


def hospital_role(group_id: int, config: dict | None = None) -> PartyRole:
    """Joint-controller role for one hospital group."""
    cfg = config or load_otrace_config()
    return _role(cfg, "hospital", hospital_party_name(group_id))


def aggregation_server_role(config: dict | None = None) -> PartyRole:
    """Processor role for the aggregation server."""
    cfg = config or load_otrace_config()
    return _role(cfg, "aggregation_server", AGGREGATION_SERVER_PARTY)


def model_deployer_role(config: dict | None = None) -> PartyRole:
    """Controller role for the party deploying the trained model."""
    cfg = config or load_otrace_config()
    return _role(cfg, "model_deployer", MODEL_DEPLOYER_PARTY)


def declare_all_roles(
    num_groups: int, config: dict | None = None
) -> list[PartyRole]:
    """Every participating party, hospitals first.

    Args:
        num_groups: number of hospital groups in the federation.
        config: parsed OTrace configuration.

    Returns:
        Hospital roles followed by the server and deployer roles.
    """
    cfg = config or load_otrace_config()
    roles = [hospital_role(g, cfg) for g in range(num_groups)]
    roles += [aggregation_server_role(cfg), model_deployer_role(cfg)]
    logger.info(
        "Declared %d parties: %d joint controllers, 1 processor, 1 controller",
        len(roles),
        num_groups,
    )
    return roles
