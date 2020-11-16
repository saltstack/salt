"""
    salt._logging.impl
    ~~~~~~~~~~~~~~~~~~

    Salt's logging implementation classes/functionality
"""


import atexit
import logging
import multiprocessing
import os
import re
import signal
import socket
import sys
import traceback
import types
import urllib.parse

# Let's define these custom logging levels before importing the salt._logging.mixins
# since they will be used there
PROFILE = logging.PROFILE = 15
TRACE = logging.TRACE = 5
GARBAGE = logging.GARBAGE = 1
QUIET = logging.QUIET = 1000

from salt._logging.handlers import DeferredStreamHandler  # isort:skip
from salt._logging.handlers import RotatingFileHandler  # isort:skip
from salt._logging.handlers import StreamHandler  # isort:skip
from salt._logging.handlers import SysLogHandler  # isort:skip
from salt._logging.handlers import TemporaryLoggingHandler  # isort:skip
from salt._logging.handlers import WatchedFileHandler  # isort:skip
from salt._logging.handlers import ZMQHandler  # isort:skip
from salt._logging.mixins import LoggingMixinMeta  # isort:skip
from salt._logging.mixins import NewStyleClassMixin  # isort:skip
from salt.exceptions import LoggingRuntimeError  # isort:skip
from salt.utils.ctx import RequestContext  # isort:skip
from salt.utils.textformat import TextFormat  # isort:skip


try:
    import msgpack

    HAS_MSGPACK = True
except ImportError:
    HAS_MSGPACK = False

try:
    import zmq

    HAS_ZMQ = True
except ImportError:
    HAS_ZMQ = False

LOG_LEVELS = {
    "all": logging.NOTSET,
    "debug": logging.DEBUG,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
    "garbage": GARBAGE,
    "info": logging.INFO,
    "profile": PROFILE,
    "quiet": QUIET,
    "trace": TRACE,
    "warning": logging.WARNING,
}

LOG_VALUES_TO_LEVELS = {v: k for (k, v) in LOG_LEVELS.items()}

LOG_COLORS = {
    "levels": {
        "QUIET": TextFormat("reset"),
        "CRITICAL": TextFormat("bold", "red"),
        "ERROR": TextFormat("bold", "red"),
        "WARNING": TextFormat("bold", "yellow"),
        "INFO": TextFormat("bold", "green"),
        "PROFILE": TextFormat("bold", "cyan"),
        "DEBUG": TextFormat("bold", "cyan"),
        "TRACE": TextFormat("bold", "magenta"),
        "GARBAGE": TextFormat("bold", "blue"),
        "NOTSET": TextFormat("reset"),
        "SUBDEBUG": TextFormat(
            "bold", "cyan"
        ),  # used by multiprocessing.log_to_stderr()
        "SUBWARNING": TextFormat(
            "bold", "yellow"
        ),  # used by multiprocessing.log_to_stderr()
    },
    "msgs": {
        "QUIET": TextFormat("reset"),
        "CRITICAL": TextFormat("bold", "red"),
        "ERROR": TextFormat("red"),
        "WARNING": TextFormat("yellow"),
        "INFO": TextFormat("green"),
        "PROFILE": TextFormat("bold", "cyan"),
        "DEBUG": TextFormat("cyan"),
        "TRACE": TextFormat("magenta"),
        "GARBAGE": TextFormat("blue"),
        "NOTSET": TextFormat("reset"),
        "SUBDEBUG": TextFormat(
            "bold", "cyan"
        ),  # used by multiprocessing.log_to_stderr()
        "SUBWARNING": TextFormat(
            "bold", "yellow"
        ),  # used by multiprocessing.log_to_stderr()
    },
    "name": TextFormat("bold", "green"),
    "process": TextFormat("bold", "blue"),
}

# Make a list of log level names sorted by log level
SORTED_LEVEL_NAMES = [l[0] for l in sorted(LOG_LEVELS.items(), key=lambda x: x[1])]

MODNAME_PATTERN = re.compile(r"(?P<name>%%\(name\)(?:\-(?P<digits>[\d]+))?s)")


# ----- REMOVE ME ON REFACTOR COMPLETE ------------------------------------------------------------------------------>
class __NullLoggingHandler(TemporaryLoggingHandler):
    """
    This class exists just to better identify which temporary logging
    handler is being used for what.
    """


class __StoreLoggingHandler(TemporaryLoggingHandler):
    """
    This class exists just to better identify which temporary logging
    handler is being used for what.
    """


# Store a reference to the temporary queue logging handler
LOGGING_NULL_HANDLER = __NullLoggingHandler(logging.WARNING)

# Store a reference to the temporary console logger
LOGGING_TEMP_HANDLER = StreamHandler(sys.stderr)

# Store a reference to the "storing" logging handler
LOGGING_STORE_HANDLER = __StoreLoggingHandler()
# <---- REMOVE ME ON REFACTOR COMPLETE -------------------------------------------------------------------------------


class SaltLogRecord(logging.LogRecord):
    def __init__(self, *args, **kwargs):
        logging.LogRecord.__init__(self, *args, **kwargs)
        self.bracketname = "[{:<17}]".format(str(self.name))
        self.bracketlevel = "[{:<8}]".format(str(self.levelname))
        self.bracketprocess = "[{:>5}]".format(str(self.process))


