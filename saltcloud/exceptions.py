# -*- coding: utf-8 -*-
'''
    saltcloud.exceptions
    ~~~~~~~~~~~~~~~~~~~~

    Salt cloud related exceptions.

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import salt libs
from salt.exceptions import SaltException


class SaltCloudException(SaltException):
    '''
    Generic Salt Cloud Exception
    '''


class SaltCloudSystemExit(SaltCloudException):
    '''
    This exception is raised when the execution should be stopped.
    '''
    def __init__(self, message, exit_code=1):
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
    Raised when too much failures have ocurred while querying/waiting for data.
    '''
