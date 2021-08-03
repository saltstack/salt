"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    salt.log.setup
    ~~~~~~~~~~~~~~

    This is where Salt's logging gets set up.

    This module should be imported as soon as possible, preferably the first
    module salt or any salt depending library imports so any new logging
    logger instance uses our ``salt.log.setup.SaltLoggingClass``.
"""


import logging
import logging.handlers
import multiprocessing
import os
import socket
import sys
import time
import traceback
import types
import urllib.parse

# pylint: disable=unused-import
from salt._logging import (
    LOG_COLORS,
    LOG_LEVELS,
    LOG_VALUES_TO_LEVELS,
    SORTED_LEVEL_NAMES,
)
from salt._logging.handlers import (
    FileHandler,
    QueueHandler,
    RotatingFileHandler,
    StreamHandler,
    SysLogHandler,
    WatchedFileHandler,
)
from salt._logging.impl import (
    LOGGING_NULL_HANDLER,
    LOGGING_STORE_HANDLER,
    LOGGING_TEMP_HANDLER,
    SaltColorLogRecord,
    SaltLogRecord,
)
from salt._logging.impl import set_log_record_factory as setLogRecordFactory

# pylint: enable=unused-import

__CONSOLE_CONFIGURED = False
__LOGGING_CONSOLE_HANDLER = None
__LOGFILE_CONFIGURED = False
__LOGGING_LOGFILE_HANDLER = None
__TEMP_LOGGING_CONFIGURED = False
__EXTERNAL_LOGGERS_CONFIGURED = False
__MP_LOGGING_LISTENER_CONFIGURED = False
__MP_LOGGING_CONFIGURED = False
__MP_LOGGING_QUEUE = None
__MP_LOGGING_LEVEL = logging.GARBAGE
__MP_LOGGING_QUEUE_PROCESS = None
__MP_LOGGING_QUEUE_HANDLER = None
__MP_IN_MAINPROCESS = multiprocessing.current_process().name == "MainProcess"
__MP_MAINPROCESS_ID = None


def is_console_configured():
    return __CONSOLE_CONFIGURED


def is_logfile_configured():
    return __LOGFILE_CONFIGURED


def is_logging_configured():
    return __CONSOLE_CONFIGURED or __LOGFILE_CONFIGURED


def is_temp_logging_configured():
    return __TEMP_LOGGING_CONFIGURED


def is_mp_logging_listener_configured():
    return __MP_LOGGING_LISTENER_CONFIGURED


def is_mp_logging_configured():
    return __MP_LOGGING_LISTENER_CONFIGURED


def is_extended_logging_configured():
    return __EXTERNAL_LOGGERS_CONFIGURED


class SaltLogQueueHandler(QueueHandler):
    """
    Subclassed just to differentiate when debugging
    """


def getLogger(name):  # pylint: disable=C0103
    """
    This function is just a helper, an alias to:
        logging.getLogger(name)

    Although you might find it useful, there's no reason why you should not be
    using the aliased method.
    """
    return logging.getLogger(name)


def setup_temp_logger(log_level="error"):
    """
    Setup the temporary console logger
    """
    if is_temp_logging_configured():
        logging.getLogger(__name__).warning("Temporary logging is already configured")
        return

    if log_level is None:
        log_level = "warning"

    level = LOG_LEVELS.get(log_level.lower(), logging.ERROR)

    handler = None
    for handler in logging.root.handlers:
        if handler in (LOGGING_NULL_HANDLER, LOGGING_STORE_HANDLER):
            continue

        if not hasattr(handler, "stream"):
            # Not a stream handler, continue
            continue

        if handler.stream is sys.stderr:
            # There's already a logging handler outputting to sys.stderr
            break
    else:
        handler = LOGGING_TEMP_HANDLER
    handler.setLevel(level)

    # Set the default temporary console formatter config
    formatter = logging.Formatter("[%(levelname)-8s] %(message)s", datefmt="%H:%M:%S")
    handler.setFormatter(formatter)
    logging.root.addHandler(handler)

    # Sync the null logging handler messages with the temporary handler
    if LOGGING_NULL_HANDLER is not None:
        LOGGING_NULL_HANDLER.sync_with_handlers([handler])
    else:
        logging.getLogger(__name__).debug(
            "LOGGING_NULL_HANDLER is already None, can't sync messages with it"
        )

    # Remove the temporary null logging handler
    __remove_null_logging_handler()

    global __TEMP_LOGGING_CONFIGURED
    __TEMP_LOGGING_CONFIGURED = True


def setup_console_logger(log_level="error", log_format=None, date_format=None):
    """
    Setup the console logger
    """
    if is_console_configured():
        logging.getLogger(__name__).warning("Console logging already configured")
        return

    # Remove the temporary logging handler
    __remove_temp_logging_handler()

    if log_level is None:
        log_level = "warning"

    level = LOG_LEVELS.get(log_level.lower(), logging.ERROR)

    setLogRecordFactory(SaltColorLogRecord)

    handler = None
    for handler in logging.root.handlers:
        if handler is LOGGING_STORE_HANDLER:
            continue

        if not hasattr(handler, "stream"):
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
        log_format = "[%(levelname)-8s] %(message)s"
    if not date_format:
        date_format = "%H:%M:%S"

    formatter = logging.Formatter(log_format, datefmt=date_format)

    handler.setFormatter(formatter)
    logging.root.addHandler(handler)

    global __CONSOLE_CONFIGURED
    global __LOGGING_CONSOLE_HANDLER
    __CONSOLE_CONFIGURED = True
    __LOGGING_CONSOLE_HANDLER = handler


def setup_logfile_logger(
    log_path,
    log_level="error",
    log_format=None,
    date_format=None,
    max_bytes=0,
    backup_count=0,
):
    """
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
    """

    if is_logfile_configured():
        logging.getLogger(__name__).warning("Logfile logging already configured")
        return

    if log_path is None:
        logging.getLogger(__name__).warning(
            "log_path setting is set to `None`. Nothing else to do"
        )
        return

    # Remove the temporary logging handler
    __remove_temp_logging_handler()

    if log_level is None:
        log_level = "warning"

    level = LOG_LEVELS.get(log_level.lower(), logging.ERROR)

    parsed_log_path = urllib.parse.urlparse(log_path)

    root_logger = logging.getLogger()

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
                raise RuntimeError(
                    "The syslog facility '{}' is not known".format(facility_name)
                )
        else:
            # This is the case of udp or tcp without a facility specified
            facility_name = "LOG_USER"  # Syslog default

        facility = getattr(SysLogHandler, facility_name, None)
        if facility is None:
            # This python syslog version does not know about the user provided
            # facility name
            raise RuntimeError(
                "The syslog facility '{}' is not known".format(facility_name)
            )
        syslog_opts["facility"] = facility

        if parsed_log_path.scheme == "tcp":
            # tcp syslog support was only added on python versions >= 2.7
            if sys.version_info < (2, 7):
                raise RuntimeError(
                    "Python versions lower than 2.7 do not support logging "
                    "to syslog using tcp sockets"
                )
            syslog_opts["socktype"] = socket.SOCK_STREAM

        if parsed_log_path.scheme in ("tcp", "udp"):
            syslog_opts["address"] = (
                parsed_log_path.hostname,
                parsed_log_path.port or logging.handlers.SYSLOG_UDP_PORT,
            )

        if sys.version_info < (2, 7) or parsed_log_path.scheme == "file":
            # There's not socktype support on python versions lower than 2.7
            syslog_opts.pop("socktype", None)

        try:
            # Et voilá! Finally our syslog handler instance
            handler = SysLogHandler(**syslog_opts)
        except OSError as err:
            logging.getLogger(__name__).error(
                "Failed to setup the Syslog logging handler: %s", err
            )
            shutdown_multiprocessing_logging_listener()
            sys.exit(2)
    else:
        # make sure, the logging directory exists and attempt to create it if necessary
        log_dir = os.path.dirname(log_path)
        if not os.path.exists(log_dir):
            logging.getLogger(__name__).info(
                "Log directory not found, trying to create it: %s", log_dir
            )
            try:
                os.makedirs(log_dir, mode=0o700)
            except OSError as ose:
                logging.getLogger(__name__).warning(
                    "Failed to create directory for log file: %s (%s)", log_dir, ose
                )
                return
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
            logging.getLogger(__name__).warning(
                "Failed to open log file, do you have permission to write to %s?",
                log_path,
            )
            # Do not proceed with any more configuration since it will fail, we
            # have the console logging already setup and the user should see
            # the error.
            return

    handler.setLevel(level)

    # Set the default console formatter config
    if not log_format:
        log_format = "%(asctime)s [%(name)-15s][%(levelname)-8s] %(message)s"
    if not date_format:
        date_format = "%Y-%m-%d %H:%M:%S"

    formatter = logging.Formatter(log_format, datefmt=date_format)

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    global __LOGFILE_CONFIGURED
    global __LOGGING_LOGFILE_HANDLER
    __LOGFILE_CONFIGURED = True
    __LOGGING_LOGFILE_HANDLER = handler


def setup_extended_logging(opts):
    """
    Setup any additional logging handlers, internal or external
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
        logging.getLogger(__name__).info("Processing `log_handlers.%s`", name)
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
                logging.getLogger(__name__).info(
                    "The `log_handlers.%s`, did not return any handlers "
                    "and the global handlers count did not increase. This "
                    "could be a sign of `log_handlers.%s` not working as "
                    "supposed",
                    name,
                    name,
                )
                continue

            logging.getLogger(__name__).debug(
                "Adding the '%s' provided logging handler: '%s'", name, handler
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
            "LOGGING_STORE_HANDLER is already None, can't sync messages with it"
        )

    # Remove the temporary queue logging handler
    __remove_queue_logging_handler()

    # Remove the temporary null logging handler (if it exists)
    __remove_null_logging_handler()

    global __EXTERNAL_LOGGERS_CONFIGURED
    __EXTERNAL_LOGGERS_CONFIGURED = True


