from pydantic import BaseModel


class ProviderConnectResponse(BaseModel):
    authorization_url: str


class ProviderConnectCompleteRequest(BaseModel):
    # What the provider appended to the redirect URI, which the client reads back
    code: str
    state: str
