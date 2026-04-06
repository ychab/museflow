from polyfactory.factories import DataclassFactory

from museflow.application.inputs.taste import BuildTasteProfileConfigInput


class BuildTasteProfileConfigInputFactory(DataclassFactory[BuildTasteProfileConfigInput]):
    __model__ = BuildTasteProfileConfigInput
