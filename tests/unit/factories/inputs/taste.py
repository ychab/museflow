from polyfactory.factories import DataclassFactory

from museflow.application.inputs.taste import BuildTasteProfileConfigInput


class BuildTasteProfileConfigInputFactory(DataclassFactory[BuildTasteProfileConfigInput]):
    __model__ = BuildTasteProfileConfigInput

    throttling_sleep_seconds = 0.0
    resume = False
    rated_only = False
