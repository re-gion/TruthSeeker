from fastapi.testclient import TestClient

from app.main import app


def test_upload_preflight_allows_localhost_alias_origin():
    client = TestClient(app)

    response = client.options(
        "/api/v1/upload/",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"
