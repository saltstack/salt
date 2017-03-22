# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    salt.utils.validate.path
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Several path related validators
'''
from __future__ import absolute_import

# Import python libs
import os
import logging


log = logging.getLogger(__name__)


def is_writeable(path, check_parent=False):
    '''
    Check if a given path is writeable by the current user.

    :param path: The path to check
    :param check_parent: If the path to check does not exist, check for the
           ability to write to the parent directory instead
    :returns: True or False
    '''

    if os.access(path, os.F_OK) and os.access(path, os.W_OK):
        # The path exists and is writeable
        return True

    if os.access(path, os.F_OK) and not os.access(path, os.W_OK):
        # The path exists and is not writeable
        return False

    # The path does not exists or is not writeable

    if check_parent is False:
        # We're not allowed to check the parent directory of the provided path
        return False

    # Lets get the parent directory of the provided path
    parent_dir = os.path.dirname(path)

    if not os.access(parent_dir, os.F_OK):
        # Parent directory does not exit
        return False

    # Finally, return if we're allowed to write in the parent directory of the
    # provided path
    return os.access(parent_dir, os.W_OK)


def exists(path, quiet=False):
    '''
    Check if a given path exists.

    :param path: The path to check
    :param quiet: Suppresses the log message
    :returns: True or False
    '''

    _exists = os.access(path, os.F_OK)
    if not _exists and not quiet:
        log.error('Failed to read configuration from {0} - file does not exist'.format(path))

    return _exists


def is_readable(path, quiet=False):
    '''
    Check if a given path is readable by the current user.

    :param path: The path to check
    :param quiet: Suppresses the log message
    :returns: True or False
    '''

    _readable = os.access(path, os.R_OK)
    if not _readable and not quiet:
        log.error('Failed to read configuration from {0} - access denied'.format(path))

    return _readable
