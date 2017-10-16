# -*- coding: utf-8 -*-
'''
This module is a central location for all salt exceptions
'''
from __future__ import absolute_import

# Import python libs
import copy
import logging
import time

# Import Salt libs
import salt.defaults.exitcodes
import salt.ext.six as six

log = logging.getLogger(__name__)


def _nested_output(obj):
    '''
    Serialize obj and format for output
    '''
    # Explicit late import to avoid circular import
    from salt.output import nested
    nested.__opts__ = {}
    ret = nested.output(obj).rstrip()
    return ret


def get_error_message(error):
    '''
    Get human readable message from Python Exception
    '''
    return error.args[0] if error.args else ''


class SaltException(Exception):
    '''
    Base exception class; all Salt-specific exceptions should subclass this
    '''
    def __init__(self, message=''):
        super(SaltException, self).__init__(message)
        self.strerror = message

    def pack(self):
        '''
        Pack this exception into a serializable dictionary that is safe for
        transport via msgpack
        '''
        if six.PY3:
            return {'message': str(self), 'args': self.args}
        return dict(message=self.__unicode__(), args=self.args)


class SaltClientError(SaltException):
    '''
    Problem reading the master root key
    '''


class SaltMasterError(SaltException):
    '''
    Problem reading the master root key
    '''


class SaltNoMinionsFound(SaltException):
    '''
    An attempt to retrieve a list of minions failed
    '''


class SaltSyndicMasterError(SaltException):
    '''
    Problem while proxying a request in the syndication master
    '''


class MasterExit(SystemExit):
    '''
    Rise when the master exits
    '''


class AuthenticationError(SaltException):
    '''
    If sha256 signature fails during decryption
    '''


class CommandNotFoundError(SaltException):
    '''
    Used in modules or grains when a required binary is not available
    '''


class CommandExecutionError(SaltException):
    '''
    Used when a module runs a command which returns an error and wants
    to show the user the output gracefully instead of dying
    '''
    def __init__(self, message='', info=None):
        self.error = exc_str_prefix = message
        self.info = info
        if self.info:
            try:
                if exc_str_prefix[-1] not in '.?!':
                    exc_str_prefix += '.'
            except IndexError:
                pass
            exc_str_prefix += ' Additional info follows:\n\n'
            # Get rid of leading space if the exception was raised with an
            # empty message.
            exc_str_prefix = exc_str_prefix.lstrip()
            # NOTE: exc_str will be passed to the parent class' constructor and
            # become self.strerror.
            exc_str = exc_str_prefix + _nested_output(self.info)

            # For states, if self.info is a dict also provide an attribute
            # containing a nested output of the info dict without the changes
            # (since they will be in the 'changes' key of the state return and
            # this information would be redundant).
            if isinstance(self.info, dict):
                info_without_changes = copy.deepcopy(self.info)
                info_without_changes.pop('changes', None)
                if info_without_changes:
                    self.strerror_without_changes = \
                        exc_str_prefix + _nested_output(info_without_changes)
                else:
                    # 'changes' was the only key in the info dictionary. We no
                    # longer have any additional info to display. Use the
                    # original error message.
                    self.strerror_without_changes = self.error
            else:
                self.strerror_without_changes = exc_str
        else:
            self.strerror_without_changes = exc_str = self.error

        super(CommandExecutionError, self).__init__(exc_str)


class LoaderError(SaltException):
    '''
    Problems loading the right renderer
    '''


class PublishError(SaltException):
    '''
    Problems encountered when trying to publish a command
    '''


class MinionError(SaltException):
    '''
    Minion problems reading uris such as salt:// or http://
    '''


class FileserverConfigError(SaltException):
    '''
    Used when invalid fileserver settings are detected
    '''


class FileLockError(SaltException):
    '''
    Used when an error occurs obtaining a file lock
    '''
    def __init__(self, msg, time_start=None, *args, **kwargs):
        super(FileLockError, self).__init__(msg, *args, **kwargs)
        if time_start is None:
            log.warning(
                'time_start should be provided when raising a FileLockError. '
                'Defaulting to current time as a fallback, but this may '
                'result in an inaccurate timeout.'
            )
            self.time_start = time.time()
        else:
            self.time_start = time_start


class GitLockError(SaltException):
    '''
    Raised when an uncaught error occurs in the midst of obtaining an
    update/checkout lock in salt.utils.gitfs.

    NOTE: While this uses the errno param similar to an OSError, this exception
    class is *not* as subclass of OSError. This is done intentionally, so that
    this exception class can be caught in a try/except without being caught as
    an OSError.
    '''
    def __init__(self, errno, strerror, *args, **kwargs):
        super(GitLockError, self).__init__(strerror, *args, **kwargs)
        self.errno = errno
        self.strerror = strerror


