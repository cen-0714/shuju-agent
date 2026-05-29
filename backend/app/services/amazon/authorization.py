from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.time import utc_now
from app.domain.enums import AmazonAuthorizationStatus
from app.models.amazon import AmazonAuthorization
from app.models.settings import SellerAccount
from app.services.security.tokens import TokenCipher, TokenCipherConfigError


@dataclass(frozen=True)
class AmazonAuthorizationStatusInfo:
    lwa_client_id_configured: bool
    lwa_client_secret_configured: bool
    token_encryption_key_configured: bool


class AmazonAuthorizationConfigError(Exception):
    pass


class AmazonAuthorizationNotFoundError(Exception):
    pass


def get_authorization_status(settings: Settings) -> AmazonAuthorizationStatusInfo:
    return AmazonAuthorizationStatusInfo(
        lwa_client_id_configured=bool(settings.AMAZON_LWA_CLIENT_ID),
        lwa_client_secret_configured=bool(settings.AMAZON_LWA_CLIENT_SECRET),
        token_encryption_key_configured=bool(settings.TOKEN_ENCRYPTION_KEY),
    )


def save_self_authorization(
    *,
    session: Session,
    settings: Settings,
    selling_partner_id: str,
    refresh_token: str,
    token_type: str | None,
) -> AmazonAuthorization:
    _validate_authorization_config(settings)
    try:
        refresh_token_encrypted = TokenCipher(settings.TOKEN_ENCRYPTION_KEY).encrypt(refresh_token)
    except TokenCipherConfigError as exc:
        raise AmazonAuthorizationConfigError(str(exc)) from exc

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
            lwa_client_id=settings.AMAZON_LWA_CLIENT_ID or "",
            refresh_token_encrypted=refresh_token_encrypted,
            token_type=token_type or "bearer",
            authorized_at=now,
            status=AmazonAuthorizationStatus.ACTIVE.value,
            last_error=None,
        )
        session.add(authorization)
    else:
        authorization.seller_account = seller_account
        authorization.lwa_client_id = settings.AMAZON_LWA_CLIENT_ID or ""
        authorization.refresh_token_encrypted = refresh_token_encrypted
        authorization.token_type = token_type or "bearer"
        authorization.authorized_at = now
        authorization.status = AmazonAuthorizationStatus.ACTIVE.value
        authorization.last_error = None

    session.flush()
    return authorization


def delete_authorization(session: Session, authorization_id: int) -> None:
    authorization = session.get(AmazonAuthorization, authorization_id)
    if authorization is None:
        raise AmazonAuthorizationNotFoundError("Amazon authorization not found")
    session.delete(authorization)
    session.flush()


def _validate_authorization_config(settings: Settings) -> None:
    missing = []
    if not settings.AMAZON_LWA_CLIENT_ID:
        missing.append("AMAZON_LWA_CLIENT_ID")
    if not settings.AMAZON_LWA_CLIENT_SECRET:
        missing.append("AMAZON_LWA_CLIENT_SECRET")
    if not settings.TOKEN_ENCRYPTION_KEY:
        missing.append("TOKEN_ENCRYPTION_KEY")
    if missing:
        missing_config = ", ".join(missing)
        raise AmazonAuthorizationConfigError(
            f"Missing Amazon authorization config: {missing_config}"
        )
