from pydantic import BaseModel
from pydantic import ConfigDict


class BaseValueObject(BaseModel):
    model_config = ConfigDict(from_attributes=True)
