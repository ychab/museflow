from polyfactory import Use
from polyfactory.factories.dataclass_factory import DataclassFactory

from museflow.domain.value_objects.taste import ListeningPeriod
from museflow.domain.value_objects.taste import PeriodTrack

from tests.unit.factories.entities.track import TrackFactory


class PeriodTrackFactory(DataclassFactory[PeriodTrack]):
    __model__ = PeriodTrack

    track = Use(TrackFactory.build)


class ListeningPeriodFactory(DataclassFactory[ListeningPeriod]):
    __model__ = ListeningPeriod

    tracks = Use(PeriodTrackFactory.batch, size=3)
