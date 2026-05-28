import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.time import utc_now
from app.domain.enums import AmazonAuthorizationStatus, AmazonOAuthSessionStatus
from app.models.amazon import AmazonAuthorization, AmazonAuthorizationSession
from app.models.settings import SellerAccount
from app.services.amazon.lwa import LWAClient, LWATokenExchangeError, LWATokenResponse
from app.services.security.tokens import TokenCipher, TokenCipherConfigError


class LWAExchangeClient(Protocol):
    def exchange_authorization_code(self, *, code: str, redirect_uri: str) -> LWATokenResponse:
        pass


LWAClientFactory = Callable[[Settings], LWAExchangeClient]


@dataclass(frozen=True)
class AmazonOAuthStatus:
    public_base_url_configured: bool
    lwa_client_id_configured: bool
    lwa_client_secret_configured: bool
    token_encryption_key_configured: bool
    login_uri: str | None
    redirect_uri: str | None


@dataclass(frozen=True)
class LoginRedirect:
    state: str
    redirect_url: str


@dataclass(frozen=True)
class CallbackResult:
    authorization_id: int
    selling_partner_id: str
    seller_account_id: int | None
    status: str


class AmazonOAuthError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def build_public_url(settings: Settings, path: str) -> str | None:
    if not settings.PUBLIC_BASE_URL:
        return None
    return f"{settings.PUBLIC_BASE_URL.rstrip('/')}/{path.lstrip('/')}"


def get_oauth_status(settings: Settings) -> AmazonOAuthStatus:
    return AmazonOAuthStatus(
        public_base_url_configured=bool(settings.PUBLIC_BASE_URL),
        lwa_client_id_configured=bool(settings.AMAZON_LWA_CLIENT_ID),
        lwa_client_secret_configured=bool(settings.AMAZON_LWA_CLIENT_SECRET),
        token_encryption_key_configured=bool(settings.TOKEN_ENCRYPTION_KEY),
        login_uri=build_public_url(settings, settings.AMAZON_OAUTH_LOGIN_PATH),
        redirect_uri=build_public_url(settings, settings.AMAZON_OAUTH_REDIRECT_PATH),
    )


def create_login_redirect(
    *,
    session: Session,
    settings: Settings,
    amazon_callback_uri: str,
    amazon_state: str,
    selling_partner_id: str,
) -> LoginRedirect:
    parsed = urlparse(amazon_callback_uri)
    if parsed.scheme != "https":
        raise AmazonOAuthError("amazon_callback_uri must use https")

    local_state = secrets.token_urlsafe(32)
    oauth_session = AmazonAuthorizationSession(
        state=local_state,
        amazon_state=amazon_state,
        amazon_callback_uri=amazon_callback_uri,
        selling_partner_id=selling_partner_id,
        status=AmazonOAuthSessionStatus.CREATED.value,
        expires_at=utc_now() + timedelta(minutes=settings.AMAZON_OAUTH_STATE_TTL_MINUTES),
    )
    session.add(oauth_session)
    session.flush()

    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["state"] = local_state
    query["amazon_state"] = amazon_state
    redirect_url = urlunparse(parsed._replace(query=urlencode(query)))
    return LoginRedirect(state=local_state, redirect_url=redirect_url)


