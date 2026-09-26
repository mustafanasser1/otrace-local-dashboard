"""Endpoint coverage for the OTrace service.

One test class per router, covering the happy path and the failure
modes that matter for GDPR behaviour - notably that a data use is
rejected when its consent was never accepted or has been revoked.
"""

import pytest


class TestRoot:
    def test_root_reports_the_local_build(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "OTrace" in response.json()["message"]


class TestIntroduction:
    def test_introduce_and_list(self, client, unique):
        """Introduction takes three plain names, not party objects."""
        response = client.post(
            "/introduction/introduce/",
            json={
                "consumer": f"consumer-{unique}",
                "operator": f"operator-{unique}",
                "service": f"service-{unique}",
            },
        )
        assert response.status_code == 200

        # The lookup is a pair query, not a listing of everything.
        listed = client.get(
            "/introduction/introduced",
            params={
                "consumer": f"consumer-{unique}",
                "operator": f"operator-{unique}",
            },
        )
        assert listed.status_code == 200


class TestConsent:
    def test_offer_starts_in_offered_state(self, client, unique):
        response = client.post(
            "/consents/offer/",
            params={"expiry_timestamp": "2030-01-01T00:00:00"},
            json={
                "operator": {"name": f"op-{unique}"},
                "user": {"name": f"user-{unique}"},
                "data": {"description": "ICU vitals"},
                "operations": [{"operation_type": "read"}],
            },
        )
        assert response.status_code == 200
        assert response.json()["state"] == "offered"

    def test_operations_must_be_objects_not_strings(self, client, unique):
        """A shape that looks reasonable but the service rejects."""
        response = client.post(
            "/consents/offer/",
            params={"expiry_timestamp": "2030-01-01T00:00:00"},
            json={
                "operator": {"name": f"op-{unique}"},
                "user": {"name": f"user-{unique}"},
                "data": {"description": "ICU vitals"},
                "operations": ["read"],
            },
        )
        assert response.status_code == 422

    def test_expiry_timestamp_is_required(self, client, unique):
        response = client.post(
            "/consents/offer/",
            json={
                "operator": {"name": f"op-{unique}"},
                "user": {"name": f"user-{unique}"},
                "data": {"description": "ICU vitals"},
                "operations": [{"operation_type": "read"}],
            },
        )
        assert response.status_code == 422

    def test_accept_moves_state_to_accepted(self, client, accepted_consent):
        response = client.get(f"/consents/{accepted_consent['id']}/")
        assert response.json()["state"] == "accepted"

    def test_accept_requires_a_user_body(self, client, unique):
        offered = client.post(
            "/consents/offer/",
            params={"expiry_timestamp": "2030-01-01T00:00:00"},
            json={
                "operator": {"name": f"op-{unique}"},
                "user": {"name": f"user-{unique}"},
                "data": {"description": "d"},
                "operations": [{"operation_type": "read"}],
            },
        ).json()
        assert client.post(f"/consents/accept/{offered['id']}/").status_code == 422

    def test_deny_and_revoke_change_state(self, client, unique):
        def offer(name):
            return client.post(
                "/consents/offer/",
                params={"expiry_timestamp": "2030-01-01T00:00:00"},
                json={
                    "operator": {"name": f"op-{unique}"},
                    "user": {"name": name},
                    "data": {"description": "d"},
                    "operations": [{"operation_type": "read"}],
                },
            ).json()

        denied = offer(f"denier-{unique}")
        client.post(f"/consents/deny/{denied['id']}/", json={"name": f"denier-{unique}"})
        assert client.get(f"/consents/{denied['id']}/").json()["state"] == "denied"

        revoked = offer(f"revoker-{unique}")
        client.post(
            f"/consents/accept/{revoked['id']}/", json={"name": f"revoker-{unique}"}
        )
        client.post(
            f"/consents/revoke/{revoked['id']}/", json={"name": f"revoker-{unique}"}
        )
        assert client.get(f"/consents/{revoked['id']}/").json()["state"] == "revoked"

    def test_list_returns_a_users_consents(self, client, accepted_consent):
        response = client.get(f"/consents/list/{accepted_consent['user']}/")
        assert response.status_code == 200
        assert any(c["id"] == accepted_consent["id"] for c in response.json())

    def test_unknown_consent_is_not_found(self, client):
        """A well-formed but absent id gives 404."""
        absent = "00000000-0000-4000-8000-000000000000"
        assert client.get(f"/consents/{absent}/").status_code == 404

    def test_malformed_consent_id_is_rejected(self, client):
        """The path is typed as a UUID, so a non-UUID never reaches lookup."""
        assert client.get("/consents/does-not-exist/").status_code == 422


class TestAttestation:
    def test_attest_stores_freeform_information(self, client, unique):
        """action.information is the adapter surface for FL metadata."""
        response = client.post(
            f"/attestations/attest/hospital-{unique}/data_provider/",
            json={
                "type": "data use",
                "information": {
                    "event_type": "LocalTrainingEvent",
                    "training_round": 3,
                    "raw_data_shared": False,
                },
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["id"]
        assert body["action"]["information"]["event_type"] == "LocalTrainingEvent"
        assert body["action"]["information"]["raw_data_shared"] is False

    def test_action_type_is_restricted_to_the_enum(self, client, unique):
        """Arbitrary strings are still rejected; only enum values pass."""
        response = client.post(
            f"/attestations/attest/hospital-{unique}/data_provider/",
            json={"type": "SomeMadeUpEvent", "information": {}},
        )
        assert response.status_code == 422

    def test_fl_action_types_are_first_class(self, client, unique):
        """The four FL lifecycle events attest under their own types."""
        for action_type in (
            "local training",
            "update submission",
            "aggregation",
            "deployment",
        ):
            response = client.post(
                f"/attestations/attest/hospital-{unique}/joint_controller/",
                json={"type": action_type, "information": {"round": 1}},
            )
            assert response.status_code == 200, action_type
            assert response.json()["action"]["type"] == action_type

    def test_gdpr_roles_are_accepted(self, client, unique):
        """joint_controller (Art. 26) and processor (Art. 28) are valid parties."""
        for role in ("joint_controller", "processor"):
            response = client.post(
                f"/attestations/attest/party-{unique}-{role}/{role}/",
                json={"type": "aggregation", "information": {}},
            )
            assert response.status_code == 200, role
            assert response.json()["party"]["data_controller"] == role

    def test_batch_attest_records_every_action(self, client, unique):
        """One request records a whole round's worth of events."""
        party = f"batch-party-{unique}"
        actions = [
            {"type": "local training", "information": {"round": 1, "group": g}}
            for g in range(3)
        ] + [{"type": "aggregation", "information": {"round": 1}}]
        response = client.post(
            f"/attestations/attest_batch/{party}/processor/", json=actions
        )
        assert response.status_code == 200
        assert len(response.json()) == 4
        stored = client.get(f"/attestations/{party}/all/")
        assert len(stored.json()) == 4

    def test_get_all_returns_a_partys_attestations(self, client, unique):
        party = f"party-{unique}"
        for round_number in (1, 2):
            client.post(
                f"/attestations/attest/{party}/data_provider/",
                json={"type": "data use", "information": {"round": round_number}},
            )
        response = client.get(f"/attestations/{party}/all/")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_up_to_date_needs_a_time_window(self, client, unique):
        party = f"party-{unique}"
        client.post(
            f"/attestations/attest/{party}/data_provider/",
            json={"type": "data use", "information": {}},
        )
        assert client.get(f"/attestations/{party}/up_to_date/").status_code == 422

        response = client.get(
            f"/attestations/{party}/up_to_date/",
            params={
                "start_time": "2020-01-01T00:00:00",
                "end_time": "2030-01-01T00:00:00",
            },
        )
        assert response.status_code == 200


class TestDataUseAndCheck:
    def _record_use(self, client, consent):
        return client.post(
            "/data_use/use/",
            json={
                "operator": {"name": consent["operator"]},
                "data": {"description": "ICU vitals"},
                "data_subject": {"name": consent["user"]},
                "operation": {"operation_type": "read"},
                "basis": {"base_type": "consent", "basis_object": consent["id"]},
            },
        ).json()

    def test_check_passes_under_an_accepted_consent(self, client, accepted_consent):
        use = self._record_use(client, accepted_consent)
        response = client.get(f"/check/{use['id']}/{accepted_consent['id']}")
        assert response.status_code == 200
        assert response.json()["valid"] is True

    def test_check_fails_when_consent_was_never_accepted(self, client, unique):
        user = f"user-{unique}"
        consent = client.post(
            "/consents/offer/",
            params={"expiry_timestamp": "2030-01-01T00:00:00"},
            json={
                "operator": {"name": f"op-{unique}"},
                "user": {"name": user},
                "data": {"description": "d"},
                "operations": [{"operation_type": "read"}],
            },
        ).json()
        use = self._record_use(
            client, {"id": consent["id"], "operator": f"op-{unique}", "user": user}
        )
        verdict = client.get(f"/check/{use['id']}/{consent['id']}").json()
        assert verdict["valid"] is False

    def test_check_fails_after_consent_is_revoked(self, client, accepted_consent):
        """Withdrawing consent must invalidate later uses (Article 7(3))."""
        client.post(
            f"/consents/revoke/{accepted_consent['id']}/",
            json={"name": accepted_consent["user"]},
        )
        use = self._record_use(client, accepted_consent)
        verdict = client.get(f"/check/{use['id']}/{accepted_consent['id']}").json()
        assert verdict["valid"] is False

    def test_revoked_consent_is_reported_as_withdrawn(
        self, client, accepted_consent
    ):
        """The refusal reason now names the actual consent state.

        Upstream OTrace tests only ``state != accepted``, so ``offered``,
        ``denied`` and ``revoked`` all produced "Consent was never
        accepted." — the verdict was right, the explanation was not.
        A withdrawn consent means the data subject exercised
        Article 7(3); a consent never accepted means no legal basis ever
        existed. An auditor must be able to tell those apart.

        This test previously pinned the upstream behaviour as a finding;
        per its own instruction it is updated now that the extension
        makes the message specific.
        """
        client.post(
            f"/consents/revoke/{accepted_consent['id']}/",
            json={"name": accepted_consent["user"]},
        )
        use = self._record_use(client, accepted_consent)
        verdict = client.get(f"/check/{use['id']}/{accepted_consent['id']}").json()

        assert verdict["valid"] is False
        assert verdict["message"] == (
            "Consent was withdrawn by the data subject (Article 7(3))."
        )
        assert verdict["consent_state"] == "revoked"

    def test_never_accepted_consent_reports_its_own_reason(self, client, unique):
        """An offered-but-never-accepted consent is not called withdrawn."""
        user = f"user-{unique}"
        consent = client.post(
            "/consents/offer/",
            params={"expiry_timestamp": "2030-01-01T00:00:00"},
            json={
                "operator": {"name": f"op-{unique}"},
                "user": {"name": user},
                "data": {"description": "d"},
                "operations": [{"operation_type": "read"}],
            },
        ).json()
        use = self._record_use(
            client, {"id": consent["id"], "operator": f"op-{unique}", "user": user}
        )
        verdict = client.get(f"/check/{use['id']}/{consent['id']}").json()
        assert verdict["valid"] is False
        assert verdict["message"] == "Consent was offered but never accepted."
        assert verdict["consent_state"] == "offered"

    def test_get_basis_returns_the_legal_basis(self, client, accepted_consent):
        use = self._record_use(client, accepted_consent)
        response = client.get(f"/data_use/get_basis/{use['id']}/")
        assert response.status_code == 200


class TestDataSubjectRequest:
    @pytest.mark.parametrize(
        "request_type",
        ["Access Request", "Correction Request", "Delete Request", "Output Request"],
    )
    def test_every_permitted_request_type_is_accepted(
        self, client, unique, request_type
    ):
        response = client.post(
            "/dsr/request/",
            params={
                "subject": f"subject-{unique}",
                "controller": f"controller-{unique}",
                "request_type": request_type,
            },
        )
        assert response.status_code == 200
        assert response.json()["status"] == "Received"

    def test_request_type_is_a_fixed_enum(self, client, unique):
        """'erasure' reads naturally but the service rejects it."""
        response = client.post(
            "/dsr/request/",
            params={
                "subject": f"subject-{unique}",
                "controller": f"controller-{unique}",
                "request_type": "erasure",
            },
        )
        assert response.status_code == 422

    def test_request_can_be_fetched_and_completed(self, client, unique):
        created = client.post(
            "/dsr/request/",
            params={
                "subject": f"subject-{unique}",
                "controller": f"controller-{unique}",
                "request_type": "Delete Request",
            },
        ).json()
        request_id = created["request_id"]

        assert client.get(f"/dsr/request/{request_id}").status_code == 200

        updated = client.put(
            f"/dsr/request/{request_id}/status", params={"status": "Completed"}
        )
        assert updated.status_code == 200
        assert client.get(f"/dsr/request/{request_id}").json()["status"] == "Completed"


class TestTrace:
    def test_search_accepts_the_full_filter_set(self, client, unique):
        party = f"traced-{unique}"
        client.post(
            f"/attestations/attest/{party}/data_provider/",
            json={"type": "data use", "information": {"event_type": "AggregationEvent"}},
        )
        response = client.get(
            "/trace/search/",
            params={
                "party_name": party,
                "data_controller": "data_provider",
                "action_type": "data use",
                "provider": "",
                "user": "",
                "consent": "",
                "start_time": "2020-01-01T00:00:00",
                "end_time": "2030-01-01T00:00:00",
            },
        )
        assert response.status_code == 200
