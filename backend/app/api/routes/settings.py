from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.schemas.settings import (
    MarketplaceCreate,
    MarketplaceResponse,
    MarketplaceSeed,
    MarketplaceUpdate,
    SellerAccountCreate,
    SellerAccountResponse,
    SellerAccountUpdate,
    StoreOption,
)
from app.services.settings import (
    create_marketplace,
    create_seller_account,
    list_marketplaces,
    list_seller_accounts,
    list_store_options,
    update_marketplace,
    update_seller_account,
)

router = APIRouter(prefix="/settings", tags=["settings"])
SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/default-marketplaces", response_model=list[MarketplaceSeed])
def default_marketplaces() -> list[MarketplaceSeed]:
    return [
        MarketplaceSeed(
            marketplace_id="ATVPDKIKX0DER",
            region="americas",
            country_code="US",
            timezone="America/Los_Angeles",
            currency_code="USD",
        ),
        MarketplaceSeed(
            marketplace_id="A2EUQ1WTGCTBG2",
            region="americas",
            country_code="CA",
            timezone="America/Toronto",
            currency_code="CAD",
        ),
        MarketplaceSeed(
            marketplace_id="A1AM78C64UM0Y8",
            region="americas",
            country_code="MX",
            timezone="America/Mexico_City",
            currency_code="MXN",
        ),
    ]


@router.get("/seller-accounts", response_model=list[SellerAccountResponse])
def get_seller_accounts(session: SessionDep) -> list[SellerAccountResponse]:
    return list_seller_accounts(session)


@router.post("/seller-accounts", response_model=SellerAccountResponse)
def post_seller_account(
    payload: SellerAccountCreate,
    session: SessionDep,
) -> SellerAccountResponse:
    seller_account = create_seller_account(session, payload)
    session.commit()
    return seller_account


@router.patch("/seller-accounts/{seller_account_id}", response_model=SellerAccountResponse)
def patch_seller_account(
    seller_account_id: int,
    payload: SellerAccountUpdate,
    session: SessionDep,
) -> SellerAccountResponse:
    try:
        seller_account = update_seller_account(session, seller_account_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    return seller_account


@router.get("/marketplaces", response_model=list[MarketplaceResponse])
def get_marketplaces(session: SessionDep) -> list[MarketplaceResponse]:
    return list_marketplaces(session)


@router.post("/marketplaces", response_model=MarketplaceResponse)
def post_marketplace(
    payload: MarketplaceCreate,
    session: SessionDep,
) -> MarketplaceResponse:
    try:
        marketplace = create_marketplace(session, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    return marketplace


@router.patch("/marketplaces/{marketplace_id}", response_model=MarketplaceResponse)
def patch_marketplace(
    marketplace_id: int,
    payload: MarketplaceUpdate,
    session: SessionDep,
) -> MarketplaceResponse:
    try:
        marketplace = update_marketplace(session, marketplace_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    return marketplace


@router.get("/store-options", response_model=list[StoreOption])
def get_store_options(session: SessionDep) -> list[StoreOption]:
    return list_store_options(session)
