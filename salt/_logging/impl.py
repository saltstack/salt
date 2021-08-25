"""
    salt._logging.impl
    ~~~~~~~~~~~~~~~~~~

    Salt's logging implementation classes/functionality
"""
import logging
import re
import sys
import types

# Let's define these custom logging levels before importing the salt._logging.mixins
# since they will be used there
PROFILE = logging.PROFILE = 15
TRACE = logging.TRACE = 5
GARBAGE = logging.GARBAGE = 1
QUIET = logging.QUIET = 1000

from salt._logging.handlers import StreamHandler  # isort:skip

# from salt._logging.handlers import SysLogHandler  # isort:skip
# from salt._logging.handlers import RotatingFileHandler  # isort:skip
# from salt._logging.handlers import WatchedFileHandler  # isort:skip
from salt._logging.handlers import TemporaryLoggingHandler  # isort:skip
from salt._logging.mixins import LoggingMixinMeta  # isort:skip
from salt._logging.mixins import NewStyleClassMixin  # isort:skip
from salt.exceptions import LoggingRuntimeError  # isort:skip
from salt.utils.ctx import RequestContext  # isort:skip
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
            for handler in logging.root.handlers:
                if handler in (
                    LOGGING_NULL_HANDLER,
                    LOGGING_STORE_HANDLER,
                    LOGGING_TEMP_HANDLER,
                ):
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

    # ----- REMOVE ON REFACTORING COMPLETE -------------------------------------------------------------------------->
    if not logging.root.handlers:
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
    # <---- REMOVE ON REFACTORING COMPLETE ---------------------------------------------------------------------------


# Now that we defined the default logging logger class, we can instantiate our logger
# DO NOT MOVE THIS
log = logging.getLogger(__name__)


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
