from fastapi.testclient import TestClient

from hermod.main import app


def test_health():
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}


def test_webhook_verify_rejects_bad_token():
    with TestClient(app) as client:
        r = client.get(
            "/webhook/whatsapp",
            params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "x"},
        )
        assert r.status_code == 403
