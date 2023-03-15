"""
    Log4Mongo Logging Handler
    =========================

    This module provides a logging handler for sending salt logs to MongoDB

    Configuration
    -------------

    In the salt configuration file (e.g. /etc/salt/{master,minion}):

    .. code-block:: yaml

        log4mongo_handler:
          host: mongodb_host
          port: 27017
          database_name: logs
          collection: salt_logs
          username: logging
          password: reindeerflotilla
          write_concern: 0
          log_level: warning


    Log Level
    .........

    If not set, the log_level will be set to the level defined in the global
    configuration file setting.

    .. admonition:: Inspiration

        This work was inspired by the Salt logging handlers for LogStash and
        Sentry and by the log4mongo Python implementation.
"""

import logging
import socket

from salt._logging import LOG_LEVELS

try:
    from log4mongo.handlers import MongoFormatter, MongoHandler

    HAS_MONGO = True
except ImportError:
    HAS_MONGO = False

__virtualname__ = "mongo"


def __virtual__():
    if not HAS_MONGO:
        return False
    return __virtualname__


class FormatterWithHost(logging.Formatter):
    def format(self, record):
        mongoformatter = MongoFormatter()
        document = mongoformatter.format(record)
        document["hostname"] = socket.gethostname()
        return document


def setup_handlers():
    handler_id = "log4mongo_handler"
    if handler_id in __opts__:
        config_fields = {
            "host": "host",
            "port": "port",
            "database_name": "database_name",
            "collection": "collection",
            "username": "username",
            "password": "password",
            "write_concern": "w",
        }

        config_opts = {}
        for config_opt, arg_name in config_fields.items():
            config_opts[arg_name] = __opts__[handler_id].get(config_opt)

        config_opts["level"] = LOG_LEVELS[
            __opts__[handler_id].get("log_level", __opts__.get("log_level", "error"))
        ]

        handler = MongoHandler(formatter=FormatterWithHost(), **config_opts)
        yield handler
    else:
        yield False
