from pydantic import BaseModel
from pydantic import ConfigDict


class BaseInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
