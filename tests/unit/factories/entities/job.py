from polyfactory.factories.dataclass_factory import DataclassFactory

from museflow.domain.entities.job import Job


class JobFactory(DataclassFactory[Job]):
    __model__ = Job
    __set_as_default_factory_for_type__ = True
    __use_defaults__ = True