class SaltColorLogRecord(SaltLogRecord):
    def __init__(self, *args, **kwargs):
        SaltLogRecord.__init__(self, *args, **kwargs)

        reset = TextFormat("reset")
        clevel = LOG_COLORS["levels"].get(self.levelname, reset)
        cmsg = LOG_COLORS["msgs"].get(self.levelname, reset)

        self.colorname = "{}[{:<17}]{}".format(
            LOG_COLORS["name"], str(self.name), reset
        )
        self.colorlevel = "{}[{:<8}]{}".format(clevel, str(self.levelname), reset)
        self.colorprocess = "{}[{:>5}]{}".format(
            LOG_COLORS["process"], str(self.process), reset
        )
        self.colormsg = "{}{}{}".format(cmsg, self.getMessage(), reset)


def get_log_record_factory():
    """
    Get the logging  log record factory
    """
    try:
        return get_log_record_factory.__factory__
    except AttributeError:
        return


def set_log_record_factory(factory):
    """
    Set the logging  log record factory
    """
    get_log_record_factory.__factory__ = factory
    logging.setLogRecordFactory(factory)


set_log_record_factory(SaltLogRecord)


# Store an instance of the current logging logger class
LOGGING_LOGGER_CLASS = logging.getLoggerClass()


class SaltLoggingClass(
    LOGGING_LOGGER_CLASS, NewStyleClassMixin, metaclass=LoggingMixinMeta
):
    def __new__(cls, *args):
        """
        We override `__new__` in our logging logger class in order to provide
        some additional features like expand the module name padding if length
        is being used, and also some Unicode fixes.

        This code overhead will only be executed when the class is
        instantiated, i.e.:

            logging.getLogger(__name__)

        """
        instance = super().__new__(cls)

        try:
            max_logger_length = len(
                max(list(logging.Logger.manager.loggerDict), key=len)
            )
            if max_logger_length > 80:
                # Make sure the logger name on the formatted log record is not longer than 100 chars
                # Messages which need more that 100 chars will use them, but not ALL log messages
                max_logger_length = 80
            for handler in logging.root.handlers:
                if handler in (get_null_handler(), get_temp_handler()):
                    continue

                formatter = handler.formatter
                if not formatter:
                    continue

                if not handler.lock:
                    handler.createLock()
                handler.acquire()

                fmt = formatter._fmt.replace("%", "%%")

                match = MODNAME_PATTERN.search(fmt)
                if not match:
                    # Not matched. Release handler and return.
                    handler.release()
                    return instance

                if "digits" not in match.groupdict():
                    # No digits group. Release handler and return.
                    handler.release()
                    return instance

                digits = match.group("digits")
                if not digits or not (digits and digits.isdigit()):
                    # No valid digits. Release handler and return.
                    handler.release()
                    return instance

                if int(digits) < max_logger_length:
                    # Formatter digits value is lower than current max, update.
                    fmt = fmt.replace(match.group("name"), "%%(name)-%ds")
                    formatter = logging.Formatter(
                        fmt % max_logger_length, datefmt=formatter.datefmt
                    )
                    handler.setFormatter(formatter)
                handler.release()
        except ValueError:
            # There are no registered loggers yet
            pass
        return instance

    def _log(
        self,
        level,
        msg,
        args,
        exc_info=None,
        extra=None,  # pylint: disable=arguments-differ
        stack_info=False,
        stacklevel=1,
        exc_info_on_loglevel=None,
    ):
        if extra is None:
            extra = {}

        # pylint: disable=no-member
        current_jid = RequestContext.current.get("data", {}).get("jid", None)
        log_fmt_jid = RequestContext.current.get("opts", {}).get("log_fmt_jid", None)
        # pylint: enable=no-member

        if current_jid is not None:
            extra["jid"] = current_jid

        if log_fmt_jid is not None:
            extra["log_fmt_jid"] = log_fmt_jid

        # If both exc_info and exc_info_on_loglevel are both passed, let's fail
        if exc_info and exc_info_on_loglevel:
            raise LoggingRuntimeError(
                "Only one of 'exc_info' and 'exc_info_on_loglevel' is " "permitted"
            )
        if exc_info_on_loglevel is not None:
            if isinstance(exc_info_on_loglevel, str):
                exc_info_on_loglevel = LOG_LEVELS.get(
                    exc_info_on_loglevel, logging.ERROR
                )
            elif not isinstance(exc_info_on_loglevel, int):
                raise RuntimeError(
                    "The value of 'exc_info_on_loglevel' needs to be a "
                    "logging level or a logging level name, not '{}'".format(
                        exc_info_on_loglevel
                    )
                )
        if extra is None:
            extra = {"exc_info_on_loglevel": exc_info_on_loglevel}
        else:
            extra["exc_info_on_loglevel"] = exc_info_on_loglevel

        if sys.version_info < (3,):
            LOGGING_LOGGER_CLASS._log(
                self, level, msg, args, exc_info=exc_info, extra=extra
            )
        elif sys.version_info < (3, 8):
            LOGGING_LOGGER_CLASS._log(
                self,
                level,
                msg,
                args,
                exc_info=exc_info,
                extra=extra,
                stack_info=stack_info,
            )
        else:
            LOGGING_LOGGER_CLASS._log(
                self,
                level,
                msg,
                args,
                exc_info=exc_info,
                extra=extra,
                stack_info=stack_info,
                stacklevel=stacklevel,
            )

    def makeRecord(
        self,
        name,
        level,
        fn,
        lno,
        msg,
        args,
        exc_info,
        func=None,
        extra=None,
        sinfo=None,
    ):
        # Let's remove exc_info_on_loglevel from extra
        exc_info_on_loglevel = extra.pop("exc_info_on_loglevel")

        jid = extra.pop("jid", "")
        if jid:
            log_fmt_jid = extra.pop("log_fmt_jid")
            jid = log_fmt_jid % {"jid": jid}

        if not extra:
            # If nothing else is in extra, make it None
            extra = None

        # Let's try to make every logging message unicode
        try:
            salt_system_encoding = __salt_system_encoding__
            if salt_system_encoding == "ascii":
                # Encoding detection most likely failed, let's use the utf-8
                # value which we defaulted before __salt_system_encoding__ was
                # implemented
                salt_system_encoding = "utf-8"
        except NameError:
            salt_system_encoding = "utf-8"

        if isinstance(msg, bytes):
            try:
                _msg = msg.decode(salt_system_encoding, "replace")
            except UnicodeDecodeError:
                _msg = msg.decode(salt_system_encoding, "ignore")
        else:
            _msg = msg

        _args = []
        for item in args:
            if isinstance(item, bytes):
                try:
                    _args.append(item.decode(salt_system_encoding, "replace"))
                except UnicodeDecodeError:
                    _args.append(item.decode(salt_system_encoding, "ignore"))
            else:
                _args.append(item)
        _args = tuple(_args)

        logrecord = LOGGING_LOGGER_CLASS.makeRecord(
            self, name, level, fn, lno, _msg, _args, exc_info, func, sinfo
        )

        if exc_info_on_loglevel is not None:
            # Let's add some custom attributes to the LogRecord class in order
            # to include the exc_info on a per handler basis. This will allow
            # showing tracebacks on logfiles but not on console if the logfile
            # handler is enabled for the log level "exc_info_on_loglevel" and
            # console handler is not.
            logrecord.exc_info_on_loglevel_instance = sys.exc_info()
            logrecord.exc_info_on_loglevel_formatted = None

        logrecord.exc_info_on_loglevel = exc_info_on_loglevel
        logrecord.jid = jid
        return logrecord


