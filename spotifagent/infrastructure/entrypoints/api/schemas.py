from pydantic import BaseModel


class HealthCheckResponse(BaseModel):
    status: str
    database: str


class SuccessResponse(BaseModel):
    message: str
