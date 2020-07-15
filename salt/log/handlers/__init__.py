# -*- coding: utf-8 -*-
"""
    salt.log.handlers
    ~~~~~~~~~~~~~~~~~

    .. versionadded:: 0.17.0

    Custom logging handlers to be used in salt.
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import salt libs
from salt._logging.handlers import (
    FileHandler,
    QueueHandler,
    RotatingFileHandler,
    StreamHandler,
    SysLogHandler,
    TemporaryLoggingHandler,
    WatchedFileHandler,
)

# from salt.utils.versions import warn_until_date
# warn_until_date(
#    '20220101',
#    'Please stop using \'{name}\' and instead use \'salt._logging.handlers\'. '
#    '\'{name}\' will go away after {{date}}.'.format(
#        name=__name__
#    )
# )

NullHandler = logging.NullHandler