def get_null_handler():
    """
    Return the permanent NullHandler instance.
    """
    try:
        return get_null_handler.__handler__
    except AttributeError:
        _handler = __NullLoggingHandler()
        get_null_handler.__handler__ = _handler
        return _handler


def is_temp_handler_configured():
    """
    Is the temporary deferred stream handler configured
    """
    return get_temp_handler() is not None


def get_temp_handler():
    """
    Get the temporary deferred stream handler
    """
    try:
        return setup_temp_handler.__handler__
    except AttributeError:
        return


def setup_temp_handler(log_level=None):
    """
    Setup the temporary deferred stream handler
    """
    if is_temp_handler_configured():
        log.warning("Temporary logging is already configured")
        return

    if log_level is None:
        log_level = logging.WARNING

    log_level = get_logging_level_from_string(log_level)

    handler = None
    for handler in logging.root.handlers:
        if handler is get_null_handler():
            continue

        if not hasattr(handler, "stream"):
            # Not a stream handler, continue
            continue

        if handler.stream is sys.stderr:
            # There's already a logging handler outputting to sys.stderr
            break
    else:
        handler = DeferredStreamHandler(sys.stderr)
        atexit.register(handler.flush)
    handler.setLevel(log_level)

    # Set the default temporary console formatter config
    import salt.config

    formatter = logging.Formatter(
        salt.config._DFLT_LOG_FMT_CONSOLE, datefmt=salt.config._DFLT_LOG_DATEFMT
    )
    handler.setFormatter(formatter)
    logging.root.addHandler(handler)

    setup_temp_handler.__handler__ = handler


def shutdown_temp_handler():
    """
    Shutdown the temporary deferred stream handler
    """
    temp_handler = get_temp_handler()
    if temp_handler is not None:
        for handler in logging.root.handlers[:]:
            if handler is temp_handler:
                logging.root.removeHandler(handler)
                break
        # Redefine the handler to None so it can be garbage collected
        setup_temp_handler.__handler__ = None


# Override the python's logging logger class as soon as this module is imported
if logging.getLoggerClass() is not SaltLoggingClass:

    logging.setLoggerClass(SaltLoggingClass)
    logging.addLevelName(QUIET, "QUIET")
    logging.addLevelName(PROFILE, "PROFILE")
    logging.addLevelName(TRACE, "TRACE")
    logging.addLevelName(GARBAGE, "GARBAGE")

    if not logging.root.handlers:
        # No configuration to the logging system has been done so far.
        # Set the root logger at the lowest level possible
        logging.root.setLevel(GARBAGE)

        # Add a permanent null handler so that we never get messages like:
        #   No handlers could be found for logger 'foo'
        logging.root.addHandler(get_null_handler())


# Now that we defined the default logging logger class, we can instantiate our logger
# DO NOT MOVE THIS
log = logging.getLogger(__name__)


def get_logging_level_from_string(level):
    """
    Return an integer matching a logging level.
    Return logging.ERROR when not matching.
    Return logging.WARNING when the passed level is None
    """
    if level is None:
        return logging.WARNING

    if isinstance(level, int):
        # Level is already an integer, return it
        return level
    try:
        return LOG_LEVELS[level.lower()]
    except KeyError:
        if level:
            log.warning(
                "Could not translate the logging level string '%s' "
                "into an actually logging level integer. Returning "
                "'logging.ERROR'.",
                level,
            )
        # Could't translate the passed string into a logging level.
        return logging.ERROR