def get_multiprocessing_logging_queue():
    global __MP_LOGGING_QUEUE
    from salt.utils.platform import is_darwin, is_aix

    if __MP_LOGGING_QUEUE is not None:
        return __MP_LOGGING_QUEUE

    if __MP_IN_MAINPROCESS is False:
        # We're not in the MainProcess, return! No Queue shall be instantiated
        return __MP_LOGGING_QUEUE

    if __MP_LOGGING_QUEUE is None:
        if is_darwin() or is_aix():
            __MP_LOGGING_QUEUE = multiprocessing.Queue(32767)
        else:
            __MP_LOGGING_QUEUE = multiprocessing.Queue(100000)
    return __MP_LOGGING_QUEUE


def set_multiprocessing_logging_queue(queue):
    global __MP_LOGGING_QUEUE
    if __MP_LOGGING_QUEUE is not queue:
        __MP_LOGGING_QUEUE = queue


def get_multiprocessing_logging_level():
    return __MP_LOGGING_LEVEL


def set_multiprocessing_logging_level(log_level):
    global __MP_LOGGING_LEVEL
    __MP_LOGGING_LEVEL = log_level


def set_multiprocessing_logging_level_by_opts(opts):
    """
    This will set the multiprocessing logging level to the lowest
    logging level of all the types of logging that are configured.
    """
    global __MP_LOGGING_LEVEL

    log_levels = [
        LOG_LEVELS.get(opts.get("log_level", "").lower(), logging.ERROR),
        LOG_LEVELS.get(opts.get("log_level_logfile", "").lower(), logging.ERROR),
    ]
    for level in opts.get("log_granular_levels", {}).values():
        log_levels.append(LOG_LEVELS.get(level.lower(), logging.ERROR))

    __MP_LOGGING_LEVEL = min(log_levels)


