from dataclasses import dataclass

import httpx


class LWATokenExchangeError(Exception):
    pass


@dataclass(frozen=True)
class LWATokenResponse:
    refresh_token: str
    access_token: str | None
    token_type: str | None
    expires_in: int | None


@dataclass(frozen=True)
class LWAAccessTokenResponse:
    access_token: str
    token_type: str | None
    expires_in: int | None


class LWAClient:
    def __init__(
        self,
        *,
        token_url: str,
        client_id: str,
        client_secret: str,
        timeout_seconds: int = 15,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def exchange_authorization_code(self, *, code: str, redirect_uri: str) -> LWATokenResponse:
        try:
            with httpx.Client(timeout=self.timeout_seconds, transport=self.transport) as client:
                response = client.post(
                    self.token_url,
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "redirect_uri": redirect_uri,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            raise LWATokenExchangeError(f"LWA token exchange failed: {exc}") from exc

        refresh_token = payload.get("refresh_token")
        if not refresh_token:
            raise LWATokenExchangeError("LWA token response did not include refresh_token")

        return LWATokenResponse(
            refresh_token=refresh_token,
            access_token=payload.get("access_token"),
            token_type=payload.get("token_type"),
            expires_in=payload.get("expires_in"),
        )

    def exchange_refresh_token(self, *, refresh_token: str) -> LWAAccessTokenResponse:
        try:
            with httpx.Client(timeout=self.timeout_seconds, transport=self.transport) as client:
                response = client.post(
                    self.token_url,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            raise LWATokenExchangeError(f"LWA refresh token exchange failed: {exc}") from exc

        access_token = payload.get("access_token")
        if not access_token:
            raise LWATokenExchangeError("LWA token response did not include access_token")

        return LWAAccessTokenResponse(
            access_token=access_token,
            token_type=payload.get("token_type"),
            expires_in=payload.get("expires_in"),
        )
