# -*- coding: utf-8 -*-
'''
Decorators for salt.utils.path
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
import salt.utils.path
from salt.exceptions import CommandNotFoundError
from salt.utils.decorators.signature import identical_signature_wrapper


def which(exe):
    '''
    Decorator wrapper for salt.utils.path.which
    '''
    def wrapper(function):
        def wrapped(*args, **kwargs):
            if salt.utils.path.which(exe) is None:
                raise CommandNotFoundError(
                    'The \'{0}\' binary was not found in $PATH.'.format(exe)
                )
            return function(*args, **kwargs)
        return identical_signature_wrapper(function, wrapped)
    return wrapper


def which_bin(exes):
    '''
    Decorator wrapper for salt.utils.path.which_bin
    '''
    def wrapper(function):
        def wrapped(*args, **kwargs):
            if salt.utils.path.which_bin(exes) is None:
                raise CommandNotFoundError(
                    'None of provided binaries({0}) was not found '
                    'in $PATH.'.format(
                        ['\'{0}\''.format(exe) for exe in exes]
                    )
                )
            return function(*args, **kwargs)
        return identical_signature_wrapper(function, wrapped)
    return wrapper
