from pydantic import BaseModel
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Literal

class Action_Type(str, Enum):
    consent_offered = "consent offered"
    consent_revoked = "consent revoked"
    consent_accepted = "consent accepted"
    consent_denied = "consent denied"
    authorization_granted = "authorization granted"
    authorization_revoked = "authorization revoked"
    data_subject_request_make_request = "data subject request: make"
    data_subject_request_receive_request = "data subject request: receive"
    data_subject_request_update_request = "data subject request: update"
    data_use = "data use"
    # Federated-learning lifecycle events. Upstream OTrace has no action
    # types for training, so FL events previously had to be attested as
    # "data use" with the real event name buried in action.information.
    local_training = "local training"
    update_submission = "update submission"
    aggregation = "aggregation"
    deployment = "deployment"

class Action(BaseModel):
    type: Action_Type
    information: Dict[str, Any]

class Party(BaseModel):
    name: str
    # joint_controller (Art. 26) and processor (Art. 28) let hospitals and
    # an aggregation server carry their actual GDPR roles instead of being
    # squeezed into data_provider/data_recipient.
    data_controller: Literal[
        "consumer",
        "data_provider",
        "data_recipient",
        "joint_controller",
        "processor",
    ]

class Attestation(BaseModel):
    id: str
    party: Party
    action: Action
    timestamp: datetime