def handle_authorization_callback(
    *,
    session: Session,
    settings: Settings,
    state: str,
    selling_partner_id: str,
    spapi_oauth_code: str,
    lwa_client: LWAExchangeClient | None = None,
    token_cipher: TokenCipher | None = None,
    lwa_client_factory: LWAClientFactory | None = None,
) -> CallbackResult:
    oauth_session = session.scalar(
        select(AmazonAuthorizationSession).where(AmazonAuthorizationSession.state == state)
    )
    if oauth_session is None:
        raise AmazonOAuthError("state not found")
    if oauth_session.status != AmazonOAuthSessionStatus.CREATED.value:
        raise AmazonOAuthError("state has already been used")
    if _is_expired(oauth_session.expires_at):
        oauth_session.status = AmazonOAuthSessionStatus.EXPIRED.value
        oauth_session.error_message = "state expired"
        session.flush()
        raise AmazonOAuthError("state expired")
    if oauth_session.selling_partner_id != selling_partner_id:
        raise AmazonOAuthError("selling_partner_id does not match authorization session")

    redirect_uri = build_public_url(settings, settings.AMAZON_OAUTH_REDIRECT_PATH)
    if (
        not redirect_uri
        or not settings.AMAZON_LWA_CLIENT_ID
        or not settings.AMAZON_LWA_CLIENT_SECRET
    ):
        raise AmazonOAuthError("Amazon OAuth configuration is incomplete", status_code=500)

    try:
        token_cipher = token_cipher or TokenCipher(settings.TOKEN_ENCRYPTION_KEY)
    except TokenCipherConfigError as exc:
        raise AmazonOAuthError(str(exc), status_code=500) from exc

    if lwa_client is None:
        factory = lwa_client_factory or create_lwa_client
        lwa_client = factory(settings)

    try:
        token_response = lwa_client.exchange_authorization_code(
            code=spapi_oauth_code,
            redirect_uri=redirect_uri,
        )
        refresh_token_encrypted = token_cipher.encrypt(token_response.refresh_token)
    except (LWATokenExchangeError, TokenCipherConfigError, ValueError) as exc:
        oauth_session.status = AmazonOAuthSessionStatus.FAILED.value
        oauth_session.error_message = str(exc)
        session.flush()
        raise AmazonOAuthError("LWA token exchange failed", status_code=502) from exc

    seller_account = session.scalar(
        select(SellerAccount).where(SellerAccount.amazon_seller_id == selling_partner_id)
    )
    authorization = session.scalar(
        select(AmazonAuthorization).where(
            AmazonAuthorization.selling_partner_id == selling_partner_id
        )
    )
    now = utc_now()
    if authorization is None:
        authorization = AmazonAuthorization(
            selling_partner_id=selling_partner_id,
            seller_account=seller_account,
            lwa_client_id=settings.AMAZON_LWA_CLIENT_ID,
            refresh_token_encrypted=refresh_token_encrypted,
            token_type=token_response.token_type,
            authorized_at=now,
            status=AmazonAuthorizationStatus.ACTIVE.value,
        )
        session.add(authorization)
    else:
        authorization.seller_account = seller_account
        authorization.lwa_client_id = settings.AMAZON_LWA_CLIENT_ID
        authorization.refresh_token_encrypted = refresh_token_encrypted
        authorization.token_type = token_response.token_type
        authorization.authorized_at = now
        authorization.status = AmazonAuthorizationStatus.ACTIVE.value
        authorization.last_error = None

    oauth_session.status = AmazonOAuthSessionStatus.CONSUMED.value
    oauth_session.consumed_at = now
    session.flush()
    return CallbackResult(
        authorization_id=authorization.id,
        selling_partner_id=selling_partner_id,
        seller_account_id=authorization.seller_account_id,
        status=authorization.status,
    )


def _is_expired(expires_at: datetime) -> bool:
    now = utc_now()
    if expires_at.tzinfo is None:
        return expires_at < now.replace(tzinfo=None)
    return expires_at < now


def create_lwa_client(settings: Settings) -> LWAClient:
    if not settings.AMAZON_LWA_CLIENT_ID or not settings.AMAZON_LWA_CLIENT_SECRET:
        raise AmazonOAuthError("Amazon OAuth configuration is incomplete", status_code=500)
    return LWAClient(
        token_url=settings.AMAZON_LWA_TOKEN_URL,
        client_id=settings.AMAZON_LWA_CLIENT_ID,
        client_secret=settings.AMAZON_LWA_CLIENT_SECRET,
        timeout_seconds=settings.AMAZON_LWA_TIMEOUT_SECONDS,
    )