def setup_multiprocessing_logging_listener(opts, queue=None):
    global __MP_LOGGING_QUEUE_PROCESS
    global __MP_LOGGING_LISTENER_CONFIGURED
    global __MP_MAINPROCESS_ID

    if __MP_IN_MAINPROCESS is False:
        # We're not in the MainProcess, return! No logging listener setup shall happen
        return

    if __MP_LOGGING_LISTENER_CONFIGURED is True:
        return

    if __MP_MAINPROCESS_ID is not None and __MP_MAINPROCESS_ID != os.getpid():
        # We're not in the MainProcess, return! No logging listener setup shall happen
        return

    __MP_MAINPROCESS_ID = os.getpid()
    __MP_LOGGING_QUEUE_PROCESS = multiprocessing.Process(
        target=__process_multiprocessing_logging_queue,
        args=(
            opts,
            queue or get_multiprocessing_logging_queue(),
        ),
    )
    __MP_LOGGING_QUEUE_PROCESS.daemon = True
    __MP_LOGGING_QUEUE_PROCESS.start()
    __MP_LOGGING_LISTENER_CONFIGURED = True


def setup_multiprocessing_logging(queue=None):
    """
    This code should be called from within a running multiprocessing
    process instance.
    """
    from salt.utils.platform import is_windows

    global __MP_LOGGING_CONFIGURED
    global __MP_LOGGING_QUEUE_HANDLER

    if __MP_IN_MAINPROCESS is True and not is_windows():
        # We're in the MainProcess, return! No multiprocessing logging setup shall happen
        # Windows is the exception where we want to set up multiprocessing
        # logging in the MainProcess.
        return

    try:
        logging._acquireLock()  # pylint: disable=protected-access

        if __MP_LOGGING_CONFIGURED is True:
            return

        # Let's set it to true as fast as possible
        __MP_LOGGING_CONFIGURED = True

        if __MP_LOGGING_QUEUE_HANDLER is not None:
            return

        # The temp null and temp queue logging handlers will store messages.
        # Since noone will process them, memory usage will grow. If they
        # exist, remove them.
        __remove_null_logging_handler()
        __remove_queue_logging_handler()

        # Let's add a queue handler to the logging root handlers
        __MP_LOGGING_QUEUE_HANDLER = SaltLogQueueHandler(
            queue or get_multiprocessing_logging_queue()
        )
        logging.root.addHandler(__MP_LOGGING_QUEUE_HANDLER)
        # Set the logging root level to the lowest needed level to get all
        # desired messages.
        log_level = get_multiprocessing_logging_level()
        logging.root.setLevel(log_level)
        logging.getLogger(__name__).debug(
            "Multiprocessing queue logging configured for the process running "
            "under PID: %s at log level %s",
            os.getpid(),
            log_level,
        )
        # The above logging call will create, in some situations, a futex wait
        # lock condition, probably due to the multiprocessing Queue's internal
        # lock and semaphore mechanisms.
        # A small sleep will allow us not to hit that futex wait lock condition.
        time.sleep(0.0001)
    finally:
        logging._releaseLock()  # pylint: disable=protected-access