class SaltInvocationError(SaltException, TypeError):
    '''
    Used when the wrong number of arguments are sent to modules or invalid
    arguments are specified on the command line
    '''


class PkgParseError(SaltException):
    '''
    Used when of the pkg modules cannot correctly parse the output from
    the CLI tool (pacman, yum, apt, aptitude, etc)
    '''


class SaltRenderError(SaltException):
    '''
    Used when a renderer needs to raise an explicit error. If a line number and
    buffer string are passed, get_context will be invoked to get the location
    of the error.
    '''
    def __init__(self,
                 message,
                 line_num=None,
                 buf='',
                 marker='    <======================',
                 trace=None):
        self.error = message
        exc_str = copy.deepcopy(message)
        self.line_num = line_num
        self.buffer = buf
        self.context = ''
        if trace:
            exc_str += '\n{0}\n'.format(trace)
        if self.line_num and self.buffer:

            import salt.utils
            self.context = salt.utils.get_context(
                self.buffer,
                self.line_num,
                marker=marker
            )
            exc_str += '; line {0}\n\n{1}'.format(
                self.line_num,
                self.context
            )
        SaltException.__init__(self, exc_str)


class SaltClientTimeout(SaltException):
    '''
    Thrown when a job sent through one of the Client interfaces times out

    Takes the ``jid`` as a parameter
    '''
    def __init__(self, msg, jid=None, *args, **kwargs):
        super(SaltClientTimeout, self).__init__(msg, *args, **kwargs)
        self.jid = jid


class SaltCacheError(SaltException):
    '''
    Thrown when a problem was encountered trying to read or write from the salt cache
    '''


class SaltReqTimeoutError(SaltException):
    '''
    Thrown when a salt master request call fails to return within the timeout
    '''


class TimedProcTimeoutError(SaltException):
    '''
    Thrown when a timed subprocess does not terminate within the timeout,
    or if the specified timeout is not an int or a float
    '''


class EauthAuthenticationError(SaltException):
    '''
    Thrown when eauth authentication fails
    '''


class TokenAuthenticationError(SaltException):
    '''
    Thrown when token authentication fails
    '''


class AuthorizationError(SaltException):
    '''
    Thrown when runner or wheel execution fails due to permissions
    '''


class SaltDaemonNotRunning(SaltException):
    '''
    Throw when a running master/minion/syndic is not running but is needed to
    perform the requested operation (e.g., eauth).
    '''


class SaltRunnerError(SaltException):
    '''
    Problem in runner
    '''


class SaltWheelError(SaltException):
    '''
    Problem in wheel
    '''


class SaltConfigurationError(SaltException):
    '''
    Configuration error
    '''


class SaltSystemExit(SystemExit):
    '''
    This exception is raised when an unsolvable problem is found. There's
    nothing else to do, salt should just exit.
    '''
    def __init__(self, code=0, msg=None):
        SystemExit.__init__(self, msg)


class SaltCloudException(SaltException):
    '''
    Generic Salt Cloud Exception
    '''


class SaltCloudSystemExit(SaltCloudException):
    '''
    This exception is raised when the execution should be stopped.
    '''
    def __init__(self, message, exit_code=salt.defaults.exitcodes.EX_GENERIC):
        SaltCloudException.__init__(self, message)
        self.message = message
        self.exit_code = exit_code


class SaltCloudConfigError(SaltCloudException):
    '''
    Raised when a configuration setting is not found and should exist.
    '''


class SaltCloudNotFound(SaltCloudException):
    '''
    Raised when some cloud provider function cannot find what's being searched.
    '''


class SaltCloudExecutionTimeout(SaltCloudException):
    '''
    Raised when too much time has passed while querying/waiting for data.
    '''


class SaltCloudExecutionFailure(SaltCloudException):
    '''
    Raised when too much failures have occurred while querying/waiting for data.
    '''


class SaltCloudPasswordError(SaltCloudException):
    '''
    Raise when virtual terminal password input failed
    '''


class NotImplemented(SaltException):
    '''
    Used when a module runs a command which returns an error and wants
    to show the user the output gracefully instead of dying
    '''


# VMware related exceptions
class VMwareSaltError(CommandExecutionError):
    '''
    Used when a VMware object cannot be retrieved
    '''


class VMwareRuntimeError(VMwareSaltError):
    '''
    Used when a runtime error is encountered when communicating with the
    vCenter
    '''


class VMwareConnectionError(VMwareSaltError):
    '''
    Used when the client fails to connect to a either a VMware vCenter server or
    to a ESXi host
    '''


class VMwareObjectRetrievalError(VMwareSaltError):
    '''
    Used when a VMware object cannot be retrieved
    '''


class VMwareApiError(VMwareSaltError):
    '''
    Used when representing a generic VMware API error
    '''


class VMwareSystemError(VMwareSaltError):
    '''
    Used when representing a generic VMware system error
    '''
