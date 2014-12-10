# -*- coding: utf-8 -*-
'''
    salt.cloud.exceptions
    ~~~~~~~~~~~~~~~~~~~~

    Salt cloud related exceptions.

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
'''
from __future__ import absolute_import

# Import salt libs
import salt.defaults.exitcodes
from salt.exceptions import SaltException


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
        self.message = '{0} [WARNING: salt.cloud.exceptions is deprecated. Please migrate to salt.exceptions!]'.format(message)
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
