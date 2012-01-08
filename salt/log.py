'''
    salt.log
    ~~~~~~~~

    This is where Salt's logging gets set up.


    :copyright: 2011 :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: Apache 2.0, see LICENSE for more details.
'''

import logging
import logging.handlers

TRACE = 5
GARBAGE = 1

LOG_LEVELS = {
    'debug': logging.DEBUG,
    'error': logging.ERROR,
    'garbage': GARBAGE,
    'info': logging.INFO,
    'none': logging.NOTSET,
    'trace': TRACE,
    'warning': logging.WARNING,
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


def setup_console_logger(log_level='error', log_format=None, date_format=None):
    '''
    Setup the console logger
    '''
    init()
    level = LOG_LEVELS.get(log_level.lower(), logging.ERROR)

    rootLogger = logging.getLogger()
    handler = logging.StreamHandler()

    handler.setLevel(level)

    # Set the default console formatter config
    if not log_format:
        log_format = '[%(levelname)-8s] %(message)s'
    if not date_format:
        date_format = '%H:%M:%S'

    formatter = logging.Formatter(
        log_format,
        datefmt = date_format
    )

    handler.setFormatter(formatter)
    rootLogger.addHandler(handler)


def setup_logfile_logger(log_path, log_level='error'):
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


def set_logger_level(logger_name, log_level='error'):
    '''
    Tweak a specific logger's logging level
    '''
    init()
    logging.getLogger(logger_name).setLevel(
        LOG_LEVELS.get(log_level.lower(), logging.ERROR)
    )