def get_console_handler():
    """
    Get the console stream handler
    """
    try:
        return setup_console_handler.__handler__
    except AttributeError:
        return


def is_console_handler_configured():
    """
    Is the console stream handler configured
    """
    return get_console_handler() is not None


def shutdown_console_handler():
    """
    Shutdown the console stream handler
    """
    console_handler = get_console_handler()
    if console_handler is not None:
        logging.root.removeHandler(console_handler)
        setup_console_handler.__handler__ = None
        console_handler.close()


def setup_console_handler(log_level=None, log_format=None, date_format=None):
    """
    Setup the console stream handler
    """
    if is_console_handler_configured():
        log.warning("Console logging already configured")
        return

    log.trace(
        "Setting up console logging: %s",
        dict(log_level=log_level, log_format=log_format, date_format=date_format),
    )

    if log_level is None:
        log_level = logging.WARNING

    log_level = get_logging_level_from_string(log_level)

    set_log_record_factory(SaltColorLogRecord)

    handler = None
    for handler in logging.root.handlers:
        if handler in (get_null_handler(), get_temp_handler()):
            continue

        if not hasattr(handler, "stream"):
            # Not a stream handler, continue
            continue

        if handler.stream is sys.stderr:
            # There's already a logging handler outputting to sys.stderr
            break
    else:
        handler = StreamHandler(sys.stderr)
    handler.setLevel(log_level)

    # Set the default console formatter config
    import salt.config

    if not log_format:
        log_format = salt.config._DFLT_LOG_FMT_CONSOLE
    if not date_format:
        date_format = salt.config._DFLT_LOG_DATEFMT

    formatter = logging.Formatter(log_format, datefmt=date_format)

    handler.setFormatter(formatter)
    logging.root.addHandler(handler)

    setup_console_handler.__handler__ = handler


def get_logfile_handler():
    """
    Get the log file handler
    """
    try:
        return setup_logfile_handler.__handler__
    except AttributeError:
        return


def is_logfile_handler_configured():
    """
    Is the log file handler configured
    """
    return get_logfile_handler() is not None


def shutdown_logfile_handler():
    """
    Shutdown the log file handler
    """
    logfile_handler = get_logfile_handler()
    if logfile_handler is not None:
        logging.root.removeHandler(logfile_handler)
        setup_logfile_handler.__handler__ = None
        logfile_handler.close()


def setup_logfile_handler(
    log_path,
    log_level=None,
    log_format=None,
    date_format=None,
    max_bytes=0,
    backup_count=0,
    user=None,
):
    """
    Setup the log file handler

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
    """
    if is_logfile_handler_configured():
        log.warning("Logfile logging already configured")
        return

    log.trace(
        "Setting up log file logging: %s",
        dict(
            log_path=log_path,
            log_level=log_level,
            log_format=log_format,
            date_format=date_format,
            max_bytes=max_bytes,
            backup_count=backup_count,
            user=user,
        ),
    )

    if log_path is None:
        log.warning("log_path setting is set to `None`. Nothing else to do")
        return

    if log_level is None:
        log_level = logging.WARNING

    log_level = get_logging_level_from_string(log_level)

    parsed_log_path = urllib.parse.urlparse(log_path)

    if parsed_log_path.scheme in ("tcp", "udp", "file"):
        syslog_opts = {
            "facility": SysLogHandler.LOG_USER,
            "socktype": socket.SOCK_DGRAM,
        }

        if parsed_log_path.scheme == "file" and parsed_log_path.path:
            facility_name = parsed_log_path.path.split(os.sep)[-1].upper()
            if not facility_name.startswith("LOG_"):
                # The user is not specifying a syslog facility
                facility_name = "LOG_USER"  # Syslog default
                syslog_opts["address"] = parsed_log_path.path
            else:
                # The user has set a syslog facility, let's update the path to
                # the logging socket
                syslog_opts["address"] = os.sep.join(
                    parsed_log_path.path.split(os.sep)[:-1]
                )
        elif parsed_log_path.path:
            # In case of udp or tcp with a facility specified
            facility_name = parsed_log_path.path.lstrip(os.sep).upper()
            if not facility_name.startswith("LOG_"):
                # Logging facilities start with LOG_ if this is not the case
                # fail right now!
                raise LoggingRuntimeError(
                    "The syslog facility '{}' is not known".format(facility_name)
                )
        else:
            # This is the case of udp or tcp without a facility specified
            facility_name = "LOG_USER"  # Syslog default

        facility = getattr(SysLogHandler, facility_name, None)
        if facility is None:
            # This python syslog version does not know about the user provided
            # facility name
            raise LoggingRuntimeError(
                "The syslog facility '{}' is not known".format(facility_name)
            )
        syslog_opts["facility"] = facility

        if parsed_log_path.scheme == "tcp":
            syslog_opts["socktype"] = socket.SOCK_STREAM

        if parsed_log_path.scheme in ("tcp", "udp"):
            syslog_opts["address"] = (
                parsed_log_path.hostname,
                parsed_log_path.port or logging.handlers.SYSLOG_UDP_PORT,
            )

        if parsed_log_path.scheme == "file":
            syslog_opts.pop("socktype", None)

        try:
            # Et voilá! Finally our syslog handler instance
            handler = SysLogHandler(**syslog_opts)
        except OSError as err:
            log.error("Failed to setup the Syslog logging handler: %s", err)
            sys.exit(2)
    else:
        # make sure, the logging directory exists and attempt to create it if necessary
        if user is None:
            import salt.utils.user

            user = salt.utils.user.get_user()

        import salt.utils.files
        import salt.utils.verify

        # Logfile is not using Syslog, verify
        with salt.utils.files.set_umask(0o027):
            salt.utils.verify.verify_log_files([log_path], user)
        try:
            # Logfile logging is UTF-8 on purpose.
            # Since salt uses YAML and YAML uses either UTF-8 or UTF-16, if a
            # user is not using plain ASCII, their system should be ready to
            # handle UTF-8.
            if max_bytes > 0:
                handler = RotatingFileHandler(
                    log_path,
                    mode="a",
                    maxBytes=max_bytes,
                    backupCount=backup_count,
                    encoding="utf-8",
                    delay=0,
                )
            else:
                handler = WatchedFileHandler(
                    log_path, mode="a", encoding="utf-8", delay=0
                )
        except OSError:
            log.warning(
                "Failed to open log file, do you have permission to write to %s?",
                log_path,
            )
            # Do not proceed with any more configuration since it will fail, we
            # have the console logging already setup and the user should see
            # the error.
            return

    handler.setLevel(log_level)

    import salt.config

    if not log_format:
        log_format = salt.config._DFLT_LOG_FMT_LOGFILE
    if not date_format:
        date_format = salt.config._DFLT_LOG_DATEFMT_LOGFILE

    formatter = logging.Formatter(log_format, datefmt=date_format)

    handler.setFormatter(formatter)
    logging.root.addHandler(handler)

    setup_logfile_handler.__handler__ = handler


