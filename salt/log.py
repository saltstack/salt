# -*- coding: utf-8 -*-
"""
    salt.log
    ~~~~~~~~

    This is were Salt's logging get's setup.


    :copyright: © 2011 :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: Apache 2.0, see LICENSE for more details.
"""

import logging
import logging.handlers

TRACE = 5
GARBAGE = 1

LOG_LEVELS = {
    'none': logging.NOTSET,
    'info': logging.INFO,
    'warn': logging.WARNING,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'none': logging.CRITICAL,
    'debug': logging.DEBUG,
    'trace': TRACE,
    'garbage': GARBAGE
}

LoggingLoggerClass = logging.getLoggerClass()

class Logging(LoggingLoggerClass):
    def garbage(self, msg, *args, **kwargs):
        return LoggingLoggerClass.log(self, 1, msg, *args, **kwargs)

    def trace(self, msg, *args, **kwargs):
        return LoggingLoggerClass.log(self, 5, msg, *args, **kwargs)

def getLogger(name):
    init()
    return logging.getLogger(name)

def init():
    '''
    Replace the default system logger with a version that includes trace()
    and garbage() methods.
    '''
    if logging.getLoggerClass() is not Logging:
        logging.setLoggerClass(Logging)
        logging.addLevelName(5, 'TRACE')
        logging.addLevelName(1, 'GARBAGE')
        # Set the root logger at the lowest level possible
        logging.getLogger().setLevel(1)

def setup_console_logger(log_level):
    '''
    Setup the console logger
    '''
    init()
    level = LOG_LEVELS.get(log_level.lower(), logging.ERROR)

    rootLogger = logging.getLogger()
    handler = logging.StreamHandler()

    handler.setLevel(level)
    formatter = logging.Formatter(
        '%(asctime)s,%(msecs)03.0f [%(name)-15s][%(levelname)-8s] %(message)s',
        datefmt="%H:%M:%S"
    )

    handler.setFormatter(formatter)
    rootLogger.addHandler(handler)


def setup_logfile_logger(log_path, log_level):
    '''
    Setup the logfile logger
    '''
    init()
    level = LOG_LEVELS.get(log_level.lower(), logging.ERROR)

    rootLogger = logging.getLogger()
    handler = getattr(
        logging.handlers, 'WatchedFileHandler', logging.FileHandler)(
            log_path, 'a', 'utf-8', delay=0
    )

    handler.setLevel(level)
    formatter = logging.Formatter(
        '%(asctime)s [%(name)-15s][%(levelname)-8s] %(message)s',
    )

    handler.setFormatter(formatter)
    rootLogger.addHandler(handler)

def set_logger_level(logger_name, log_level):
    '''
    Tweak a specific logger's logging level
    '''
    init()
    logging.getLogger(logger_name).setLevel(
        LOG_LEVELS.get(log_level.lower(), logging.ERROR)
    )
