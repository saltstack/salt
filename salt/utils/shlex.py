# -*- coding: utf-8 -*-
'''
Modified versions of functions from shlex module
'''
from __future__ import absolute_import

# Import Python libs
import shlex

# Import 3rd-party libs
from salt.ext import six


def split(s, **kwargs):
    '''
    Only split if variable is a string
    '''
    if isinstance(s, six.string_types):
        return shlex.split(s, **kwargs)
    else:
        return s
