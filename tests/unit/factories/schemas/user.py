from polyfactory.factories.pydantic_factory import ModelFactory

from museflow.domain.schemas.user import UserCreate
from museflow.domain.schemas.user import UserUpdate


class UserCreateFactory(ModelFactory[UserCreate]):
    __model__ = UserCreate


class UserUpdateFactory(ModelFactory[UserUpdate]):
    __model__ = UserUpdate
    __allow_none_optionals__ = False
