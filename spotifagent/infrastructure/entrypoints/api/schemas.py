import uuid

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import EmailStr


class HealthCheckResponse(BaseModel):
    status: str
    database: str


class SuccessResponse(BaseModel):
    message: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    is_active: bool


class UserWithToken(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user: UserResponse
    access_token: str
    token_type: str = "Bearer"
