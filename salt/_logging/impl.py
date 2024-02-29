"""
    salt._logging.impl
    ~~~~~~~~~~~~~~~~~~

    Salt's logging implementation classes/functionality
"""

import atexit
import logging
import multiprocessing
import os
import pathlib
import re
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

import salt.defaults.exitcodes  # isort:skip  pylint: disable=unused-import
import salt.utils.ctx

from salt._logging.handlers import DeferredStreamHandler  # isort:skip
from salt._logging.handlers import RotatingFileHandler  # isort:skip
from salt._logging.handlers import StreamHandler  # isort:skip
from salt._logging.handlers import SysLogHandler  # isort:skip
from salt._logging.handlers import WatchedFileHandler  # isort:skip
from salt._logging.mixins import LoggingMixinMeta  # isort:skip
from salt.exceptions import LoggingRuntimeError  # isort:skip
from salt.utils.immutabletypes import freeze, ImmutableDict  # isort:skip
from salt.utils.textformat import TextFormat  # isort:skip

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

# Default logging formatting options
DFLT_LOG_FMT_JID = "[JID: %(jid)s]"
DFLT_LOG_DATEFMT = "%H:%M:%S"
DFLT_LOG_DATEFMT_LOGFILE = "%Y-%m-%d %H:%M:%S"
DFLT_LOG_FMT_CONSOLE = "[%(levelname)-8s] %(message)s"
DFLT_LOG_FMT_LOGFILE = "%(asctime)s,%(msecs)03d [%(name)-17s:%(lineno)-4d][%(levelname)-8s][%(process)d] %(message)s"


class SaltLogRecord(logging.LogRecord):
    def __init__(self, *args, **kwargs):
        logging.LogRecord.__init__(self, *args, **kwargs)
        self.bracketname = f"[{str(self.name):<17}]"
        self.bracketlevel = f"[{str(self.levelname):<8}]"
        self.bracketprocess = f"[{str(self.process):>5}]"


class SaltColorLogRecord(SaltLogRecord):
    def __init__(self, *args, **kwargs):
        SaltLogRecord.__init__(self, *args, **kwargs)

        reset = TextFormat("reset")
        clevel = LOG_COLORS["levels"].get(self.levelname, reset)
        cmsg = LOG_COLORS["msgs"].get(self.levelname, reset)

        self.colorname = "{}[{:<17}]{}".format(
            LOG_COLORS["name"], str(self.name), reset
        )
        self.colorlevel = f"{clevel}[{str(self.levelname):<8}]{reset}"
        self.colorprocess = "{}[{:>5}]{}".format(
            LOG_COLORS["process"], str(self.process), reset
        )
        self.colormsg = f"{cmsg}{self.getMessage()}{reset}"


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


