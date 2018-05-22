# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    salt.log
    ~~~~~~~~

    This is where Salt's logging gets set up. Currently, the required imports
    are made to assure backwards compatibility.
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import severals classes/functions from salt.log.setup for backwards
# compatibility
from salt.log.setup import (
    LOG_LEVELS,
    SORTED_LEVEL_NAMES,
    is_console_configured,
    is_logfile_configured,
    is_logging_configured,
    is_temp_logging_configured,
    setup_temp_logger,
    setup_console_logger,
    setup_logfile_logger,
    set_logger_level,
)
