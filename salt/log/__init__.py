"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    salt.log
    ~~~~~~~~

    This is where Salt's logging gets set up. Currently, the required imports
    are made to assure backwards compatibility.
"""

# Import several classes/functions from salt.log.setup for backwards compatibility
from salt._logging import LOG_LEVELS, SORTED_LEVEL_NAMES
from salt.log.setup import (
    is_console_configured,
    is_logfile_configured,
    is_logging_configured,
    is_temp_logging_configured,
    set_logger_level,
    setup_console_logger,
    setup_logfile_logger,
    setup_temp_logger,
)
from salt.utils.versions import warn_until_date

warn_until_date(
    "20240101",
    "Please stop using '{name}' and instead use 'salt._logging'. "
    "'{name}' will go away after {{date}}.".format(name=__name__),
    stacklevel=3,
)
