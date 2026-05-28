from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.settings import Marketplace, Organization, SellerAccount
from app.schemas.settings import (
    MarketplaceCreate,
    MarketplaceUpdate,
    SellerAccountCreate,
    SellerAccountUpdate,
    StoreOption,
)

DEFAULT_ORG_NAME = "Internal Team"
DEFAULT_ORG_SLUG = "internal"


def ensure_default_organization(session: Session) -> Organization:
    organization = session.scalar(
        select(Organization).where(Organization.slug == DEFAULT_ORG_SLUG)
    )
    if organization is not None:
        return organization

    organization = Organization(name=DEFAULT_ORG_NAME, slug=DEFAULT_ORG_SLUG)
    session.add(organization)
    session.flush()
    return organization


def create_seller_account(session: Session, payload: SellerAccountCreate) -> SellerAccount:
    organization = ensure_default_organization(session)
    seller_account = SellerAccount(
        organization=organization,
        display_name=payload.display_name,
        amazon_seller_id=payload.amazon_seller_id,
    )
    session.add(seller_account)
    session.flush()
    return seller_account


def update_seller_account(
    session: Session,
    seller_account_id: int,
    payload: SellerAccountUpdate,
) -> SellerAccount:
    seller_account = session.get(SellerAccount, seller_account_id)
    if seller_account is None:
        raise ValueError("seller account not found")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(seller_account, field, value)
    session.flush()
    return seller_account


def list_seller_accounts(session: Session) -> list[SellerAccount]:
    return list(session.scalars(select(SellerAccount).order_by(SellerAccount.id)))


def create_marketplace(session: Session, payload: MarketplaceCreate) -> Marketplace:
    seller_account = session.get(SellerAccount, payload.seller_account_id)
    if seller_account is None:
        raise ValueError("seller account not found")

    marketplace = Marketplace(
        seller_account=seller_account,
        marketplace_id=payload.marketplace_id,
        region=payload.region,
        country_code=payload.country_code,
        timezone=payload.timezone,
        currency_code=payload.currency_code,
    )
    session.add(marketplace)
    session.flush()
    return marketplace


def update_marketplace(
    session: Session,
    marketplace_id: int,
    payload: MarketplaceUpdate,
) -> Marketplace:
    marketplace = session.get(Marketplace, marketplace_id)
    if marketplace is None:
        raise ValueError("marketplace not found")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(marketplace, field, value)
    session.flush()
    return marketplace


def list_marketplaces(session: Session) -> list[Marketplace]:
    return list(session.scalars(select(Marketplace).order_by(Marketplace.id)))


def list_store_options(session: Session) -> list[StoreOption]:
    query = (
        select(Marketplace)
        .join(Marketplace.seller_account)
        .where(Marketplace.is_active.is_(True), SellerAccount.is_active.is_(True))
        .order_by(SellerAccount.display_name, Marketplace.country_code)
    )
    options: list[StoreOption] = []
    for marketplace in session.scalars(query):
        options.append(
            StoreOption(
                seller_account_id=marketplace.seller_account_id,
                marketplace_id=marketplace.id,
                label=f"{marketplace.seller_account.display_name} - {marketplace.country_code}",
                region=marketplace.region,
                country_code=marketplace.country_code,
                currency_code=marketplace.currency_code,
            )
        )
    return options
