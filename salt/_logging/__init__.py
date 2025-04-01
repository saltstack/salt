"""
    salt._logging
    ~~~~~~~~~~~~~

    This is salt's new logging setup.
    As the name suggests, this is considered an internal API which can change without notice,
    although, as best effort, we'll try not to break code relying on it.

    The ``salt._logging`` package should be imported as soon as possible since salt tweaks
    the python's logging system.
"""

from salt._logging.impl import (
    DFLT_LOG_DATEFMT,
    DFLT_LOG_DATEFMT_LOGFILE,
    DFLT_LOG_FMT_CONSOLE,
    DFLT_LOG_FMT_JID,
    DFLT_LOG_FMT_LOGFILE,
    LOG_COLORS,
    LOG_LEVELS,
    LOG_VALUES_TO_LEVELS,
    SORTED_LEVEL_NAMES,
    freeze_logging_options_dict,
    get_console_handler,
    get_extended_logging_handlers,
    get_log_record_factory,
    get_logfile_handler,
    get_logging_level_from_string,
    get_logging_options_dict,
    get_lowest_log_level,
    get_temp_handler,
    in_mainprocess,
    is_console_handler_configured,
    is_extended_logging_configured,
    is_logfile_handler_configured,
    is_temp_handler_configured,
    set_log_record_factory,
    set_logging_options_dict,
    set_lowest_log_level,
    set_lowest_log_level_by_opts,
    setup_console_handler,
    setup_extended_logging,
    setup_log_granular_levels,
    setup_logfile_handler,
    setup_logging,
    setup_temp_handler,
    shutdown_console_handler,
    shutdown_extended_logging,
    shutdown_logfile_handler,
    shutdown_logging,
    shutdown_temp_handler,
)
