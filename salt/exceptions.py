"""
This module is a central location for all salt exceptions
"""

import copy
import logging
import time

import salt.defaults.exitcodes
from salt.ext import six

log = logging.getLogger(__name__)


def _nested_output(obj):
    """
    Serialize obj and format for output
    """
    # Explicit late import to avoid circular import
    from salt.output import nested

    nested.__opts__ = {}
    ret = nested.output(obj).rstrip()
    return ret


def get_error_message(error):
    """
    Get human readable message from Python Exception
    """
    return error.args[0] if error.args else ""


class SaltException(Exception):
    """
    Base exception class; all Salt-specific exceptions should subclass this
    """

    def __init__(self, message=""):
        # Avoid circular import
        import salt.utils.stringutils

        if not isinstance(message, str):
            message = str(message)
        # pylint: disable=incompatible-py3-code,undefined-variable
        if six.PY3 or isinstance(message, unicode):
            super().__init__(salt.utils.stringutils.to_str(message))
            self.message = self.strerror = message
        # pylint: enable=incompatible-py3-code,undefined-variable
        elif isinstance(message, str):
            super().__init__(message)
            self.message = self.strerror = salt.utils.stringutils.to_unicode(message)
        else:
            # Some non-string input was passed. Run the parent dunder init with
            # a str version, and convert the passed value to unicode for the
            # message/strerror attributes.
            # futurdisable lint: blacklisteenable-function
            super().__init__(str(message))
            # future lint: blacklisteenable-function
            # pylint: disable=incompatible-py3-code,undefined-variable
            self.message = self.strerror = unicode(message)
            # pylint: enable=incompatible-py3-code,undefined-variable

    def pack(self):
        """
        Pack this exception into a serializable dictionary that is safe for
        transport via msgpack
        """
        return {"message": str(self), "args": self.args}


class SaltClientError(SaltException):
    """
    Problem reading the master root key
    """


class SaltMasterError(SaltException):
    """
    Problem reading the master root key
    """


class SaltNoMinionsFound(SaltException):
    """
    An attempt to retrieve a list of minions failed
    """


class SaltSyndicMasterError(SaltException):
    """
    Problem while proxying a request in the syndication master
    """


class SaltMasterUnresolvableError(SaltException):
    """
    Problem resolving the name of the Salt master
    """


class MasterExit(SystemExit):
    """
    Rise when the master exits
    """


class AuthenticationError(SaltException):
    """
    If sha256 signature fails during decryption
    """


class CommandNotFoundError(SaltException):
    """
    Used in modules or grains when a required binary is not available
    """


class CommandExecutionError(SaltException):
    """
    Used when a module runs a command which returns an error and wants
    to show the user the output gracefully instead of dying
    """

    def __init__(self, message="", info=None):
        # Avoid circular import
        import salt.utils.stringutils

        try:
            exc_str_prefix = salt.utils.stringutils.to_unicode(message)
        except TypeError:
            # Exception class instance passed. The SaltException __init__ will
            # gracefully handle non-string types passed to it, but since this
            # class needs to do some extra stuff with the exception "message"
            # before handing it off to the parent class' __init__, we'll need
            # to extract the message from the exception instance here
            try:
                exc_str_prefix = str(message)
            except UnicodeDecodeError:
                exc_str_prefix = salt.utils.stringutils.to_unicode(
                    str(message)
                )  # future lint: disable=blacklisted-function
        self.error = exc_str_prefix
        self.info = info
        if self.info:
            if exc_str_prefix:
                if exc_str_prefix[-1] not in ".?!":
                    exc_str_prefix += "."
                exc_str_prefix += " "

            exc_str_prefix += "Additional info follows:\n\n"
            # NOTE: exc_str will be passed to the parent class' constructor and
            # become self.strerror.
            exc_str = exc_str_prefix + _nested_output(self.info)

            # For states, if self.info is a dict also provide an attribute
            # containing a nested output of the info dict without the changes
            # (since they will be in the 'changes' key of the state return and
            # this information would be redundant).
            if isinstance(self.info, dict):
                info_without_changes = copy.deepcopy(self.info)
                info_without_changes.pop("changes", None)
                if info_without_changes:
                    self.strerror_without_changes = exc_str_prefix + _nested_output(
                        info_without_changes
                    )
                else:
                    # 'changes' was the only key in the info dictionary. We no
                    # longer have any additional info to display. Use the
                    # original error message.
                    self.strerror_without_changes = self.error
            else:
                self.strerror_without_changes = exc_str
        else:
            self.strerror_without_changes = exc_str = self.error

        # We call the parent __init__ last instead of first because we need the
        # logic above to derive the message string to use for the exception
        # message.
        super().__init__(exc_str)


