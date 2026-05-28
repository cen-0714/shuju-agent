from pydantic import BaseModel, ConfigDict


class MarketplaceSeed(BaseModel):
    marketplace_id: str
    region: str
    country_code: str
    timezone: str
    currency_code: str


class SellerAccountCreate(BaseModel):
    display_name: str
    amazon_seller_id: str


class SellerAccountUpdate(BaseModel):
    display_name: str | None = None
    amazon_seller_id: str | None = None
    is_active: bool | None = None


class SellerAccountResponse(BaseModel):
    id: int
    display_name: str
    amazon_seller_id: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class MarketplaceCreate(BaseModel):
    seller_account_id: int
    marketplace_id: str
    region: str
    country_code: str
    timezone: str
    currency_code: str


class MarketplaceUpdate(BaseModel):
    region: str | None = None
    country_code: str | None = None
    timezone: str | None = None
    currency_code: str | None = None
    is_active: bool | None = None


class MarketplaceResponse(BaseModel):
    id: int
    seller_account_id: int
    marketplace_id: str
    region: str
    country_code: str
    timezone: str
    currency_code: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class StoreOption(BaseModel):
    seller_account_id: int
    marketplace_id: int
    label: str
    region: str
    country_code: str
    currency_code: str
