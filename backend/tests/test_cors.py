"""The operator console is served by the Vite dev server on another origin,
so the browser preflights cross-origin calls to the API (CORS)."""

import pytest


@pytest.mark.parametrize(
    "origin", ["http://localhost:5173", "http://127.0.0.1:5173"]
)
async def test_preflight_from_vite_dev_server_is_allowed(client, origin):
    response = await client.options(
        "/api/operator/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


async def test_preflight_from_unknown_origin_is_not_granted(client):
    response = await client.options(
        "/api/operator/login",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert "access-control-allow-origin" not in response.headers
