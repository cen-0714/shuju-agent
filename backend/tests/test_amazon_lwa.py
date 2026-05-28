import httpx
import pytest

from app.services.amazon.lwa import LWAClient, LWATokenExchangeError


def test_lwa_client_exchanges_authorization_code() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read().decode("utf-8")
        assert request.method == "POST"
        assert request.url == "https://api.amazon.com/auth/o2/token"
        assert "grant_type=authorization_code" in body
        assert "code=spapi-code" in body
        assert "client_id=client-id" in body
        assert "client_secret=client-secret" in body
        assert (
            "redirect_uri=https%3A%2F%2Fspapi.example.com%2Fapi%2Fauth%2Famazon%2Fcallback"
            in body
        )
        return httpx.Response(
            200,
            json={
                "refresh_token": "refresh-token",
                "access_token": "access-token",
                "token_type": "bearer",
                "expires_in": 3600,
            },
        )

    client = LWAClient(
        token_url="https://api.amazon.com/auth/o2/token",
        client_id="client-id",
        client_secret="client-secret",
        timeout_seconds=15,
        transport=httpx.MockTransport(handler),
    )

    result = client.exchange_authorization_code(
        code="spapi-code",
        redirect_uri="https://spapi.example.com/api/auth/amazon/callback",
    )

    assert result.refresh_token == "refresh-token"
    assert result.access_token == "access-token"
    assert result.token_type == "bearer"
    assert result.expires_in == 3600


def test_lwa_client_raises_clear_error_on_http_failure() -> None:
    client = LWAClient(
        token_url="https://api.amazon.com/auth/o2/token",
        client_id="client-id",
        client_secret="client-secret",
        transport=httpx.MockTransport(lambda _request: httpx.Response(400, text="bad code")),
    )

    with pytest.raises(LWATokenExchangeError, match="LWA token exchange failed"):
        client.exchange_authorization_code(
            code="bad-code",
            redirect_uri="https://spapi.example.com/api/auth/amazon/callback",
        )


def test_lwa_client_requires_refresh_token_in_response() -> None:
    client = LWAClient(
        token_url="https://api.amazon.com/auth/o2/token",
        client_id="client-id",
        client_secret="client-secret",
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={})),
    )

    with pytest.raises(LWATokenExchangeError, match="refresh_token"):
        client.exchange_authorization_code(
            code="spapi-code",
            redirect_uri="https://spapi.example.com/api/auth/amazon/callback",
        )
