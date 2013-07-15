# -*- coding: utf-8 -*-
'''
    salt.log
    ~~~~~~~~

    This is where Salt's logging gets set up.

    This module should be imported as soon as possible, preferably the first
    module salt or any salt depending library imports so any new logging
    logger instance uses our ``salt.log.SaltLoggingClass``.


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
LOGGING_LOGGER_CLASS = logging.getLoggerClass()

MODNAME_PATTERN = re.compile(r'(?P<name>%%\(name\)(?:\-(?P<digits>[\d]+))?s)')

__CONSOLE_CONFIGURED = False
__LOGFILE_CONFIGURED = False
__TEMP_LOGGING_CONFIGURED = False


def is_console_configured():
    return __CONSOLE_CONFIGURED


def is_logfile_configured():
    return __LOGFILE_CONFIGURED


def is_logging_configured():
    return __CONSOLE_CONFIGURED or __LOGFILE_CONFIGURED


def is_temp_logging_configured():
    return __TEMP_LOGGING_CONFIGURED


if sys.version_info < (2, 7):
    # Since the NullHandler is only available on python >= 2.7, here's a copy
    class NullHandler(logging.Handler):
        '''
        This is 1 to 1 copy of python's 2.7 NullHandler
        '''
        def handle(self, record):
            pass

        def emit(self, record):
            pass

        def createLock(self):  # pylint: disable=C0103
            self.lock = None

    logging.NullHandler = NullHandler


# Store a reference to the null logging handler
LOGGING_NULL_HANDLER = logging.NullHandler()

# Store a reference to the temporary console logger
LOGGING_TEMP_HANDLER = logging.StreamHandler(sys.stderr)


class LoggingTraceMixIn(object):
    '''
    Simple mix-in class to add a trace method to python's logging.
    '''

    def trace(self, msg, *args, **kwargs):
        self.log(TRACE, msg, *args, **kwargs)


class LoggingGarbageMixIn(object):
    '''
    Simple mix-in class to add a garbage method to python's logging.
    '''

    def garbage(self, msg, *args, **kwargs):
        self.log(GARBAGE, msg, *args, **kwargs)


class LoggingMixInMeta(type):
    '''
    This class is called whenever a new instance of ``SaltLoggingClass`` is
    created.

    What this class does is check if any of the bases have a `trace()` or a
    `garbage()` method defined, if they don't we add the respective mix-ins to
    the bases.
    '''
    def __new__(mcs, name, bases, attrs):
        include_trace = include_garbage = True
        bases = list(bases)
        if name == 'SaltLoggingClass':
            for base in bases:
                if hasattr(base, 'trace'):
                    include_trace = False
                if hasattr(base, 'garbage'):
                    include_garbage = False
        if include_trace:
            bases.append(LoggingTraceMixIn)
        if include_garbage:
            bases.append(LoggingGarbageMixIn)
        return super(LoggingMixInMeta, mcs).__new__(
            mcs, name, tuple(bases), attrs
        )


class _NewStyleClassMixIn(object):
    '''
    Simple new style class to make pylint shut up!
    This is required because SaltLoggingClass can't subclass object directly:

        'Cannot create a consistent method resolution order (MRO) for bases'
    '''


class SaltLoggingClass(LOGGING_LOGGER_CLASS, _NewStyleClassMixIn):
    __metaclass__ = LoggingMixInMeta

    def __new__(cls, *args):
        '''
        We override `__new__` in our logging logger class in order to provide
        some additional features like expand the module name padding if length
        is being used, and also some Unicode fixes.

        This code overhead will only be executed when the class is
        instantiated, ie:

            logging.getLogger(__name__)

        '''
        instance = super(SaltLoggingClass, cls).__new__(cls)

        try:
            max_logger_length = len(max(
                logging.Logger.manager.loggerDict.keys(), key=len
            ))
            for handler in logging.getLogger().handlers:
                if handler is LOGGING_NULL_HANDLER:
                    continue

                if not handler.lock:
                    handler.createLock()
                handler.acquire()

                formatter = handler.formatter
                if not formatter:
                    continue

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

    # pylint: disable=C0103
    def makeRecord(self, name, level, fn, lno, msg, args, exc_info, func=None,
                   extra=None):
        # Let's try to make every logging message unicode
        if isinstance(msg, basestring) and not isinstance(msg, unicode):
            try:
                return LOGGING_LOGGER_CLASS.makeRecord(
                    self, name, level, fn, lno,
                    msg.decode('utf-8', 'replace'),
                    args, exc_info, func, extra
                )
            except UnicodeDecodeError:
                return LOGGING_LOGGER_CLASS.makeRecord(
                    self, name, level, fn, lno,
                    msg.decode('utf-8', 'ignore'),
                    args, exc_info, func, extra
                )
        return LOGGING_LOGGER_CLASS.makeRecord(
            self, name, level, fn, lno, msg, args, exc_info, func, extra
        )
    # pylint: enable=C0103


# Override the python's logging logger class as soon as this module is imported
if logging.getLoggerClass() is not SaltLoggingClass:

    logging.setLoggerClass(SaltLoggingClass)
    logging.addLevelName(TRACE, 'TRACE')
    logging.addLevelName(GARBAGE, 'GARBAGE')

    if len(logging.root.handlers) == 0:
        # No configuration to the logging system has been done so far.
        # Set the root logger at the lowest level possible
        logging.getLogger().setLevel(GARBAGE)

        # Add a Null logging handler until logging is configured(will be
        # removed at a later stage) so we stop getting:
        #   No handlers could be found for logger 'foo'
        logging.getLogger().addHandler(LOGGING_NULL_HANDLER)


def getLogger(name):  # pylint: disable=C0103
    '''
    This function is just a helper, an alias to:
        logging.getLogger(name)

    Although you might find it useful, there's no reason why you should not be
    using the aliased method.
    '''
    return logging.getLogger(name)


def setup_temp_logger(log_level='error'):
    '''
    Setup the temporary console logger
    '''
    if is_temp_logging_configured():
        logging.getLogger(__name__).warn(
            'Temporary logging is already configured'
        )
        return

    # Remove the temporary null logging handler
    __remove_null_logging_handler()

    if log_level is None:
        log_level = 'warning'

    level = LOG_LEVELS.get(log_level.lower(), logging.ERROR)

    handler = None
    for handler in logging.root.handlers:
        if handler.stream is sys.stderr:
            # There's already a logging handler outputting to sys.stderr
            break
    else:
        handler = LOGGING_TEMP_HANDLER
    handler.setLevel(level)

    # Set the default temporary console formatter config
    formatter = logging.Formatter(
        '[%(levelname)-8s] %(message)s', datefmt='%H:%M:%S'
    )
    handler.setFormatter(formatter)
    logging.getLogger().addHandler(handler)

    global __TEMP_LOGGING_CONFIGURED
    __TEMP_LOGGING_CONFIGURED = True


def setup_console_logger(log_level='error', log_format=None, date_format=None):
    '''
    Setup the console logger
    '''
    if is_console_configured():
        logging.getLogger(__name__).warn('Console logging already configured')
        return

    # Remove the temporary logging handler
    __remove_temp_logging_handler()

    if log_level is None:
        log_level = 'warning'

    level = LOG_LEVELS.get(log_level.lower(), logging.ERROR)

    handler = None
    for handler in logging.root.handlers:
        if handler.stream is sys.stderr:
            # There's already a logging handler outputting to sys.stderr
            break
    else:
        handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)

    # Set the default console formatter config
    if not log_format:
        log_format = '[%(levelname)-8s] %(message)s'
    if not date_format:
        date_format = '%H:%M:%S'

    formatter = logging.Formatter(log_format, datefmt=date_format)

    handler.setFormatter(formatter)
    logging.getLogger().addHandler(handler)

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

    If you're thinking on doing remote logging you might also be thinking that
    you could point salt's logging to the remote syslog. **Please Don't!**
    An issue has been reported when doing this over TCP when the logged lines
    get concatenated. See #3061.

    The preferred way to do remote logging is setup a local syslog, point
    salt's logging to the local syslog(unix socket is much faster) and then
    have the local syslog forward the log messages to the remote syslog.
    '''

    if is_logfile_configured():
        logging.getLogger(__name__).warn('Logfile logging already configured')
        return

    if log_path is None:
        logging.getLogger(__name__).warn(
            'log_path setting is set to `None`. Nothing else to do'
        )
        return

    # Remove the temporary logging handler
    __remove_temp_logging_handler()

    if log_level is None:
        log_level = 'warning'

    level = LOG_LEVELS.get(log_level.lower(), logging.ERROR)

    parsed_log_path = urlparse.urlparse(log_path)

    root_logger = logging.getLogger()

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

        try:
            # Et voilá! Finally our syslog handler instance
            handler = logging.handlers.SysLogHandler(**syslog_opts)
        except socket.error as err:
            logging.getLogger(__name__).error(
                'Failed to setup the Syslog logging handler: {0}'.format(
                    err
                )
            )
            # Do not proceed with any more configuration since it will fail, we
            # have the console logging already setup and the user should see
            # the error.
            return
    else:
        try:
            # Logfile logging is UTF-8 on purpose.
            # Since salt uses YAML and YAML uses either UTF-8 or UTF-16, if a
            # user is not using plain ASCII, their system should be ready to
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
    root_logger.addHandler(handler)

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
    '''
    This function will run once the temporary logging has been configured. It
    just removes the NullHandler from the logging handlers.
    '''
    if is_temp_logging_configured():
        # In this case, the NullHandler has been removed, return!
        return

    root_logger = logging.getLogger()
    global LOGGING_NULL_HANDLER

    for handler in root_logger.handlers:
        if handler is LOGGING_NULL_HANDLER:
            root_logger.removeHandler(LOGGING_NULL_HANDLER)
            # Redefine the null handler to None so it can be garbage collected
            LOGGING_NULL_HANDLER = None
            break


def __remove_temp_logging_handler():
    '''
    This function will run once logging has been configured. It just removes
    the temporary stream Handler from the logging handlers.
    '''
    if is_logging_configured():
        # In this case, the temporary logging handler has been removed, return!
        return

    # This should already be done, but...
    __remove_null_logging_handler()

    root_logger = logging.getLogger()
    global LOGGING_TEMP_HANDLER

    for handler in root_logger.handlers:
        if handler is LOGGING_TEMP_HANDLER:
            root_logger.removeHandler(LOGGING_TEMP_HANDLER)
            # Redefine the null handler to None so it can be garbage collected
            LOGGING_TEMP_HANDLER = None
            break

    if sys.version_info >= (2, 7):
        # Python versions >= 2.7 allow warnings to be redirected to the logging
        # system now that it's configured. Let's enable it.
        logging.captureWarnings(True)
