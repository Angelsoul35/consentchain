from __future__ import annotations

from fastapi.testclient import TestClient

from consentchain.scopes import DataCategory, Purpose


def test_service_grant_then_allow(service):
    service.grant_consent(
        "patient:alice",
        "clinic:onc",
        Purpose.TREATMENT,
        [DataCategory.LAB_RESULTS, DataCategory.MEDICATIONS],
    )
    text = (
        "The treating physician needs the recent lab results and the current "
        "medication list to adjust therapy."
    )
    result = service.evaluate_request("patient:alice", "clinic:onc", text)
    assert result["decision"] == "allow"
    assert result["classified_purpose"] == "Treatment"


def test_service_denies_without_consent(service):
    text = "For an approved research study we request the patient's genetic test results."
    result = service.evaluate_request("patient:bob", "lab:research", text)
    assert result["decision"] == "deny"


def test_service_revoke_flips_decision(service):
    service.grant_consent(
        "patient:carol", "clinic:gp", Purpose.TREATMENT, [DataCategory.DIAGNOSES]
    )
    text = "The care team requires the diagnosis history for ongoing clinical care."
    assert service.evaluate_request("patient:carol", "clinic:gp", text)["decision"] == "allow"
    service.revoke_consent("patient:carol", "clinic:gp", Purpose.TREATMENT)
    assert service.evaluate_request("patient:carol", "clinic:gp", text)["decision"] == "deny"


def _client(service):
    import consentchain.main as main

    main._service = service
    return TestClient(main.app)


def test_api_health_and_flow(service):
    client = _client(service)
    assert client.get("/health").json() == {"status": "ok"}

    grant = client.post(
        "/consent/grant",
        json={
            "patient": "patient:dina",
            "requester": "clinic:card",
            "purpose": "treatment",
            "categories": ["diagnoses", "lab_results"],
        },
    )
    assert grant.status_code == 200
    assert grant.json()["version"] == 1

    evaluate = client.post(
        "/access/evaluate",
        json={
            "patient": "patient:dina",
            "requester": "clinic:card",
            "text": "The treating physician needs the diagnosis history and recent lab results.",
        },
    )
    assert evaluate.status_code == 200
    assert evaluate.json()["decision"] == "allow"


def test_api_rejects_unknown_purpose_and_category(service):
    client = _client(service)
    bad_purpose = client.post(
        "/consent/grant",
        json={
            "patient": "p",
            "requester": "r",
            "purpose": "marketing",
            "categories": ["diagnoses"],
        },
    )
    assert bad_purpose.status_code == 422

    bad_category = client.post(
        "/consent/grant",
        json={
            "patient": "p",
            "requester": "r",
            "purpose": "treatment",
            "categories": ["horoscope"],
        },
    )
    assert bad_category.status_code == 422