def get_extended_logging_handlers():
    """
    Get the extended logging handlers
    """
    try:
        return setup_extended_logging.__handlers__
    except AttributeError:
        return


def is_extended_logging_configured():
    """
    Are the extended logging handlers configured
    """
    extended_logging_handlers = get_extended_logging_handlers()
    if extended_logging_handlers is None:
        return False
    return True


def shutdown_extended_logging():
    """
    Shutdown the extended logging handlers
    """
    extended_logging_handlers = get_extended_logging_handlers()
    if extended_logging_handlers:
        for handler in extended_logging_handlers:
            logging.root.removeHandler(handler)
    setup_extended_logging.__handlers__ = None


def setup_extended_logging(opts):
    """
    Setup the extended logging handlers, internal or external
    """
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

    for name, get_handlers_func in providers.items():
        log.info("Processing 'log_handlers.%s'", name)
        # Keep a reference to the logging handlers count before getting the
        # possible additional ones.
        initial_handlers_count = len(logging.root.handlers)

        handlers = get_handlers_func()
        if isinstance(handlers, types.GeneratorType):
            handlers = list(handlers)
        elif handlers is False or handlers == [False]:
            # A false return value means not configuring any logging handler on
            # purpose
            log.info(
                "The `log_handlers.%s.setup_handlers()` function returned "
                "`False` which means no logging handler was configured on "
                "purpose. Continuing...",
                name,
            )
            continue
        else:
            # Make sure we have an iterable
            handlers = [handlers]

        for handler in handlers:
            if not handler and len(logging.root.handlers) == initial_handlers_count:
                log.info(
                    "The `log_handlers.%s`, did not return any handlers "
                    "and the global handlers count did not increase. This "
                    "could be a sign of `log_handlers.%s` not working as "
                    "supposed",
                    name,
                    name,
                )
                continue

            log.debug("Adding the '%s' provided logging handler: '%s'", name, handler)
            additional_handlers.append(handler)
            logging.root.addHandler(handler)

    for handler in logging.root.handlers:
        if handler in initial_handlers:
            continue
        additional_handlers.append(handler)

    setup_extended_logging.__handlers__ = additional_handlers


def setup_log_granular_levels(log_granular_levels):
    """
    Get the extended logging handlers
    """
    for handler_name, handler_level in log_granular_levels.items():
        _logger = logging.getLogger(handler_name)
        _logger.setLevel(get_logging_level_from_string(handler_level))


def in_mainprocess():
    """
    Check to see if this is the main process
    """
    try:
        return in_mainprocess.__pid__ == os.getpid()
    except AttributeError:
        if multiprocessing.current_process().name == "MainProcess":
            in_mainprocess.__pid__ = os.getpid()
            return True
        return False


def get_log_forwarding_host():
    """
    Get the log forwarding host
    """
    try:
        return set_log_forwarding_host.__host__
    except AttributeError:
        return


def set_log_forwarding_host(host):
    """
    Set the log forwarding host
    """
    set_log_forwarding_host.__host__ = host


def get_log_forwarding_port():
    """
    Get the log forwarding port
    """
    try:
        return set_log_forwarding_port.__port__
    except AttributeError:
        return


def set_log_forwarding_port(port):
    """
    Set the log forwarding port
    """
    set_log_forwarding_port.__port__ = port


def get_log_forwarding_prefix():
    """
    Get the log forwarding prefix
    """
    try:
        return set_log_forwarding_prefix.__prefix__
    except AttributeError:
        return


