from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AmazonAuthorizationStatusResponse(BaseModel):
    lwa_client_id_configured: bool
    lwa_client_secret_configured: bool
    token_encryption_key_configured: bool


class AmazonSelfAuthorizationCreate(BaseModel):
    selling_partner_id: str = Field(min_length=1, max_length=120)
    refresh_token: str = Field(min_length=1)
    token_type: str | None = Field(default="bearer", max_length=80)


class AmazonAuthorizationResponse(BaseModel):
    id: int
    selling_partner_id: str
    seller_account_id: int | None
    token_type: str | None
    status: str
    authorized_at: datetime

    model_config = ConfigDict(from_attributes=True)
