"""End-to-end flow: enrol, verify, trials, metrics, sweep, export, withdrawal."""

from __future__ import annotations

from tests.integration.helpers import SHA256_HEX, blank_frame_b64, frame_b64


def _create_participant(client, code: str) -> int:
    resp = client.post("/api/participants", json={"subject_code": code})
    assert resp.status_code == 200, resp.text
    pid = resp.json()["id"]
    consent = client.post(
        f"/api/participants/{pid}/consent",
        json={
            "consent_version": "v1.0",
            "consent_text_sha256": SHA256_HEX,
            "purposes": ["research_face_verification_eval"],
            "accepted": True,
        },
    )
    assert consent.status_code == 200, consent.text
    return pid


def _enrol(client, pid: int, identity: int) -> dict:
    frames = [{"image_b64": frame_b64(identity, noise=n)} for n in range(5)]
    resp = client.post(f"/api/participants/{pid}/enrolment", json={"frames": frames})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_enrolment_accepts_quality_frames(auth_client):
    pid = _create_participant(auth_client, "P001")
    result = _enrol(auth_client, pid, identity=1)
    assert result["accepted"] == 5
    assert result["rejected"] == []


def test_enrolment_rejects_bad_yaw_and_requires_minimum(auth_client):
    pid = _create_participant(auth_client, "P010")
    frames = [
        {"image_b64": frame_b64(1, noise=0)},
        {"image_b64": frame_b64(1, noise=1)},
        {"image_b64": frame_b64(1, noise=2, yaw_deg=60.0)},  # rejected: excessive yaw
    ]
    resp = auth_client.post(f"/api/participants/{pid}/enrolment", json={"frames": frames})
    # Only 2 usable frames, below the minimum of 3 -> 422
    assert resp.status_code == 422, resp.text
    assert resp.json()["code"] == "ENROLMENT_ERROR"


def test_enrolment_without_consent_blocked(auth_client):
    resp = auth_client.post("/api/participants", json={"subject_code": "P099"})
    pid = resp.json()["id"]
    frames = [{"image_b64": frame_b64(1, noise=n)} for n in range(5)]
    enrol = auth_client.post(f"/api/participants/{pid}/enrolment", json={"frames": frames})
    assert enrol.status_code == 409
    assert enrol.json()["code"] == "CONSENT_INACTIVE"


def test_verify_genuine_and_impostor(auth_client):
    pid = _create_participant(auth_client, "P002")
    _enrol(auth_client, pid, identity=2)

    genuine = auth_client.post(
        "/api/verify",
        json={"claimed_participant_id": pid, "image_b64": frame_b64(2, noise=77)},
    )
    assert genuine.status_code == 200, genuine.text
    assert genuine.json()["decision"] == "accept"
    assert genuine.json()["score"] > 0.3
    assert "embedding" not in genuine.json()
    assert "vector" not in genuine.json()

    impostor = auth_client.post(
        "/api/verify",
        json={"claimed_participant_id": pid, "image_b64": frame_b64(999, noise=1)},
    )
    assert impostor.status_code == 200, impostor.text
    assert impostor.json()["decision"] == "reject"


def test_verify_fta_on_blank(auth_client):
    pid = _create_participant(auth_client, "P003")
    _enrol(auth_client, pid, identity=3)
    resp = auth_client.post(
        "/api/verify", json={"claimed_participant_id": pid, "image_b64": blank_frame_b64()}
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "NO_FACE"


def test_trials_metrics_sweep_and_export(auth_client):
    p1 = _create_participant(auth_client, "A1")
    _enrol(auth_client, p1, identity=1)
    p2 = _create_participant(auth_client, "A2")
    _enrol(auth_client, p2, identity=2)

    run_id = auth_client.post("/api/runs", json={"name": "pilot-1"}).json()["id"]

    # genuine trials for A1 and A2
    for noise in range(40, 45):
        r = auth_client.post(
            f"/api/runs/{run_id}/trials",
            json={
                "probe_label": "A1",
                "claimed_label": "A1",
                "image_b64": frame_b64(1, noise=noise),
                "condition_tags": ["lighting:normal"],
            },
        )
        assert r.status_code == 200, r.text
        assert r.json()["ground_truth"] == "genuine"
    # impostor trials: A2's face claiming to be A1
    for noise in range(50, 55):
        r = auth_client.post(
            f"/api/runs/{run_id}/trials",
            json={
                "probe_label": "A2",
                "claimed_label": "A1",
                "image_b64": frame_b64(2, noise=noise),
                "condition_tags": ["lighting:normal"],
            },
        )
        assert r.json()["ground_truth"] == "impostor"

    metrics = auth_client.get(f"/api/runs/{run_id}/metrics").json()
    assert metrics["n_genuine"] == 5
    assert metrics["n_impostor"] == 5
    assert metrics["far"] is not None and metrics["frr"] is not None
    assert metrics["far_ci95"] is not None

    sweep = auth_client.get(f"/api/runs/{run_id}/sweep").json()
    assert sweep["eer"]["discrete"] is not None
    assert sweep["operating_threshold"] is not None

    by_cond = auth_client.get(f"/api/runs/{run_id}/metrics/by-condition").json()
    assert any(row["tag"] == "lighting:normal" for row in by_cond["rows"])

    csv_text = auth_client.get(f"/api/runs/{run_id}/export/trials.csv").text
    assert csv_text.startswith("# run_id=")
    assert "image_b64" not in csv_text
    assert "probe_label" in csv_text

    # audit chain intact
    verify = auth_client.get("/api/audit/verify").json()
    assert verify["valid"] is True
    assert verify["events"] > 0


def test_withdrawal_deletes_templates_and_blocks_verify(auth_client):
    pid = _create_participant(auth_client, "W1")
    _enrol(auth_client, pid, identity=5)
    withdraw = auth_client.post(
        f"/api/participants/{pid}/consent/withdraw", json={"reason": "participant request"}
    )
    assert withdraw.status_code == 200
    assert withdraw.json()["templates_deleted"] == 5

    resp = auth_client.post(
        "/api/verify", json={"claimed_participant_id": pid, "image_b64": frame_b64(5, noise=1)}
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "CONSENT_INACTIVE"
