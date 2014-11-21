# -*- coding: utf-8 -*-
'''
Module for running arbitrary tests
'''

# Import Python libs
from __future__ import absolute_import


def jinja_error():
    '''

    CLI Example:

    .. code-block:: bash

        salt '*' salttest.jinja_error
    '''
    raise Exception('hehehe')
