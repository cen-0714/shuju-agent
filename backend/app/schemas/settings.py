from pydantic import BaseModel


class MarketplaceSeed(BaseModel):
    marketplace_id: str
    region: str
    country_code: str
    timezone: str
    currency_code: str
