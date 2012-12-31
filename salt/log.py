# -*- coding: utf-8 -*-
'''
    salt.log
    ~~~~~~~~

    This is where Salt's logging gets set up.


    :copyright: 2011-2012 :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import python libs
import os
import re
import sys
import socket
import urlparse
import logging
import logging.handlers

TRACE = logging.TRACE = 5
GARBAGE = logging.GARBAGE = 1

LOG_LEVELS = {
    'all': logging.NOTSET,
    'debug': logging.DEBUG,
    'error': logging.ERROR,
    'garbage': GARBAGE,
    'info': logging.INFO,
    'quiet': 1000,
    'trace': TRACE,
    'warning': logging.WARNING,
}

# Make a list of log level names sorted by log level
SORTED_LEVEL_NAMES = [
    l[0] for l in sorted(LOG_LEVELS.iteritems(), key=lambda x: x[1])
]

# Store an instance of the current logging logger class
LoggingLoggerClass = logging.getLoggerClass()

MODNAME_PATTERN = re.compile(r'(?P<name>%%\(name\)(?:\-(?P<digits>[\d]+))?s)')

__CONSOLE_CONFIGURED = False
__LOGFILE_CONFIGURED = False


def is_console_configured():
    global __CONSOLE_CONFIGURED
    return __CONSOLE_CONFIGURED


def is_logfile_configured():
    global __LOGFILE_CONFIGURED
    return __LOGFILE_CONFIGURED


def is_logging_configured():
    global __CONSOLE_CONFIGURED, __LOGFILE_CONFIGURED
    return __CONSOLE_CONFIGURED or __LOGFILE_CONFIGURED


if sys.version_info < (2, 7):
    # Since the NullHandler is only available on python >= 2.7, here's a copy
    class NullHandler(logging.Handler):
        """ This is 1 to 1 copy of python's 2.7 NullHandler"""
        def handle(self, record):
            pass

        def emit(self, record):
            pass

        def createLock(self):
            self.lock = None

    logging.NullHandler = NullHandler


# Store a reference to the null logging handler
LoggingNullHandler = logging.NullHandler()


class Logging(LoggingLoggerClass):
    def __new__(cls, logger_name, *args, **kwargs):
        # This makes module name padding increase to the biggest module name
        # so that logs keep readability.
        #
        # This code will only run when a new logger is created, ie:
        #
        #    logging.getLogger(__name__)
        #
        instance = super(Logging, cls).__new__(cls)

        try:
            max_logger_length = len(max(
                logging.Logger.manager.loggerDict.keys(), key=len
            ))
            for handler in logging.getLogger().handlers:
                if handler is LoggingNullHandler:
                    continue

                if not handler.lock:
                    handler.createLock()
                handler.acquire()

                formatter = handler.formatter
                fmt = formatter._fmt.replace('%', '%%')

                match = MODNAME_PATTERN.search(fmt)
                if not match:
                    # Not matched. Release handler and return.
                    handler.release()
                    return instance

                if 'digits' not in match.groupdict():
                    # No digits group. Release handler and return.
                    handler.release()
                    return instance

                digits = match.group('digits')
                if not digits or not (digits and digits.isdigit()):
                    # No valid digits. Release handler and return.
                    handler.release()
                    return instance

                if int(digits) < max_logger_length:
                    # Formatter digits value is lower than current max, update.
                    fmt = fmt.replace(match.group('name'), '%%(name)-%ds')
                    formatter = logging.Formatter(
                        fmt % max_logger_length,
                        datefmt=formatter.datefmt
                    )
                    handler.setFormatter(formatter)
                handler.release()
        except ValueError:
            # There are no registered loggers yet
            pass
        return instance

    def makeRecord(self, name, level, fn, lno, msg, args, exc_info, func=None,
                   extra=None):
        # Let's try to make every logging message unicode
        if isinstance(msg, basestring) and not isinstance(msg, unicode):
            try:
                return LoggingLoggerClass.makeRecord(
                    self, name, level, fn, lno,
                    msg.decode('utf-8', 'replace'),
                    args, exc_info, func, extra
                )
            except UnicodeDecodeError:
                return LoggingLoggerClass.makeRecord(
                    self, name, level, fn, lno,
                    msg.decode('utf-8', 'ignore'),
                    args, exc_info, func, extra
                )
        return LoggingLoggerClass.makeRecord(
            self, name, level, fn, lno, msg, args, exc_info, func, extra
        )

    def garbage(self, msg, *args, **kwargs):
        return LoggingLoggerClass.log(self, GARBAGE, msg, *args, **kwargs)

    def trace(self, msg, *args, **kwargs):
        return LoggingLoggerClass.log(self, TRACE, msg, *args, **kwargs)


# Override the python's logging logger class as soon as this module is imported
if logging.getLoggerClass() is not Logging:
    '''
    Replace the default system logger with a version that includes trace()
    and garbage() methods.
    '''
    logging.setLoggerClass(Logging)
    logging.addLevelName(TRACE, 'TRACE')
    logging.addLevelName(GARBAGE, 'GARBAGE')
    # Set the root logger at the lowest level possible
    rootLogger = logging.getLogger()
    # Add a Null logging handler until logging is configured(will be removed at
    # a later stage) so we stop getting:
    #   No handlers could be found for logger "foo"
    rootLogger.addHandler(LoggingNullHandler)
    rootLogger.setLevel(GARBAGE)


def getLogger(name):
    return logging.getLogger(name)


def setup_console_logger(log_level='error', log_format=None, date_format=None):
    '''
    Setup the console logger
    '''
    if is_console_configured():
        logging.getLogger(__name__).warn('Console logging already configured')
        return

    # Remove the temporary null logging handler
    __remove_null_logging_handler()

    if log_level is None:
        log_level = 'warning'

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

    Since version 0.10.6 we support logging to syslog, some examples:

        tcp://localhost:514/LOG_USER
        tcp://localhost/LOG_DAEMON
        udp://localhost:5145/LOG_KERN
        udp://localhost
        file:///dev/log
        file:///dev/log/LOG_SYSLOG
        file:///dev/log/LOG_DAEMON

    The above examples are self explanatory, but:
        <file|udp|tcp>://<host|socketpath>:<port-if-required>/<log-facility>

    '''

    if is_logfile_configured():
        logging.getLogger(__name__).warn('Logfile logging already configured')
        return

    # Remove the temporary null logging handler
    __remove_null_logging_handler()

    if log_level is None:
        log_level = 'warning'

    level = LOG_LEVELS.get(log_level.lower(), logging.ERROR)

    parsed_log_path = urlparse.urlparse(log_path)

    rootLogger = logging.getLogger()

    if parsed_log_path.scheme in ('tcp', 'udp', 'file'):
        syslog_opts = {
            'facility': logging.handlers.SysLogHandler.LOG_USER,
            'socktype': socket.SOCK_DGRAM

        }

        if parsed_log_path.scheme == 'file' and parsed_log_path.path:
            facility_name = parsed_log_path.path.split(os.sep)[-1].upper()
            if not facility_name.startswith('LOG_'):
                # The user is not specifying a syslog facility
                facility_name = 'LOG_USER'      # Syslog default
                syslog_opts['address'] = parsed_log_path.path
            else:
                # The user has set a syslog facility, let's update the path to
                # the logging socket
                syslog_opts['address'] = os.sep.join(
                    parsed_log_path.path.split(os.sep)[:-1]
                )
        elif parsed_log_path.path:
            # In case of udp or tcp with a facility specified
            facility_name = parsed_log_path.path.lstrip(os.sep).upper()
            if not facility_name.startswith('LOG_'):
                # Logging facilities start with LOG_ if this is not the case
                # fail right now!
                raise RuntimeError(
                    'The syslog facility {0!r} is not know'.format(
                        facility_name
                    )
                )
        else:
            # This is the case of udp or tcp without a facility specified
            facility_name = 'LOG_USER'      # Syslog default

        facility = getattr(
            logging.handlers.SysLogHandler, facility_name, None
        )
        if facility is None:
            # This python syslog version does not know about the user provided
            # facility name
            raise RuntimeError(
                'The syslog facility {0!r} is not know'.format(
                    facility_name
                )
            )
        syslog_opts['facility'] = facility

        if parsed_log_path.scheme == 'tcp':
            # tcp syslog support was only added on python versions >= 2.7
            if sys.version_info < (2, 7):
                raise RuntimeError(
                    'Python versions lower than 2.7 do not support logging '
                    'to syslog using tcp sockets'
                )
            syslog_opts['socktype'] = socket.SOCK_STREAM

        if parsed_log_path.scheme in ('tcp', 'udp'):
            syslog_opts['address'] = (
                parsed_log_path.hostname,
                parsed_log_path.port or logging.handlers.SYSLOG_UDP_PORT
            )

        if sys.version_info < (2, 7) or parsed_log_path.scheme == 'file':
            # There's not socktype support on python versions lower than 2.7
            syslog_opts.pop('socktype', None)

        # Et voilá! Finally our syslog handler instance
        handler = logging.handlers.SysLogHandler(**syslog_opts)
    else:
        try:
            # Logfile logging is UTF-8 on purpose.
            # Since salt uses yaml and yaml uses either UTF-8 or UTF-16, if a
            # user is not using plain ascii, he's system should be ready to
            # handle UTF-8.
            handler = getattr(
                logging.handlers, 'WatchedFileHandler', logging.FileHandler
            )(log_path, mode='a', encoding='utf-8', delay=0)
        except (IOError, OSError):
            sys.stderr.write(
                'Failed to open log file, do you have permission to write to '
                '{0}\n'.format(log_path)
            )
            sys.exit(2)

    handler.setLevel(level)

    # Set the default console formatter config
    if not log_format:
        log_format = '%(asctime)s [%(name)-15s][%(levelname)-8s] %(message)s'
    if not date_format:
        date_format = '%Y-%m-%d %H:%M:%S'

    formatter = logging.Formatter(log_format, datefmt=date_format)

    handler.setFormatter(formatter)
    rootLogger.addHandler(handler)

    global __LOGFILE_CONFIGURED
    __LOGFILE_CONFIGURED = True


def set_logger_level(logger_name, log_level='error'):
    '''
    Tweak a specific logger's logging level
    '''
    logging.getLogger(logger_name).setLevel(
        LOG_LEVELS.get(log_level.lower(), logging.ERROR)
    )


def __remove_null_logging_handler():
    if is_logfile_configured():
        # In this case, the NullHandler has been removed, return!
        return

    rootLogger = logging.getLogger()
    global LoggingNullHandler

    for handler in rootLogger.handlers:
        if handler is LoggingNullHandler:
            rootLogger.removeHandler(LoggingNullHandler)
            # Redefine the null handler to None so it can be garbage collected
            LoggingNullHandler = None
            break