def set_log_forwarding_prefix(prefix):
    """
    Set the log forwarding prefix
    """
    set_log_forwarding_prefix.__prefix__ = prefix


def get_log_forwarding_level():
    """
    Get the log forwarding level
    """
    try:
        return set_log_forwarding_level.__log_level__
    except AttributeError:
        return


def set_log_forwarding_level(log_level):
    """
    Set the log forwarding level
    """
    set_log_forwarding_level.__log_level__ = log_level


def get_lowest_log_level():
    """
    Get the lowest log level
    """
    try:
        return set_lowest_log_level.__log_level__
    except AttributeError:
        return


def set_lowest_log_level(log_level):
    """
    Set the lowest log level
    """
    set_lowest_log_level.__log_level__ = log_level
    # Additionally set the root logger to the same level.
    # Nothing below this leve should be processed by python's logging machinery
    logging.root.setLevel(log_level)


def set_lowest_log_level_by_opts(opts):
    """
    Set the lowest log level by the passed config
    """
    log_levels = [
        get_logging_level_from_string(opts.get("log_level")),
        get_logging_level_from_string(opts.get("log_level_logfile")),
    ]
    for log_level in opts.get("log_granular_levels", {}).values():
        log_levels.append(get_logging_level_from_string(log_level))

    log_level = min(log_levels)
    set_lowest_log_level(log_level)
    set_log_forwarding_level.__log_level__ = log_level


def get_log_forwarding_config():
    """
    Get the log forwarding configuration
    """
    return {
        "log_host": get_log_forwarding_host(),
        "log_port": get_log_forwarding_port(),
        "log_level": get_log_forwarding_level(),
        "log_prefix": get_log_forwarding_prefix(),
    }


def is_log_forwarding_consumer_configured():
    """
    Is the log forwarding consumer configured
    """
    return get_log_forwarding_consumer() is not None


def get_log_forwarding_consumer():
    """
    Get the log forwarding consumer
    """
    try:
        return setup_log_forwarding_consumer.__process__
    except AttributeError:
        return


def shutdown_log_forwarding_consumer():
    """
    Shutdown the log forwarding consumer
    """
    if in_mainprocess() is False:
        return

    log_forwarding_consumer = get_log_forwarding_consumer()
    if log_forwarding_consumer is not None:
        if log_forwarding_consumer.is_alive():
            log.info("Terminating the log forwarding consumer process")
            host = get_log_forwarding_host()
            port = get_log_forwarding_port()
            context = zmq.Context()
            sender = context.socket(zmq.PUSH)
            sender.connect("tcp://{}:{}".format(host, port))
            try:
                sender.send(msgpack.dumps(None))
            finally:
                sender.close(1)
                context.term()
            # Now that we sent the sentinel, let's allow the log forwarding
            # consumer process to finish itself
            log_forwarding_consumer.join(2)
            # Not done yet, terminate it.
            if log_forwarding_consumer.is_alive():
                log_forwarding_consumer.terminate()

        setup_log_forwarding_consumer.__process__ = None


def setup_log_forwarding_consumer(opts, log_file_setting_name=None, daemonized=False):
    """
    Setup the log forwarding consumer

    This function will start the log forwarding consumer on a separate process.

    When ``daemonized`` is true, no console handler will be configured.
    """
    if in_mainprocess() is False:
        # We're not in the main process.
        # We won't setup the logging process
        return

    if log_file_setting_name is None:
        log_file_setting_name = "log_file"

    if not opts["log_forwarding_consumer"]:
        # Don't setup the log forwarding consumer.
        # Let's setup the regular logging handlers
        if daemonized is False:
            # The console should be quited when running daemonized
            setup_console_handler(
                log_level=opts.get("log_level"),
                log_format=opts.get("log_fmt_console"),
                date_format=opts.get("log_datefmt_console"),
            )
        setup_logfile_handler(
            opts.get(log_file_setting_name),
            log_level=opts.get("log_level_logfile"),
            log_format=opts.get("log_fmt_logfile"),
            date_format=opts.get("log_datefmt_logfile"),
            max_bytes=opts.get("log_rotate_max_bytes", 0),
            backup_count=opts.get("log_rotate_backup_count", 0),
        )
        setup_extended_logging(opts)
        setup_log_granular_levels(opts.get("log_granular_levels") or {})

        # Now, sync stored log messages and shutdown the temporary handler
        temp_handler = get_temp_handler()
        if temp_handler is not None:
            try:
                temp_handler.sync_with_handlers(logging.root.handlers)
                shutdown_temp_handler()
            except AttributeError:
                # This is not our temp logging handler,
                # leave it alone
                pass
        return

    log.warning("Setting up Salt's logging process")
    try:
        logging._acquireLock()  # pylint: disable=protected-access
        if is_log_forwarding_consumer_configured():
            return

        if HAS_MSGPACK is False:
            raise LoggingRuntimeError(
                "The 'msgpack' library needs to be installed for "
                "salt's logging process to work."
            )

        if HAS_ZMQ is False:
            raise LoggingRuntimeError(
                "The 'pyzmq' library needs to be installed for "
                "salt's logging process to work."
            )

        # We only need to pass log related opts
        filtered_opts = {}
        for key, value in opts.items():
            if not key.startswith(("log_", "extension_modules", log_file_setting_name)):
                continue
            filtered_opts[key] = value

        # Define an event in order to know when the process is up and ready
        log_forwarding_consumer_running_event = multiprocessing.Event()

        setup_log_forwarding_consumer.__process__ = proc = multiprocessing.Process(
            target=_log_forwarding_consumer_target,
            args=(log_forwarding_consumer_running_event,),
            kwargs={
                "opts": filtered_opts,
                "host": get_log_forwarding_host(),
                "port": get_log_forwarding_port(),
                "log_file_setting_name": log_file_setting_name,
                "daemonized": daemonized,
            },
            name="SaltLoggingProcess",
        )
        proc.daemon = True
        proc.start()
        # Be sure to always shutdown the log forwarding consumer process when
        # the parent process exits.
        atexit.register(shutdown_log_forwarding_consumer)

        # Wait for the log forwarding consumer process to start
        process_running = log_forwarding_consumer_running_event.wait(5)

        log.warning("Salt's logging process running event: %s", process_running)
        if process_running is True:
            # Now that the log consumer process is running,
            # let's setup log forwarding
            setup_log_forwarding(
                get_log_forwarding_host(),
                get_log_forwarding_port(),
                get_log_forwarding_level(),
                get_log_forwarding_prefix(),
            )
        else:
            # Something failed, flush the temp handler to stderr
            temp_handler = get_temp_handler()
            temp_handler.flush()
            raise LoggingRuntimeError(
                "Failed to check if the logging process was running"
            )
    finally:
        logging._releaseLock()  # pylint: disable=protected-access