class LoaderError(SaltException):
    """
    Problems loading the right renderer
    """


class PublishError(SaltException):
    """
    Problems encountered when trying to publish a command
    """


class MinionError(SaltException):
    """
    Minion problems reading uris such as salt:// or http://
    """


class FileserverConfigError(SaltException):
    """
    Used when invalid fileserver settings are detected
    """


class FileLockError(SaltException):
    """
    Used when an error occurs obtaining a file lock
    """

    def __init__(
        self, message, time_start=None, *args, **kwargs
    ):  # pylint: disable=keyword-arg-before-vararg
        super().__init__(message, *args, **kwargs)
        if time_start is None:
            log.warning(
                "time_start should be provided when raising a FileLockError. "
                "Defaulting to current time as a fallback, but this may "
                "result in an inaccurate timeout."
            )
            self.time_start = time.time()
        else:
            self.time_start = time_start


class GitLockError(SaltException):
    """
    Raised when an uncaught error occurs in the midst of obtaining an
    update/checkout lock in salt.utils.gitfs.

    NOTE: While this uses the errno param similar to an OSError, this exception
    class is *not* as subclass of OSError. This is done intentionally, so that
    this exception class can be caught in a try/except without being caught as
    an OSError.
    """

    def __init__(self, errno, message, *args, **kwargs):
        super().__init__(message, *args, **kwargs)
        self.errno = errno


class GitRemoteError(SaltException):
    """
    Used by GitFS to denote a problem with the existence of the "origin" remote
    or part of its configuration
    """


class SaltInvocationError(SaltException, TypeError):
    """
    Used when the wrong number of arguments are sent to modules or invalid
    arguments are specified on the command line
    """


class PkgParseError(SaltException):
    """
    Used when of the pkg modules cannot correctly parse the output from
    the CLI tool (pacman, yum, apt, aptitude, etc)
    """


class SaltRenderError(SaltException):
    """
    Used when a renderer needs to raise an explicit error. If a line number and
    buffer string are passed, get_context will be invoked to get the location
    of the error.
    """

    def __init__(
        self,
        message,
        line_num=None,
        buf="",
        marker="    <======================",
        trace=None,
    ):
        # Avoid circular import
        import salt.utils.stringutils

        self.error = message
        try:
            exc_str = salt.utils.stringutils.to_unicode(message)
        except TypeError:
            # Exception class instance passed. The SaltException __init__ will
            # gracefully handle non-string types passed to it, but since this
            # class needs to do some extra stuff with the exception "message"
            # before handing it off to the parent class' __init__, we'll need
            # to extract the message from the exception instance here
            try:
                exc_str = str(message)
            except UnicodeDecodeError:
                exc_str = salt.utils.stringutils.to_unicode(
                    str(message)
                )  # future lint: disable=blacklisted-function
        self.line_num = line_num
        self.buffer = buf
        self.context = ""
        if trace:
            exc_str += "\n{}\n".format(trace)
        if self.line_num and self.buffer:
            # Avoid circular import
            import salt.utils.templates

            self.context = salt.utils.stringutils.get_context(
                self.buffer, self.line_num, marker=marker
            )
            exc_str += "; line {}\n\n{}".format(
                self.line_num, salt.utils.stringutils.to_unicode(self.context),
            )
        super().__init__(exc_str)


class SaltClientTimeout(SaltException):
    """
    Thrown when a job sent through one of the Client interfaces times out

    Takes the ``jid`` as a parameter
    """

    def __init__(
        self, message, jid=None, *args, **kwargs
    ):  # pylint: disable=keyword-arg-before-vararg
        super().__init__(message, *args, **kwargs)
        self.jid = jid


class SaltCacheError(SaltException):
    """
    Thrown when a problem was encountered trying to read or write from the salt cache
    """


class TimeoutError(SaltException):
    """
    Thrown when an opration cannot be completet within a given time limit.
    """


class SaltReqTimeoutError(SaltException):
    """
    Thrown when a salt master request call fails to return within the timeout
    """


class TimedProcTimeoutError(SaltException):
    """
    Thrown when a timed subprocess does not terminate within the timeout,
    or if the specified timeout is not an int or a float
    """


class EauthAuthenticationError(SaltException):
    """
    Thrown when eauth authentication fails
    """


class TokenAuthenticationError(SaltException):
    """
    Thrown when token authentication fails
    """


class SaltDeserializationError(SaltException):
    """
    Thrown when salt cannot deserialize data.
    """


class AuthorizationError(SaltException):
    """
    Thrown when runner or wheel execution fails due to permissions
    """


