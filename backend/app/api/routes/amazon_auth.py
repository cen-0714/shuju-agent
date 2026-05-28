from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_session, get_settings
from app.core.config import Settings
from app.models.amazon import AmazonAuthorization
from app.schemas.amazon import (
    AmazonAuthorizationCallbackResponse,
    AmazonAuthorizationResponse,
    AmazonOAuthStatusResponse,
)
from app.services.amazon.oauth import (
    AmazonOAuthError,
    LWAClientFactory,
    create_login_redirect,
    create_lwa_client,
    get_oauth_status,
    handle_authorization_callback,
)

router = APIRouter(prefix="/auth/amazon", tags=["amazon-auth"])
SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_lwa_client_factory() -> LWAClientFactory:
    return create_lwa_client


@router.get("/status", response_model=AmazonOAuthStatusResponse)
def status(settings: SettingsDep) -> AmazonOAuthStatusResponse:
    return AmazonOAuthStatusResponse.model_validate(get_oauth_status(settings).__dict__)


@router.get("/login")
def login(
    session: SessionDep,
    settings: SettingsDep,
    amazon_callback_uri: Annotated[str, Query(min_length=1)],
    amazon_state: Annotated[str, Query(min_length=1)],
    selling_partner_id: Annotated[str, Query(min_length=1)],
) -> RedirectResponse:
    try:
        result = create_login_redirect(
            session=session,
            settings=settings,
            amazon_callback_uri=amazon_callback_uri,
            amazon_state=amazon_state,
            selling_partner_id=selling_partner_id,
        )
    except AmazonOAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    session.commit()
    return RedirectResponse(result.redirect_url, status_code=307)


@router.get("/callback", response_model=AmazonAuthorizationCallbackResponse)
def callback(
    session: SessionDep,
    settings: SettingsDep,
    lwa_client_factory: Annotated[LWAClientFactory, Depends(get_lwa_client_factory)],
    state: Annotated[str, Query(min_length=1)],
    selling_partner_id: Annotated[str, Query(min_length=1)],
    spapi_oauth_code: Annotated[str, Query(min_length=1)],
) -> AmazonAuthorizationCallbackResponse:
    try:
        result = handle_authorization_callback(
            session=session,
            settings=settings,
            state=state,
            selling_partner_id=selling_partner_id,
            spapi_oauth_code=spapi_oauth_code,
            lwa_client_factory=lwa_client_factory,
        )
    except AmazonOAuthError as exc:
        session.commit()
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    session.commit()
    return AmazonAuthorizationCallbackResponse(**result.__dict__)


@router.get("/authorizations", response_model=list[AmazonAuthorizationResponse])
def authorizations(session: SessionDep) -> list[AmazonAuthorization]:
    return list(session.scalars(select(AmazonAuthorization).order_by(AmazonAuthorization.id)))
