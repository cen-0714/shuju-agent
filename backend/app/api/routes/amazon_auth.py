from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_session, get_settings
from app.core.config import Settings
from app.models.amazon import AmazonAuthorization
from app.schemas.amazon import (
    AmazonAuthorizationResponse,
    AmazonAuthorizationStatusResponse,
    AmazonSelfAuthorizationCreate,
)
from app.services.amazon.authorization import (
    AmazonAuthorizationConfigError,
    AmazonAuthorizationNotFoundError,
    delete_authorization,
    get_authorization_status,
    save_self_authorization,
)

router = APIRouter(prefix="/auth/amazon", tags=["amazon-auth"])
SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.get("/status", response_model=AmazonAuthorizationStatusResponse)
def status(settings: SettingsDep) -> AmazonAuthorizationStatusResponse:
    return AmazonAuthorizationStatusResponse.model_validate(
        get_authorization_status(settings).__dict__
    )


@router.post("/self-authorizations", response_model=AmazonAuthorizationResponse)
def post_self_authorization(
    payload: AmazonSelfAuthorizationCreate,
    session: SessionDep,
    settings: SettingsDep,
) -> AmazonAuthorization:
    try:
        authorization = save_self_authorization(
            session=session,
            settings=settings,
            selling_partner_id=payload.selling_partner_id,
            refresh_token=payload.refresh_token,
            token_type=payload.token_type,
        )
    except AmazonAuthorizationConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    session.commit()
    return authorization


@router.get("/authorizations", response_model=list[AmazonAuthorizationResponse])
def authorizations(session: SessionDep) -> list[AmazonAuthorization]:
    return list(session.scalars(select(AmazonAuthorization).order_by(AmazonAuthorization.id)))


@router.delete("/authorizations/{authorization_id}", status_code=204)
def delete_authorization_endpoint(authorization_id: int, session: SessionDep) -> Response:
    try:
        delete_authorization(session, authorization_id)
    except AmazonAuthorizationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    return Response(status_code=204)