def shutdown_console_logging():
    global __CONSOLE_CONFIGURED
    global __LOGGING_CONSOLE_HANDLER

    if not __CONSOLE_CONFIGURED or not __LOGGING_CONSOLE_HANDLER:
        return

    try:
        logging._acquireLock()
        logging.root.removeHandler(__LOGGING_CONSOLE_HANDLER)
        __LOGGING_CONSOLE_HANDLER = None
        __CONSOLE_CONFIGURED = False
    finally:
        logging._releaseLock()


def shutdown_logfile_logging():
    global __LOGFILE_CONFIGURED
    global __LOGGING_LOGFILE_HANDLER

    if not __LOGFILE_CONFIGURED or not __LOGGING_LOGFILE_HANDLER:
        return

    try:
        logging._acquireLock()
        logging.root.removeHandler(__LOGGING_LOGFILE_HANDLER)
        __LOGGING_LOGFILE_HANDLER = None
        __LOGFILE_CONFIGURED = False
    finally:
        logging._releaseLock()


def shutdown_temp_logging():
    __remove_temp_logging_handler()


def shutdown_multiprocessing_logging():
    global __MP_LOGGING_CONFIGURED
    global __MP_LOGGING_QUEUE_HANDLER

    if not __MP_LOGGING_CONFIGURED or not __MP_LOGGING_QUEUE_HANDLER:
        return

    try:
        logging._acquireLock()
        # Let's remove the queue handler from the logging root handlers
        logging.root.removeHandler(__MP_LOGGING_QUEUE_HANDLER)
        __MP_LOGGING_QUEUE_HANDLER = None
        __MP_LOGGING_CONFIGURED = False
        if not logging.root.handlers:
            # Ensure we have at least one logging root handler so
            # something can handle logging messages. This case should
            # only occur on Windows since on Windows we log to console
            # and file through the Multiprocessing Logging Listener.
            setup_console_logger()
    finally:
        logging._releaseLock()


def shutdown_multiprocessing_logging_listener(daemonizing=False):
    global __MP_LOGGING_QUEUE
    global __MP_LOGGING_QUEUE_PROCESS
    global __MP_LOGGING_LISTENER_CONFIGURED

    if daemonizing is False and __MP_IN_MAINPROCESS is True:
        # We're in the MainProcess and we're not daemonizing, return!
        # No multiprocessing logging listener shutdown shall happen
        return

    if not daemonizing:
        # Need to remove the queue handler so that it doesn't try to send
        # data over a queue that was shut down on the listener end.
        shutdown_multiprocessing_logging()

    if __MP_LOGGING_QUEUE_PROCESS is None:
        return

    if __MP_MAINPROCESS_ID is not None and __MP_MAINPROCESS_ID != os.getpid():
        # We're not in the MainProcess, return! No logging listener setup shall happen
        return

    if __MP_LOGGING_QUEUE_PROCESS.is_alive():
        logging.getLogger(__name__).debug(
            "Stopping the multiprocessing logging queue listener"
        )
        try:
            # Sent None sentinel to stop the logging processing queue
            __MP_LOGGING_QUEUE.put(None)
            # Let's join the multiprocessing logging handle thread
            time.sleep(0.5)
            logging.getLogger(__name__).debug("closing multiprocessing queue")
            __MP_LOGGING_QUEUE.close()
            logging.getLogger(__name__).debug("joining multiprocessing queue thread")
            __MP_LOGGING_QUEUE.join_thread()
            __MP_LOGGING_QUEUE = None
            __MP_LOGGING_QUEUE_PROCESS.join(1)
            __MP_LOGGING_QUEUE = None
        except OSError:
            # We were unable to deliver the sentinel to the queue
            # carry on...
            pass
        if __MP_LOGGING_QUEUE_PROCESS.is_alive():
            # Process is still alive!?
            __MP_LOGGING_QUEUE_PROCESS.terminate()
        __MP_LOGGING_QUEUE_PROCESS = None
        __MP_LOGGING_LISTENER_CONFIGURED = False
        logging.getLogger(__name__).debug(
            "Stopped the multiprocessing logging queue listener"
        )


