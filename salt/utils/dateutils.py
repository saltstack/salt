"""
Convenience functions for dealing with datetime classes
"""


import datetime

import salt.utils.stringutils
from salt.utils.decorators.jinja import jinja_filter

try:
    import timelib

    HAS_TIMELIB = True
except ImportError:
    HAS_TIMELIB = False


def date_cast(date):
    """
    Casts any object into a datetime.datetime object

    date
      any datetime, time string representation...
    """
    if date is None:
        return datetime.datetime.now()
    elif isinstance(date, datetime.datetime):
        return date

    # fuzzy date
    try:
        if isinstance(date, str):
            try:
                if HAS_TIMELIB:
                    # py3: yes, timelib.strtodatetime wants bytes, not str :/
                    return timelib.strtodatetime(salt.utils.stringutils.to_bytes(date))
            except ValueError:
                pass

            # not parsed yet, obviously a timestamp?
            if date.isdigit():
                date = int(date)
            else:
                date = float(date)

        return datetime.datetime.fromtimestamp(date)
    except Exception:  # pylint: disable=broad-except
        if HAS_TIMELIB:
            raise ValueError("Unable to parse {}".format(date))

        raise RuntimeError(
            "Unable to parse {}. Consider installing timelib".format(date)
        )


@jinja_filter("date_format")
@jinja_filter("strftime")
def strftime(date=None, format="%Y-%m-%d"):
    """
    Converts date into a time-based string

    date
      any datetime, time string representation...

    format
       :ref:`strftime<http://docs.python.org/2/library/datetime.html#datetime.datetime.strftime>` format

    >>> import datetime
    >>> src = datetime.datetime(2002, 12, 25, 12, 00, 00, 00)
    >>> strftime(src)
    '2002-12-25'
    >>> src = '2002/12/25'
    >>> strftime(src)
    '2002-12-25'
    >>> src = 1040814000
    >>> strftime(src)
    '2002-12-25'
    >>> src = '1040814000'
    >>> strftime(src)
    '2002-12-25'
    """
    return date_cast(date).strftime(format)


def total_seconds(td):
    """
    Takes a timedelta and returns the total number of seconds
    represented by the object. Wrapper for the total_seconds()
    method which does not exist in versions of Python < 2.7.
    """
    return (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6
