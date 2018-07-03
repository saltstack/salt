# -*- coding: utf-8 -*-
'''
Error generator to enable integration testing of salt runner error handling

'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs


# Import salt libs
import salt.utils.error


def error(name=None, message=''):
    '''
    If name is None Then return empty dict

    Otherwise raise an exception with __name__ from name, message from message

    CLI Example:

    .. code-block:: bash

        salt-run error
        salt-run error.error name="Exception" message="This is an error."
    '''
    ret = {}
    if name is not None:
        salt.utils.error.raise_error(name=name, message=message)
    return ret
