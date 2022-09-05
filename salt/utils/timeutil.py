"""
Functions various time manipulations.
"""

# Import Python
import logging
import time
from datetime import datetime, timedelta

# Import Salt modules

log = logging.getLogger(__name__)


def get_timestamp_at(time_in=None, time_at=None):
    """
    Computes the timestamp for a future event that may occur in ``time_in`` time
    or at ``time_at``.
    """
    if time_in:
        if isinstance(time_in, int):
            hours = 0
            minutes = time_in
        else:
            time_in = time_in.replace("h", ":")
            time_in = time_in.replace("m", "")
            try:
                hours, minutes = time_in.split(":")
            except ValueError:
                hours = 0
                minutes = time_in
            if not minutes:
                minutes = 0
            hours, minutes = int(hours), int(minutes)
        dt = timedelta(hours=hours, minutes=minutes)
        time_now = datetime.utcnow()
        time_at = time_now + dt
        return time.mktime(time_at.timetuple())
    elif time_at:
        log.debug("Predicted at specified as %s", time_at)
        if isinstance(time_at, (int, float)):
            # then it's a timestamp
            return time_at
        else:
            fmts = ("%H%M", "%Hh%M", "%I%p", "%I:%M%p", "%I:%M %p")
            # Support different formats for the timestamp
            # The current formats accepted are the following:
            #
            #   - 18:30 (and 18h30)
            #   - 1pm (no minutes, fixed hour)
            #   - 1:20am (and 1:20am - with or without space)
            for fmt in fmts:
                try:
                    log.debug("Trying to match %s", fmt)
                    dt = datetime.strptime(time_at, fmt)
                    return time.mktime(dt.timetuple())
                except ValueError:
                    log.debug("Did not match %s, continue searching", fmt)
                    continue
            msg = "{pat} does not match any of the accepted formats: {fmts}".format(
                pat=time_at, fmts=", ".join(fmts)
            )
            log.error(msg)
            raise ValueError(msg)


def get_time_at(time_in=None, time_at=None, out_fmt="%Y-%m-%dT%H:%M:%S"):
    """
    Return the time in human readable format for a future event that may occur
    in ``time_in`` time, or at ``time_at``.
    """
    dt = get_timestamp_at(time_in=time_in, time_at=time_at)
    return time.strftime(out_fmt, time.localtime(dt))
