# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    salt.log.setup
    ~~~~~~~~~~~~~~

    This is where Salt's logging gets set up.

    This module should be imported as soon as possible, preferably the first
    module salt or any salt depending library imports so any new logging
    logger instance uses our ``salt.log.setup.SaltLoggingClass``.
'''

# Import python libs
from __future__ import absolute_import
import os
import re
import sys
import types
import socket
import logging
import logging.handlers
import traceback

# Import 3rd-party libs
import salt.ext.six as six
from salt.ext.six.moves.urllib.parse import urlparse  # pylint: disable=import-error,no-name-in-module

# Let's define these custom logging levels before importing the salt.log.mixins
# since they will be used there
PROFILE = logging.PROFILE = 15
TRACE = logging.TRACE = 5
GARBAGE = logging.GARBAGE = 1
QUIET = logging.QUIET = 1000

# Import salt libs
from salt.textformat import TextFormat
from salt.log.handlers import TemporaryLoggingHandler, StreamHandler, SysLogHandler, WatchedFileHandler
from salt.log.mixins import LoggingMixInMeta, NewStyleClassMixIn


LOG_LEVELS = {
    'all': logging.NOTSET,
    'debug': logging.DEBUG,
    'error': logging.ERROR,
    'critical': logging.CRITICAL,
    'garbage': GARBAGE,
    'info': logging.INFO,
    'profile': PROFILE,
    'quiet': QUIET,
    'trace': TRACE,
    'warning': logging.WARNING,
}


LOG_COLORS = {
    'levels': {
        'QUIET': TextFormat('reset'),
        'CRITICAL': TextFormat('bold', 'red'),
        'ERROR': TextFormat('bold', 'red'),
        'WARNING': TextFormat('bold', 'yellow'),
        'INFO': TextFormat('bold', 'green'),
        'PROFILE': TextFormat('bold', 'cyan'),
        'DEBUG': TextFormat('bold', 'cyan'),
        'TRACE': TextFormat('bold', 'magenta'),
        'GARBAGE': TextFormat('bold', 'blue'),
        'NOTSET': TextFormat('reset'),
    },
    'msgs': {
        'QUIET': TextFormat('reset'),
        'CRITICAL': TextFormat('bold', 'red'),
        'ERROR': TextFormat('red'),
        'WARNING': TextFormat('yellow'),
        'INFO': TextFormat('green'),
        'PROFILE': TextFormat('bold', 'cyan'),
        'DEBUG': TextFormat('cyan'),
        'TRACE': TextFormat('magenta'),
        'GARBAGE': TextFormat('blue'),
        'NOTSET': TextFormat('reset'),
    },
    'name': TextFormat('bold', 'green'),
    'process': TextFormat('bold', 'blue'),
}


# Make a list of log level names sorted by log level
SORTED_LEVEL_NAMES = [
    l[0] for l in sorted(six.iteritems(LOG_LEVELS), key=lambda x: x[1])
]

# Store an instance of the current logging logger class
LOGGING_LOGGER_CLASS = logging.getLoggerClass()

MODNAME_PATTERN = re.compile(r'(?P<name>%%\(name\)(?:\-(?P<digits>[\d]+))?s)')

__CONSOLE_CONFIGURED = False
__LOGFILE_CONFIGURED = False
__TEMP_LOGGING_CONFIGURED = False
__EXTERNAL_LOGGERS_CONFIGURED = False


def is_console_configured():
    return __CONSOLE_CONFIGURED


def is_logfile_configured():
    return __LOGFILE_CONFIGURED


def is_logging_configured():
    return __CONSOLE_CONFIGURED or __LOGFILE_CONFIGURED


def is_temp_logging_configured():
    return __TEMP_LOGGING_CONFIGURED


def is_extended_logging_configured():
    return __EXTERNAL_LOGGERS_CONFIGURED


# Store a reference to the temporary queue logging handler
LOGGING_NULL_HANDLER = TemporaryLoggingHandler(logging.WARNING)

# Store a reference to the temporary console logger
LOGGING_TEMP_HANDLER = StreamHandler(sys.stderr)

# Store a reference to the "storing" logging handler
LOGGING_STORE_HANDLER = TemporaryLoggingHandler()


class SaltLogRecord(logging.LogRecord):
    def __init__(self, *args, **kwargs):
        logging.LogRecord.__init__(self, *args, **kwargs)
        # pylint: disable=E1321
        self.bracketname = '[%-17s]' % self.name
        self.bracketlevel = '[%-8s]' % self.levelname
        self.bracketprocess = '[%5s]' % self.process
        # pylint: enable=E1321


class SaltColorLogRecord(SaltLogRecord):
    def __init__(self, *args, **kwargs):
        SaltLogRecord.__init__(self, *args, **kwargs)

        reset = TextFormat('reset')
        clevel = LOG_COLORS['levels'].get(self.levelname, reset)
        cmsg = LOG_COLORS['msgs'].get(self.levelname, reset)

        # pylint: disable=E1321
        self.colorname = '%s[%-17s]%s' % (LOG_COLORS['name'],
                                          self.name,
                                          reset)
        self.colorlevel = '%s[%-8s]%s' % (clevel,
                                          self.levelname,
                                          TextFormat('reset'))
        self.colorprocess = '%s[%5s]%s' % (LOG_COLORS['process'],
                                           self.process,
                                           reset)
        self.colormsg = '%s%s%s' % (cmsg, self.getMessage(), reset)
        # pylint: enable=E1321


_log_record_factory = SaltLogRecord


def set_log_record_factory(factory):
    '''
    Set the factory to be used when instantiating a log record.

    :param factory: A callable which will be called to instantiate
    a log record.
    '''
    global _log_record_factory
    _log_record_factory = factory


def get_log_record_factory():
    '''
    Return the factory to be used when instantiating a log record.
    '''

    return _log_record_factory


set_log_record_factory(SaltLogRecord)


class SaltLoggingClass(six.with_metaclass(LoggingMixInMeta, LOGGING_LOGGER_CLASS, NewStyleClassMixIn)):
    def __new__(cls, *args):  # pylint: disable=W0613, E1002
        '''
        We override `__new__` in our logging logger class in order to provide
        some additional features like expand the module name padding if length
        is being used, and also some Unicode fixes.

        This code overhead will only be executed when the class is
        instantiated, i.e.:

            logging.getLogger(__name__)

        '''
        instance = super(SaltLoggingClass, cls).__new__(cls)

        try:
            max_logger_length = len(max(
                list(logging.Logger.manager.loggerDict.keys()), key=len
            ))
            for handler in logging.root.handlers:
                if handler in (LOGGING_NULL_HANDLER,
                               LOGGING_STORE_HANDLER,
                               LOGGING_TEMP_HANDLER):
                    continue

                formatter = handler.formatter
                if not formatter:
                    continue

                if not handler.lock:
                    handler.createLock()
                handler.acquire()

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

    def _log(self, level, msg, args, exc_info=None, extra=None,  # pylint: disable=arguments-differ
             exc_info_on_loglevel=None):
        # If both exc_info and exc_info_on_loglevel are both passed, let's fail.
        if exc_info and exc_info_on_loglevel:
            raise RuntimeError(
                'Please only use one of \'exc_info\' and \'exc_info_on_loglevel\', not both'
            )
        if exc_info_on_loglevel is not None:
            if isinstance(exc_info_on_loglevel, six.string_types):
                exc_info_on_loglevel = LOG_LEVELS.get(exc_info_on_loglevel, logging.ERROR)
            elif not isinstance(exc_info_on_loglevel, int):
                raise RuntimeError(
                    'The value of \'exc_info_on_loglevel\' needs to be a logging level or '
                    'a logging level name, not {0!r}'.format(exc_info_on_loglevel)
                )
        if extra is None:
            extra = {'exc_info_on_loglevel': exc_info_on_loglevel}
        else:
            extra['exc_info_on_loglevel'] = exc_info_on_loglevel

        LOGGING_LOGGER_CLASS._log(
            self, level, msg, args, exc_info=exc_info, extra=extra
        )

    # pylint: disable=C0103
    # pylint: disable=W0221
    def makeRecord(self, name, level, fn, lno, msg, args, exc_info,
                   func=None, extra=None, sinfo=None):
        # Let's remove exc_info_on_loglevel from extra
        exc_info_on_loglevel = extra.pop('exc_info_on_loglevel')
        if not extra:
            # If nothing else is in extra, make it None
            extra = None

        # Let's try to make every logging message unicode
        if isinstance(msg, six.string_types) and not isinstance(msg, six.text_type):
            try:
                _msg = msg.decode('utf-8', 'replace')
            except UnicodeDecodeError:
                _msg = msg.decode('utf-8', 'ignore'),
        else:
            _msg = msg

        if six.PY3:
            logrecord = _log_record_factory(name, level, fn, lno, _msg, args,
                                          exc_info, func, sinfo)
        else:
            logrecord = _log_record_factory(name, level, fn, lno, _msg, args,
                                          exc_info, func)

        if extra is not None:
            for key in extra:
                if (key in ['message', 'asctime']) \
                        or (key in logrecord.__dict__):
                    raise KeyError(
                        'Attempt to overwrite {0!r} in LogRecord'.format(key)
                    )
                logrecord.__dict__[key] = extra[key]

        if exc_info_on_loglevel is not None:
            # Let's add some custom attributes to the LogRecord class in order
            # to include the exc_info on a per handler basis. This will allow
            # showing tracebacks on logfiles but not on console if the logfile
            # handler is enabled for the log level "exc_info_on_loglevel" and
            # console handler is not.
            logrecord.exc_info_on_loglevel_instance = sys.exc_info()
            logrecord.exc_info_on_loglevel_formatted = None

        logrecord.exc_info_on_loglevel = exc_info_on_loglevel
        return logrecord

    # pylint: enable=C0103


# Override the python's logging logger class as soon as this module is imported
if logging.getLoggerClass() is not SaltLoggingClass:

    logging.setLoggerClass(SaltLoggingClass)
    logging.addLevelName(QUIET, 'QUIET')
    logging.addLevelName(PROFILE, 'PROFILE')
    logging.addLevelName(TRACE, 'TRACE')
    logging.addLevelName(GARBAGE, 'GARBAGE')

    if len(logging.root.handlers) == 0:
        # No configuration to the logging system has been done so far.
        # Set the root logger at the lowest level possible
        logging.root.setLevel(GARBAGE)

        # Add a Null logging handler until logging is configured(will be
        # removed at a later stage) so we stop getting:
        #   No handlers could be found for logger 'foo'
        logging.root.addHandler(LOGGING_NULL_HANDLER)

    # Add the queue logging handler so we can later sync all message records
    # with the additional logging handlers
    logging.root.addHandler(LOGGING_STORE_HANDLER)


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

    if log_level is None:
        log_level = 'warning'

    level = LOG_LEVELS.get(log_level.lower(), logging.ERROR)

    handler = None
    for handler in logging.root.handlers:
        if handler in (LOGGING_NULL_HANDLER, LOGGING_STORE_HANDLER):
            continue

        if not hasattr(handler, 'stream'):
            # Not a stream handler, continue
            continue

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
    logging.root.addHandler(handler)

    # Sync the null logging handler messages with the temporary handler
    if LOGGING_NULL_HANDLER is not None:
        LOGGING_NULL_HANDLER.sync_with_handlers([handler])
    else:
        logging.getLogger(__name__).debug(
            'LOGGING_NULL_HANDLER is already None, can\'t sync messages '
            'with it'
        )

    # Remove the temporary null logging handler
    __remove_null_logging_handler()

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

    set_log_record_factory(SaltColorLogRecord)

    handler = None
    for handler in logging.root.handlers:
        if handler is LOGGING_STORE_HANDLER:
            continue

        if not hasattr(handler, 'stream'):
            # Not a stream handler, continue
            continue

        if handler.stream is sys.stderr:
            # There's already a logging handler outputting to sys.stderr
            break
    else:
        handler = StreamHandler(sys.stderr)
    handler.setLevel(level)

    # Set the default console formatter config
    if not log_format:
        log_format = '[%(levelname)-8s] %(message)s'
    if not date_format:
        date_format = '%H:%M:%S'

    formatter = logging.Formatter(log_format, datefmt=date_format)

    handler.setFormatter(formatter)
    logging.root.addHandler(handler)

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

    parsed_log_path = urlparse(log_path)

    root_logger = logging.getLogger()

    if parsed_log_path.scheme in ('tcp', 'udp', 'file'):
        syslog_opts = {
            'facility': SysLogHandler.LOG_USER,
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
                    'The syslog facility {0!r} is not known'.format(
                        facility_name
                    )
                )
        else:
            # This is the case of udp or tcp without a facility specified
            facility_name = 'LOG_USER'      # Syslog default

        facility = getattr(
            SysLogHandler, facility_name, None
        )
        if facility is None:
            # This python syslog version does not know about the user provided
            # facility name
            raise RuntimeError(
                'The syslog facility {0!r} is not known'.format(
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
            handler = SysLogHandler(**syslog_opts)
        except socket.error as err:
            logging.getLogger(__name__).error(
                'Failed to setup the Syslog logging handler: {0}'.format(
                    err
                )
            )
            sys.exit(2)
    else:
        try:
            # Logfile logging is UTF-8 on purpose.
            # Since salt uses YAML and YAML uses either UTF-8 or UTF-16, if a
            # user is not using plain ASCII, their system should be ready to
            # handle UTF-8.
            handler = WatchedFileHandler(log_path, mode='a', encoding='utf-8', delay=0)
        except (IOError, OSError):
            logging.getLogger(__name__).warning(
                'Failed to open log file, do you have permission to write to '
                '{0}?'.format(log_path)
            )
            # Do not proceed with any more configuration since it will fail, we
            # have the console logging already setup and the user should see
            # the error.
            return

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


def setup_extended_logging(opts):
    '''
    Setup any additional logging handlers, internal or external
    '''
    if is_extended_logging_configured() is True:
        # Don't re-configure external loggers
        return

    # Explicit late import of salt's loader
    import salt.loader

    # Let's keep a reference to the current logging handlers
    initial_handlers = logging.root.handlers[:]

    # Load any additional logging handlers
    providers = salt.loader.log_handlers(opts)

    # Let's keep track of the new logging handlers so we can sync the stored
    # log records with them
    additional_handlers = []

    for name, get_handlers_func in six.iteritems(providers):
        logging.getLogger(__name__).info(
            'Processing `log_handlers.{0}`'.format(name)
        )
        # Keep a reference to the logging handlers count before getting the
        # possible additional ones.
        initial_handlers_count = len(logging.root.handlers)

        handlers = get_handlers_func()
        if isinstance(handlers, types.GeneratorType):
            handlers = list(handlers)
        elif handlers is False or handlers == [False]:
            # A false return value means not configuring any logging handler on
            # purpose
            logging.getLogger(__name__).info(
                'The `log_handlers.{0}.setup_handlers()` function returned '
                '`False` which means no logging handler was configured on '
                'purpose. Continuing...'.format(name)
            )
            continue
        else:
            # Make sure we have an iterable
            handlers = [handlers]

        for handler in handlers:
            if not handler and \
                    len(logging.root.handlers) == initial_handlers_count:
                logging.getLogger(__name__).info(
                    'The `log_handlers.{0}`, did not return any handlers '
                    'and the global handlers count did not increase. This '
                    'could be a sign of `log_handlers.{0}` not working as '
                    'supposed'.format(name)
                )
                continue

            logging.getLogger(__name__).debug(
                'Adding the {0!r} provided logging handler: {1!r}'.format(
                    name, handler
                )
            )
            additional_handlers.append(handler)
            logging.root.addHandler(handler)

    for handler in logging.root.handlers:
        if handler in initial_handlers:
            continue
        additional_handlers.append(handler)

    # Sync the null logging handler messages with the temporary handler
    if LOGGING_STORE_HANDLER is not None:
        LOGGING_STORE_HANDLER.sync_with_handlers(additional_handlers)
    else:
        logging.getLogger(__name__).debug(
            'LOGGING_STORE_HANDLER is already None, can\'t sync messages '
            'with it'
        )

    # Remove the temporary queue logging handler
    __remove_queue_logging_handler()

    global __EXTERNAL_LOGGERS_CONFIGURED
    __EXTERNAL_LOGGERS_CONFIGURED = True


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


def __remove_queue_logging_handler():
    '''
    This function will run once the additional loggers have been synchronized.
    It just removes the QueueLoggingHandler from the logging handlers.
    '''
    root_logger = logging.getLogger()
    global LOGGING_STORE_HANDLER

    for handler in root_logger.handlers:
        if handler is LOGGING_STORE_HANDLER:
            root_logger.removeHandler(LOGGING_STORE_HANDLER)
            # Redefine the null handler to None so it can be garbage collected
            LOGGING_STORE_HANDLER = None
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


def __global_logging_exception_handler(exc_type, exc_value, exc_traceback):
    '''
    This function will log all python exceptions.
    '''
    # Do not log the exception or display the traceback on Keyboard Interrupt
    if exc_type.__name__ != "KeyboardInterrupt":
        # Log the exception
        logging.getLogger(__name__).error(
            'An un-handled exception was caught by salt\'s global exception '
            'handler:\n{0}: {1}\n{2}'.format(
                exc_type.__name__,
                exc_value,
                ''.join(traceback.format_exception(
                    exc_type, exc_value, exc_traceback
                )).strip()
            )
        )
        # Call the original sys.excepthook
        sys.__excepthook__(exc_type, exc_value, exc_traceback)


# Set our own exception handler as the one to use
sys.excepthook = __global_logging_exception_handler