def _log_forwarding_consumer_target(
    running_event,
    opts=None,
    host=None,
    port=None,
    log_file_setting_name=None,
    daemonized=False,
):
    """
    This function is meant to run on a separate process.
    It will configure the console, file and extended logging handlers and
    additionally will set a ZeroMQ PULL socket where any process can connect
    and send(PUSH) log records.
    """
    # Expect late imports in this function
    import salt.utils.process

    salt.utils.process.appendproctitle("SaltLoggingProcess")

    # Assign UID/GID of user to proc if set
    import salt.utils.verify

    user = opts.get("user")
    if user:
        salt.utils.verify.check_user(user)

    temp_handler = get_temp_handler()
    if temp_handler is not None:
        logging.root.removeHandler(temp_handler)

    if host is None:
        host = get_log_forwarding_host()

    if port is None:
        port = get_log_forwarding_port()

    if log_file_setting_name is None:
        log_file_setting_name = "log_file"

    # Reconfigure all logging in this new process
    if daemonized is False:
        # The console should be quited when running daemonized
        setup_console_handler(
            log_level=opts.get("log_level"),
            log_format=opts.get("log_fmt_console"),
            date_format=opts.get("log_datefmt_console"),
        )
    setup_logfile_handler(
        opts.get(log_file_setting_name),
        log_level=opts.get("log_level_logfile"),
        log_format=opts.get("log_fmt_logfile"),
        date_format=opts.get("log_datefmt_logfile"),
        max_bytes=opts.get("log_rotate_max_bytes", 0),
        backup_count=opts.get("log_rotate_backup_count", 0),
    )
    setup_extended_logging(opts)
    setup_log_granular_levels(opts.get("log_granular_levels") or {})
    _log_forwarding_consumer(running_event, host, port, setup_signal_handling=True)


def _log_forwarding_consumer(running_event, host, port, setup_signal_handling=True):
    """
    This function actually processed incoming log messages
    """

    context = puller = None
    try:
        context = zmq.Context()
        puller = context.socket(zmq.PULL)
        bind_address = "tcp://{}:{}".format(host, port)
        try:
            puller.bind(bind_address)
        except zmq.ZMQError as exc:
            raise LoggingRuntimeError(
                "Unable to bind to puller at: {}".format(bind_address)
            )
    except zmq.ZMQError as exc:
        log.error(
            "An error occurred while setting up Salt's log forwarding consumer: %s", exc
        )
        if puller is not None:
            puller.close(1)
        if context is not None:
            context.term()

    if not running_event.is_set():
        running_event.set()

    log.warning("Setting up Salt's log forwarding consumer process at %s", bind_address)

    def _handle_signals(signum, sigframe):
        msg = "The log forwarding consumer"
        if signum == signal.SIGINT:
            msg += " received a SIGINT."
        elif signum == signal.SIGTERM:
            msg += " received a SIGTERM."
        msg += " Exiting."
        log.debug(msg)
        sys.exit(0)

    try:
        if setup_signal_handling:
            # Handle signals. Shutdown will be handled by passing the sentinel
            # or on the next consequent signal
            for signum in (signal.SIGINT, signal.SIGTERM):
                signal.signal(signum, _handle_signals)

        if msgpack.version >= (0, 5, 2):
            msgpack_kwargs = {"raw": False}
        else:
            msgpack_kwargs = {"encoding": "utf-8"}

        while True:
            try:
                msg = puller.recv()
                record_dict = msgpack.loads(msg, **msgpack_kwargs)
                if record_dict is None:
                    # A sentinel to stop processing the queue
                    log.warning("Stopping Salt's logging process due to sentinel")
                    break
                # Just handle everything, filtering will be done by the handlers
                record = logging.makeLogRecord(record_dict)
                logger = logging.getLogger(record.name)
                logger.handle(record)
            except (EOFError, KeyboardInterrupt, SystemExit) as exc:
                break
            except Exception as exc:  # pylint: disable=broad-except
                log.warning(
                    "An exception occurred in the salt logging " "process: %s",
                    exc,
                    exc_info_on_loglevel=logging.DEBUG,
                )
    finally:
        puller.close(1)
        context.term()
        running_event.clear()


