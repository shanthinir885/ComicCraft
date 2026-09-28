"""Route-level tests: pages, health, validation and error envelopes."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_homepage_renders(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Turn Your Ideas Into" in response.text
    assert "comicForm" in response.text


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "gemini_configured" in payload
    assert "image_provider" in payload


def test_openapi_docs_available(client: TestClient) -> None:
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200


def test_json_endpoint_rejects_invalid_payload(client: TestClient) -> None:
    response = client.post("/generate-comic/json", json={"story_prompt": "too short"})
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["code"] == "validation_error"


def test_json_endpoint_without_api_key_returns_configuration_error(
    client: TestClient, monkeypatch
) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    response = client.post(
        "/generate-comic/json",
        json={
            "story_prompt": "A brave fox discovers a portal in an enchanted forest.",
            "character_name": "Finn",
            "setting": "Enchanted Forest",
            "tone": "Adventure",
            "art_style": "Comic Book",
        },
    )
    assert response.status_code == 502
    assert response.json()["code"] == "missing_api_key"


def test_download_rejects_path_traversal(client: TestClient) -> None:
    response = client.get("/download", params={"pdf_url": "/static/../../etc/passwd"})
    assert response.status_code in (400, 404)


def test_export_success_page(client: TestClient) -> None:
    response = client.get("/export-success", params={"title": "My Comic"})
    assert response.status_code == 200
    assert "Your Comic Is Ready!" in response.text


def test_unknown_page_returns_error_template(client: TestClient) -> None:
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert "wrong turn" in response.text