def set_logger_level(logger_name, log_level="error"):
    """
    Tweak a specific logger's logging level
    """
    logging.getLogger(logger_name).setLevel(
        LOG_LEVELS.get(log_level.lower(), logging.ERROR)
    )


def patch_python_logging_handlers():
    """
    Patch the python logging handlers with out mixed-in classes
    """
    logging.StreamHandler = StreamHandler
    logging.FileHandler = FileHandler
    logging.handlers.SysLogHandler = SysLogHandler
    logging.handlers.WatchedFileHandler = WatchedFileHandler
    logging.handlers.RotatingFileHandler = RotatingFileHandler
    if sys.version_info >= (3, 2):
        logging.handlers.QueueHandler = QueueHandler


def __process_multiprocessing_logging_queue(opts, queue):
    # Avoid circular import
    import salt.utils.process

    salt.utils.process.appendproctitle("MultiprocessingLoggingQueue")

    # Assign UID/GID of user to proc if set
    from salt.utils.verify import check_user

    user = opts.get("user")
    if user:
        check_user(user)

    from salt.utils.platform import is_windows

    if is_windows():
        # On Windows, creating a new process doesn't fork (copy the parent
        # process image). Due to this, we need to setup all of our logging
        # inside this process.
        setup_temp_logger()
        setup_console_logger(
            log_level=opts.get("log_level"),
            log_format=opts.get("log_fmt_console"),
            date_format=opts.get("log_datefmt_console"),
        )
        setup_logfile_logger(
            opts.get("log_file"),
            log_level=opts.get("log_level_logfile"),
            log_format=opts.get("log_fmt_logfile"),
            date_format=opts.get("log_datefmt_logfile"),
            max_bytes=opts.get("log_rotate_max_bytes", 0),
            backup_count=opts.get("log_rotate_backup_count", 0),
        )
        setup_extended_logging(opts)
    while True:
        try:
            record = queue.get()
            if record is None:
                # A sentinel to stop processing the queue
                break
            # Just log everything, filtering will happen on the main process
            # logging handlers
            logger = logging.getLogger(record.name)
            logger.handle(record)
        except (EOFError, KeyboardInterrupt, SystemExit):
            break
        except Exception as exc:  # pylint: disable=broad-except
            logging.getLogger(__name__).warning(
                "An exception occurred in the multiprocessing logging queue thread: %r",
                exc,
                exc_info_on_loglevel=logging.DEBUG,
            )


def __remove_null_logging_handler():
    """
    This function will run once the temporary logging has been configured. It
    just removes the NullHandler from the logging handlers.
    """
    global LOGGING_NULL_HANDLER
    if LOGGING_NULL_HANDLER is None:
        # Already removed
        return

    root_logger = logging.getLogger()

    for handler in root_logger.handlers:
        if handler is LOGGING_NULL_HANDLER:
            root_logger.removeHandler(LOGGING_NULL_HANDLER)
            # Redefine the null handler to None so it can be garbage collected
            LOGGING_NULL_HANDLER = None
            break


def __remove_queue_logging_handler():
    """
    This function will run once the additional loggers have been synchronized.
    It just removes the QueueLoggingHandler from the logging handlers.
    """
    global LOGGING_STORE_HANDLER
    if LOGGING_STORE_HANDLER is None:
        # Already removed
        return

    root_logger = logging.getLogger()

    for handler in root_logger.handlers:
        if handler is LOGGING_STORE_HANDLER:
            root_logger.removeHandler(LOGGING_STORE_HANDLER)
            # Redefine the null handler to None so it can be garbage collected
            LOGGING_STORE_HANDLER = None
            break


def __remove_temp_logging_handler():
    """
    This function will run once logging has been configured. It just removes
    the temporary stream Handler from the logging handlers.
    """
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
        # Stop the logging queue listener thread
        if is_mp_logging_listener_configured():
            shutdown_multiprocessing_logging_listener()
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
