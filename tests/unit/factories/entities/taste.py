from polyfactory.factories import DataclassFactory

from museflow.domain.entities.taste import UserTasteProfile


class UserTasteProfileFactory(DataclassFactory[UserTasteProfile]):
    __model__ = UserTasteProfile
