import base64

from polyfactory.decorators import post_generated
from polyfactory.factories.dataclass_factory import DataclassFactory

from museflow.domain.entities.user import User


class UserFactory(DataclassFactory[User]):
    __model__ = User

    is_active = True

    @post_generated
    @classmethod
    def hashed_password(cls, password: str = "testtest") -> str:
        return base64.b64encode(password.encode()).decode()