class SaltDaemonNotRunning(SaltException):
    """
    Throw when a running master/minion/syndic is not running but is needed to
    perform the requested operation (e.g., eauth).
    """


class SaltRunnerError(SaltException):
    """
    Problem in runner
    """


class SaltWheelError(SaltException):
    """
    Problem in wheel
    """


class SaltConfigurationError(SaltException):
    """
    Configuration error
    """


class SaltSystemExit(SystemExit):
    """
    This exception is raised when an unsolvable problem is found. There's
    nothing else to do, salt should just exit.
    """

    def __init__(self, code=0, msg=None):
        SystemExit.__init__(self, msg)


class SaltCloudException(SaltException):
    """
    Generic Salt Cloud Exception
    """


class SaltCloudSystemExit(SaltCloudException):
    """
    This exception is raised when the execution should be stopped.
    """

    def __init__(self, message, exit_code=salt.defaults.exitcodes.EX_GENERIC):
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code


class SaltCloudConfigError(SaltCloudException):
    """
    Raised when a configuration setting is not found and should exist.
    """


class SaltCloudNotFound(SaltCloudException):
    """
    Raised when some cloud provider function cannot find what's being searched.
    """


class SaltCloudExecutionTimeout(SaltCloudException):
    """
    Raised when too much time has passed while querying/waiting for data.
    """


class SaltCloudExecutionFailure(SaltCloudException):
    """
    Raised when too much failures have occurred while querying/waiting for data.
    """


class SaltCloudPasswordError(SaltCloudException):
    """
    Raise when virtual terminal password input failed
    """


class NotImplemented(SaltException):
    """
    Used when a module runs a command which returns an error and wants
    to show the user the output gracefully instead of dying
    """


class TemplateError(SaltException):
    """
    Used when a custom error is triggered in a template
    """


class ArgumentValueError(CommandExecutionError):
    """
    Used when an invalid argument was passed to a command execution
    """


class CheckError(CommandExecutionError):
    """
    Used when a check fails
    """


# Validation related exceptions
class InvalidConfigError(CommandExecutionError):
    """
    Used when the config is invalid
    """


class InvalidEntityError(CommandExecutionError):
    """
    Used when an entity fails validation
    """


# VMware related exceptions
class VMwareSaltError(CommandExecutionError):
    """
    Used when a VMware object cannot be retrieved
    """


class VMwareRuntimeError(VMwareSaltError):
    """
    Used when a runtime error is encountered when communicating with the
    vCenter
    """


class VMwareConnectionError(VMwareSaltError):
    """
    Used when the client fails to connect to a either a VMware vCenter server or
    to a ESXi host
    """


class VMwareObjectRetrievalError(VMwareSaltError):
    """
    Used when a VMware object cannot be retrieved
    """


class VMwareObjectNotFoundError(VMwareSaltError):
    """
    Used when a VMware object was not found
    """


class VMwareObjectExistsError(VMwareSaltError):
    """
    Used when a VMware object already exists
    """


class VMwareMultipleObjectsError(VMwareObjectRetrievalError):
    """
    Used when multiple objects were retrieved (and one was expected)
    """


class VMwareNotFoundError(VMwareSaltError):
    """
    Used when a VMware object was not found
    """


class VMwareApiError(VMwareSaltError):
    """
    Used when representing a generic VMware API error
    """


class VMwareFileNotFoundError(VMwareApiError):
    """
    Used when representing a generic VMware error if a file not found
    """


class VMwareSystemError(VMwareSaltError):
    """
    Used when representing a generic VMware system error
    """


class VMwarePowerOnError(VMwareSaltError):
    """
    Used when error occurred during power on
    """


class VMwareVmRegisterError(VMwareSaltError):
    """
    Used when a configuration parameter is incorrect
    """


class VMwareVmCreationError(VMwareSaltError):
    """
    Used when a configuration parameter is incorrect
    """


class MissingSmb(SaltException):
    """
    Raised when no smb library is found.
    """


class LoggingRuntimeError(RuntimeError):
    """
    Raised when we encounter an error while logging
    """


class NxosError(SaltException):
    """
    NX-OS Base Exception class
    """


class NxosCliError(NxosError):
    """
    NX-OS Cli Error raised when Cli command rejected by the NX-OS device
    """


class NxosClientError(NxosError):
    """
    NX-OS Client Error raised for problems connecting to the NX-OS device
    """


class NxosRequestNotSupported(NxosError):
    """
    Raised for unsupported client requests
    """


class CodePageError(CommandExecutionError):
    """
    Raised when an error ocurs while getting or setting the windows code page
    """
