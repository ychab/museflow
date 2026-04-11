from polyfactory.factories.dataclass_factory import DataclassFactory

from museflow.domain.value_objects.taste import DiscoveryTasteStrategy


class DiscoveryTasteStrategyFactory(DataclassFactory[DiscoveryTasteStrategy]):
    __model__ = DiscoveryTasteStrategy
