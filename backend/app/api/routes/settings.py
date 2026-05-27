from fastapi import APIRouter

from app.schemas.settings import MarketplaceSeed

router = APIRouter(prefix="/settings", tags=["settings"])


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
