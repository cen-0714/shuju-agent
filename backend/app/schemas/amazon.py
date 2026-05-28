from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AmazonOAuthStatusResponse(BaseModel):
    public_base_url_configured: bool
    lwa_client_id_configured: bool
    lwa_client_secret_configured: bool
    token_encryption_key_configured: bool
    login_uri: str | None
    redirect_uri: str | None


class AmazonAuthorizationCallbackResponse(BaseModel):
    authorization_id: int
    selling_partner_id: str
    seller_account_id: int | None
    status: str


class AmazonAuthorizationResponse(BaseModel):
    id: int
    selling_partner_id: str
    seller_account_id: int | None
    status: str
    authorized_at: datetime

    model_config = ConfigDict(from_attributes=True)
