from polyfactory.factories import DataclassFactory

from museflow.domain.entities.taste import TasteProfile


class TasteProfileFactory(DataclassFactory[TasteProfile]):
    __model__ = TasteProfile
