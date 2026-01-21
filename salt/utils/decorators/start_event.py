import os
import logging
from functools import wraps

log = logging.getLogger(__name__)


def fire_started_event_job_wrapper(function):
    """
    Fire a custom/job/<jid>/started/<minion_id> event when starting a job
    """

    @wraps(function)
    def wrapped(*args, **kwargs):
        """We wraps for *args and **kwargs, to be safe, but we expect: (cls, minion_instance, opts, data) as args"""

        try:
            sdata = {"pid": os.getpid()}
            sdata.update(args[3])

            jid = sdata["jid"]
            minion_id = args[1].opts.get("id", "undefined")

            args[1]._fire_master(sdata, f"custom/job/{jid}/started/{minion_id}")

        except Exception as exc:
            log.warning(f"Exception raised during started job event wrapper: {exc}")

        return function(*args, **kwargs)

    return wrapped
