# -*- coding: utf-8 -*-
'''
This module is a central location for all salt exceptions
'''

# Import python libs
import copy

# Import salt libs
import salt.utils


class SaltException(Exception):
    '''
    Base exception class; all Salt-specific exceptions should subclass this
    '''


class SaltClientError(SaltException):
    '''
    Problem reading the master root key
    '''


class SaltMasterError(SaltException):
    '''
    Problem reading the master root key
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


class LoaderError(SaltException):
    '''
    Problems loading the right renderer
    '''


class MinionError(SaltException):
    '''
    Minion problems reading uris such as salt:// or http://
    '''


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
                 error,
                 line_num=None,
                 buf='',
                 marker='    <======================',
                 trace=None):
        self.error = error
        exc_str = copy.deepcopy(error)
        self.line_num = line_num
        self.buffer = buf
        self.context = ''
        if trace:
            exc_str += '\n{0}\n'.format(trace)
        if self.line_num and self.buffer:
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


class SaltRunnerError(SaltException):
    '''
    Problem in runner
    '''


class SaltWheelError(SaltException):
    '''
    Problem in wheel
    '''


class SaltSystemExit(SystemExit):
    '''
    This exception is raised when an unsolvable problem is found. There's
    nothing else to do, salt should just exit.
    '''
    def __init__(self, code=0, msg=None):
        SystemExit.__init__(self, code)
        if msg:
            self.message = msg
