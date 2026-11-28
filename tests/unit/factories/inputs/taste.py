from datetime import timedelta

from polyfactory.factories import DataclassFactory

from museflow.application.inputs.taste import BuildTasteProfileConfigInput


class BuildTasteProfileConfigInputFactory(DataclassFactory[BuildTasteProfileConfigInput]):
    __model__ = BuildTasteProfileConfigInput

    throttling_sleep_seconds = 0.0
    resume = False
    rated_only = False
    # A random duration may be negative, or overflow the database timestamps once added to now()
    lease_duration = timedelta(minutes=15)
    # A CLI build by default: a random job would break the foreign key of the lease
    job_id = None
