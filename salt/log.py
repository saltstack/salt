'''
    salt.log
    ~~~~~~~~

    This is where Salt's logging gets set up.


    :copyright: 2011-2012 :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: Apache 2.0, see LICENSE for more details.
'''

import re
import sys
import logging
import logging.handlers

TRACE = logging.TRACE = 5
GARBAGE = logging.GARBAGE = 1

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

MODNAME_PATTERN = re.compile(r'(?P<name>%%\(name\)(?P<digits>\-(?:[\d]+))?s)')
MAX_LOGGER_MODNAME_LENGTH = 4

__CONSOLE_CONFIGURED = False
__LOGFILE_CONFIGURED = False

def is_console_configured():
    global __CONSOLE_CONFIGURED
    return __CONSOLE_CONFIGURED

def is_logfile_configured():
    global __LOGFILE_CONFIGURED
    return __LOGFILE_CONFIGURED


class Logging(LoggingLoggerClass):
    def __new__(cls, logger_name, *args, **kwargs):
        global MAX_LOGGER_MODNAME_LENGTH
        # This makes module name padding increase to the biggest module name
        # so that logs keep readability.
        #
        # This code will only run when a new logger is created, ie:
        #
        #    logging.getLogger(__name__)
        #
        instance = super(Logging, cls).__new__(cls)

        try:
            max_logger_name = max(logging.Logger.manager.loggerDict.keys())

            if len(max_logger_name) > MAX_LOGGER_MODNAME_LENGTH:
                MAX_LOGGER_MODNAME_LENGTH = len(max_logger_name)
                for handler in logging.getLogger().handlers:
                    if not handler.lock:
                        handler.createLock()
                    handler.acquire()

                    formatter = handler.formatter
                    fmt = formatter._fmt.replace('%', '%%')

                    match = MODNAME_PATTERN.search(fmt)
                    if match:
                        fmt = fmt.replace(match.group('name'), '%%(name)-%ds')
                        formatter = logging.Formatter(
                            fmt % MAX_LOGGER_MODNAME_LENGTH,
                            datefmt=formatter.datefmt
                        )
                        handler.setFormatter(formatter)
                    handler.release()
        except ValueError:
            # There are no registered loggers yet
            pass
        return instance

    def garbage(self, msg, *args, **kwargs):
        return LoggingLoggerClass.log(self, GARBAGE, msg, *args, **kwargs)

    def trace(self, msg, *args, **kwargs):
        return LoggingLoggerClass.log(self, TRACE, msg, *args, **kwargs)


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
        logging.addLevelName(TRACE, 'TRACE')
        logging.addLevelName(GARBAGE, 'GARBAGE')
        # Set the root logger at the lowest level possible
        logging.getLogger().setLevel(GARBAGE)


def setup_console_logger(log_level='error', log_format=None, date_format=None):
    '''
    Setup the console logger
    '''
    if is_console_configured():
        logging.getLogger(__name__).warning("Console logging already configured")
        return

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

    formatter = logging.Formatter(log_format, datefmt=date_format)

    handler.setFormatter(formatter)
    rootLogger.addHandler(handler)

    global __CONSOLE_CONFIGURED
    __CONSOLE_CONFIGURED = True


def setup_logfile_logger(log_path, log_level='error', log_format=None,
                         date_format=None):
    '''
    Setup the logfile logger
    '''

    if is_logfile_configured():
        logging.getLogger(__name__).warning("Logfile logging already configured")
        return

    init()
    level = LOG_LEVELS.get(log_level.lower(), logging.ERROR)

    try:
        rootLogger = logging.getLogger()
        handler = getattr(
            logging.handlers, 'WatchedFileHandler', logging.FileHandler)(
                log_path, 'a', 'utf-8', delay=0
        )
    except (IOError, OSError):
        err = ('Failed to open log file, do you have permission to write to '
               '{0}'.format(log_path))
        sys.stderr.write('{0}\n'.format(err))
        sys.exit(2)

    handler.setLevel(level)

    # Set the default console formatter config
    if not log_format:
        log_format = '%(asctime)s [%(name)-15s][%(levelname)-8s] %(message)s'
    if not date_format:
        date_format = '%H:%M:%S'

    formatter = logging.Formatter(log_format, datefmt=date_format)

    handler.setFormatter(formatter)
    rootLogger.addHandler(handler)

    global __LOGFILE_CONFIGURED
    __LOGFILE_CONFIGURED = True


def set_logger_level(logger_name, log_level='error'):
    '''
    Tweak a specific logger's logging level
    '''
    init()
    logging.getLogger(logger_name).setLevel(
        LOG_LEVELS.get(log_level.lower(), logging.ERROR)
    )
