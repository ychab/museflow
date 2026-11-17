from polyfactory import Use
from polyfactory.decorators import post_generated

from museflow.infrastructure.adapters.database.models import UserModel

from tests.integration.factories.models.base import BaseModelFactory


class UserModelFactory(BaseModelFactory[UserModel]):
    __model__ = UserModel

    email = Use(BaseModelFactory.__faker__.email)

    is_active = True

    @post_generated
    @classmethod
    def hashed_password(cls, password: str = "testtest") -> str:
        from tests.integration.conftest import get_password_hasher

        return get_password_hasher().hash(password)