class SaltLoggingClass(LOGGING_LOGGER_CLASS, metaclass=LoggingMixinMeta):
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
                # Make sure the logger name on the formatted log record is not longer than 80 chars
                # Messages which need more that 80 chars will use them, but not ALL log messages
                max_logger_length = 80
            for handler in logging.root.handlers:
                if handler is get_temp_handler():
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

        current_jid = (
            salt.utils.ctx.get_request_context().get("data", {}).get("jid", None)
        )
        log_fmt_jid = (
            salt.utils.ctx.get_request_context()
            .get("opts", {})
            .get("log_fmt_jid", None)
        )

        if current_jid is not None:
            extra["jid"] = current_jid

        if log_fmt_jid is not None:
            extra["log_fmt_jid"] = log_fmt_jid

        # If both exc_info and exc_info_on_loglevel are both passed, let's fail
        if exc_info and exc_info_on_loglevel:
            raise LoggingRuntimeError(
                "Only one of 'exc_info' and 'exc_info_on_loglevel' is permitted"
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

        try:
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
        except TypeError:
            # Python < 3.8 - We still need this for salt-ssh since it will use
            # the system python, and not out onedir.
            LOGGING_LOGGER_CLASS._log(
                self,
                level,
                msg,
                args,
                exc_info=exc_info,
                extra=extra,
                stack_info=stack_info,
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
                "into an actual logging level integer. Returning "
                "'logging.ERROR'.",
                level,
            )
        # Couldn't translate the passed string into a logging level.
        return logging.ERROR


def get_logging_options_dict():
    """
    Return the logging options dictionary
    """
    try:
        return set_logging_options_dict.__options_dict__
    except AttributeError:
        return


def set_logging_options_dict(opts):
    """
    Create a logging related options dictionary based off of the loaded salt config
    """
    try:
        if isinstance(set_logging_options_dict.__options_dict__, ImmutableDict):
            raise RuntimeError(
                "The logging options have been frozen. They can no longer be changed."
            )
    except AttributeError:
        pass
    set_logging_options_dict.__options_dict__ = opts
    set_lowest_log_level_by_opts(opts)


def freeze_logging_options_dict():
    """
    Turn the logging options dictionary into an immutable dictionary
    """
    set_logging_options_dict.__options_dict__ = freeze(
        set_logging_options_dict.__options_dict__
    )


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
    handler = get_temp_handler()
    if handler is not None:
        log_level = get_logging_level_from_string(log_level)
        if handler.level != log_level:
            handler.setLevel(log_level)
        return

    if log_level is None:
        log_level = logging.WARNING

    log_level = get_logging_level_from_string(log_level)

    handler = None
    for handler in logging.root.handlers:

        if not hasattr(handler, "stream"):
            # Not a stream handler, continue
            continue

        if handler.stream is sys.stderr:
            # There's already a logging handler outputting to sys.stderr
            break
    else:
        handler = DeferredStreamHandler(sys.stderr)

        def tryflush():
            try:
                handler.flush()
            except ValueError:
                # File handle has already been closed.
                pass

        atexit.register(tryflush)
    handler.setLevel(log_level)

    # Set the default temporary console formatter config
    formatter = logging.Formatter(DFLT_LOG_FMT_CONSOLE, datefmt=DFLT_LOG_DATEFMT)
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
                logging.root.handlers.remove(handler)
                handler.sync_with_handlers(logging.root.handlers)
                handler.close()
                break
        # Redefine the handler to None so it can be garbage collected
        setup_temp_handler.__handler__ = None


# Override the python's logging logger class as soon as this module is imported
if logging.getLoggerClass() is not SaltLoggingClass:

    # Import pip._internal which itself will install it's own custom logging handler
    # we want to override that handler with ours
    try:
        import pip._internal.utils._log as pip_log_module  # pylint: disable=no-name-in-module,import-error
    except ImportError:
        pip_log_module = None

    logging.setLoggerClass(SaltLoggingClass)
    logging.addLevelName(QUIET, "QUIET")
    logging.addLevelName(PROFILE, "PROFILE")
    logging.addLevelName(TRACE, "TRACE")
    logging.addLevelName(GARBAGE, "GARBAGE")
    if pip_log_module is not None:
        # Let's make newer versions of pip work by patching SaltLoggingClass to
        # add a verbose method which is what pip expects
        SaltLoggingClass.verbose = SaltLoggingClass.debug

    if not logging.root.handlers:
        # No configuration to the logging system has been done so far.
        # Set the root logger at the lowest level possible
        logging.root.setLevel(GARBAGE)

        # Add a permanent null handler so that we never get messages like:
        #   No handlers could be found for logger 'foo'
        setup_temp_handler()
        logging.root.addHandler(get_temp_handler())


# Now that we defined the default logging logger class, we can instantiate our logger
# DO NOT MOVE THIS
log = logging.getLogger(__name__)


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
        console_handler.close()
        setup_console_handler.__handler__ = None
        atexit.unregister(shutdown_console_handler)


def setup_console_handler(log_level=None, log_format=None, date_format=None):
    """
    Setup the console stream handler
    """
    if is_console_handler_configured():
        log.warning("Console logging already configured")
        return

    atexit.register(shutdown_console_handler)

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
        if handler is get_temp_handler():
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
    if not log_format:
        log_format = DFLT_LOG_FMT_CONSOLE
    if not date_format:
        date_format = DFLT_LOG_DATEFMT

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
        logfile_handler.close()
        setup_logfile_handler.__handler__ = None
        atexit.unregister(shutdown_logfile_handler)


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

    Thinking on doing remote logging you might also be thinking that
    you could point Salt's logging to the remote syslog. **Please Don't!**
    An issue has been reported when doing this over TCP where the logged lines
    get concatenated. See #3061.

    The preferred way to do remote logging is setup a local syslog, point
    Salt's logging to the local syslog(unix socket is much faster) and then
    have the local syslog forward the log messages to the remote syslog.
    """
    if is_logfile_handler_configured():
        log.warning("Logfile logging already configured")
        return

    atexit.register(shutdown_logfile_handler)
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
            path = pathlib.Path(parsed_log_path.path)
            facility_name = path.stem.upper()
            try:
                if not facility_name.startswith("LOG_"):
                    # The user is not specifying a syslog facility
                    facility_name = "LOG_USER"  # Syslog default
                    syslog_opts["address"] = str(path.resolve())
                else:
                    # The user has set a syslog facility, let's update the path to
                    # the logging socket
                    syslog_opts["address"] = str(path.resolve().parent)
            except OSError as exc:
                raise LoggingRuntimeError(
                    f"Failed to setup the Syslog logging handler: {exc}"
                ) from exc
        elif parsed_log_path.path:
            # In case of udp or tcp with a facility specified
            path = pathlib.Path(parsed_log_path.path)
            facility_name = path.stem.upper()
            if not facility_name.startswith("LOG_"):
                # Logging facilities start with LOG_ if this is not the case
                # fail right now!
                raise LoggingRuntimeError(
                    f"The syslog facility '{facility_name}' is not known"
                )
        else:
            # This is the case of udp or tcp without a facility specified
            facility_name = "LOG_USER"  # Syslog default

        facility = getattr(SysLogHandler, facility_name, None)
        if facility is None:
            # This python syslog version does not know about the user provided
            # facility name
            raise LoggingRuntimeError(
                f"The syslog facility '{facility_name}' is not known"
            )
        syslog_opts["facility"] = facility

        if parsed_log_path.scheme in ("tcp", "udp"):
            syslog_opts["address"] = (
                parsed_log_path.hostname,
                parsed_log_path.port or logging.handlers.SYSLOG_UDP_PORT,
            )
            if parsed_log_path.scheme == "tcp":
                syslog_opts["socktype"] = socket.SOCK_STREAM

        elif parsed_log_path.scheme == "file":
            syslog_opts.pop("socktype", None)

        try:
            # Et voilá! Finally our syslog handler instance
            handler = SysLogHandler(**syslog_opts)
        except OSError as exc:
            raise LoggingRuntimeError(
                f"Failed to setup the Syslog logging handler: {exc}"
            ) from exc
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

    if not log_format:
        log_format = DFLT_LOG_FMT_LOGFILE
    if not date_format:
        date_format = DFLT_LOG_DATEFMT_LOGFILE

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
            handler.close()
        atexit.unregister(shutdown_extended_logging)
    setup_extended_logging.__handlers__ = None


def setup_extended_logging(opts):
    """
    Setup the extended logging handlers, internal or external
    """
    if is_extended_logging_configured() is True:
        # Don't re-configure external loggers
        return

    # Explicit late import of Salt's loader
    import salt.loader

    # Be sure to always shutdown extened logging on process termination
    atexit.register(shutdown_extended_logging)

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
                    "The `log_handlers.%s`, did not return any handlers and the "
                    "global handlers count did not increase. This could be a sign "
                    "that `log_handlers.%s` is not working as expected.",
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


def setup_logging():
    opts = get_logging_options_dict()
    if not opts:
        raise RuntimeError("The logging options have not been set yet.")
    if (
        opts.get("configure_console_logger", True)
        and not is_console_handler_configured()
    ):
        setup_console_handler(
            log_level=opts["log_level"],
            log_format=opts["log_fmt_console"],
            date_format=opts["log_datefmt"],
        )
    if opts.get("configure_file_logger", True) and not is_logfile_handler_configured():
        log_file_level = opts["log_level_logfile"] or opts["log_level"]
        if log_file_level != "quiet":
            log_file_key = opts.get("log_file_key") or "log_file"
            setup_logfile_handler(
                log_path=opts[log_file_key],
                log_level=log_file_level,
                log_format=opts["log_fmt_logfile"],
                date_format=opts["log_datefmt_logfile"],
                max_bytes=opts["log_rotate_max_bytes"],
                backup_count=opts["log_rotate_backup_count"],
                user=opts["user"],
            )
        else:
            setup_logfile_handler.__handler__ = logging.NullHandler()
    if (
        opts.get("configure_ext_handlers", True)
        and not is_extended_logging_configured()
    ):
        setup_extended_logging(opts)
    if opts.get("configure_granular_levels", True):
        setup_log_granular_levels(opts["log_granular_levels"])

    # Any logging that should be configured, is configured by now. Shutdown the temporary logging handler.
    shutdown_temp_handler()


def shutdown_logging():
    if is_temp_handler_configured():
        shutdown_temp_handler()
    if is_extended_logging_configured():
        shutdown_extended_logging()
    if is_logfile_handler_configured():
        shutdown_logfile_handler()
    if is_console_handler_configured():
        shutdown_console_handler()


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
    # Nothing below this level should be processed by python's logging machinery
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
    msg = "An un-handled exception was caught by Salt's global exception handler:"
    try:
        msg = "{}\n{}: {}\n{}".format(
            msg,
            exc_type.__name__,
            exc_value,
            "".join(_format_exception(exc_type, exc_value, exc_traceback)).strip(),
        )
    except Exception:  # pylint: disable=broad-except
        msg = "{}\n{}: {}\n(UNABLE TO FORMAT TRACEBACK)".format(
            msg,
            exc_type.__name__,
            exc_value,
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
