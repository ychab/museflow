from pydantic import BaseModel
from pydantic import ConfigDict


class BaseEntity(BaseModel):
    model_config = ConfigDict(from_attributes=True)
