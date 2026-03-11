from polyfactory.factories.pydantic_factory import ModelFactory

from museflow.application.inputs.user import UserCreateInput
from museflow.application.inputs.user import UserUpdateInput


class UserCreateInputFactory(ModelFactory[UserCreateInput]):
    __model__ = UserCreateInput


class UserUpdateInputFactory(ModelFactory[UserUpdateInput]):
    __model__ = UserUpdateInput
    __allow_none_optionals__ = False