def is_log_forwarding_setup():
    """
    Is log forwarding configured
    """
    return get_log_forwarding_handler() is not None


def get_log_forwarding_handler():
    """
    Get the log forwarding handler
    """
    try:
        handler = setup_log_forwarding.__handler__
        if handler.pid != os.getpid():
            shutdown_log_forwarding(log_forwarding_handler=handler)
            handler = None
        return handler
    except (AttributeError, KeyError):
        return


def shutdown_log_forwarding(log_forwarding_handler=None):
    """
    Shutdown the log forwarding handler
    """
    if log_forwarding_handler is None:
        log_forwarding_handler = get_log_forwarding_handler()
        if log_forwarding_handler is not None:
            log.debug(
                "Shutting down log forwarding on process with pid: %s", os.getpid(),
            )

    if log_forwarding_handler is not None:
        log_forwarding_handler.stop()
        logging.root.removeHandler(log_forwarding_handler)
        delattr(setup_log_forwarding, "__handler__")


def setup_log_forwarding(log_host=None, log_port=None, log_level=None, log_prefix=None):
    """
    Configure the log forwarding handler
    """
    if is_log_forwarding_setup():
        return
        # This scenario happens on platforms which support forking
        # where the forked process will "inherit" the configured
        # log forwarding handler from the parent process.
        # We just make sure that handler is shutdown before
        # reconfiguring log forwarding:
        #
        # handler = get_log_forwarding_handler()
        # if handler.pid != os.getpid():
        #    shutdown_log_forwarding(handler)
        # else:
        #    return

    if log_host is None:
        log_host = get_log_forwarding_host()

    if log_port is None:
        log_port = get_log_forwarding_port()

    if log_level is None:
        log_level = get_log_forwarding_level()

    if log_prefix is None:
        log_prefix = get_log_forwarding_prefix()

    log_level = get_logging_level_from_string(log_level)

    log.debug(
        "Setting up log forwarding on process with pid %s: "
        "Host: %s; Port: %s; Level: %s; Prefix: %s",
        os.getpid(),
        log_host,
        log_port,
        LOG_VALUES_TO_LEVELS.get(log_level) or log_level,
        log_prefix,
    )

    try:
        logging._acquireLock()  # pylint: disable=protected-access
        # Instantiate the forwarding log handler
        handler = ZMQHandler(host=log_host, port=log_port, log_prefix=log_prefix)
        handler.setLevel(log_level)
        atexit.register(shutdown_log_forwarding)
        # Add it to the root logger
        logging.root.addHandler(handler)

        setup_log_forwarding.__handler__ = handler

        # Now, sync stored log messages and shutdown the temporary handler
        temp_handler = get_temp_handler()
        if temp_handler is not None:
            try:
                temp_handler.sync_with_handlers(logging.root.handlers)
                shutdown_temp_handler()
            except AttributeError:
                # This is not our temp logging handler,
                # leave it alone
                pass
    finally:
        logging._releaseLock()


def __get_exposed_module_attributes():
    """
    This function just ``dir()``'s this module and filters out any functions
    or variables which should not be available when wildcard importing it
    """
    exposed = []
    module = sys.modules[__name__]
    for name in dir(module):
        if name.startswith("_"):
            continue
        obj = getattr(module, name)
        if not isinstance(obj, types.FunctionType):
            if name.startswith(("LOG_", "SORTED_")):
                exposed.append(name)
            continue
        if obj.__module__ != __name__:
            continue
        exposed.append(name)
    return exposed


# Define what can be imported by wildcard imports
__all__ = __get_exposed_module_attributes()

# We're done with the function, nuke it
del __get_exposed_module_attributes


def __global_logging_exception_handler(
    exc_type,
    exc_value,
    exc_traceback,
    _logger=logging.getLogger(__name__),
    _stderr=sys.__stderr__,
    _format_exception=traceback.format_exception,
):
    """
    This function will log all un-handled python exceptions.
    """
    if exc_type.__name__ == "KeyboardInterrupt":
        # Do not log the exception or display the traceback on Keyboard Interrupt
        return

    # Log the exception
    msg = "An un-handled exception was caught by salt's global exception handler:"
    try:
        msg = "{}\n{}: {}\n{}".format(
            msg,
            exc_type.__name__,
            exc_value,
            "".join(_format_exception(exc_type, exc_value, exc_traceback)).strip(),
        )
    except Exception:  # pylint: disable=broad-except
        msg = "{}\n{}: {}\n(UNABLE TO FORMAT TRACEBACK)".format(
            msg, exc_type.__name__, exc_value,
        )
    try:
        _logger.error(msg)
    except Exception:  # pylint: disable=broad-except
        # Python is shutting down and logging has been set to None already
        try:
            _stderr.write(msg + "\n")
        except Exception:  # pylint: disable=broad-except
            # We have also lost reference to sys.__stderr__ ?!
            print(msg)

    # Call the original sys.excepthook
    try:
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
    except Exception:  # pylint: disable=broad-except
        # Python is shutting down and sys has been set to None already
        pass


# Set our own exception handler as the one to use
sys.excepthook = __global_logging_exception_handler
