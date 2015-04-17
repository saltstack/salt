# -*- coding: utf-8 -*-
'''
Compatibility functions for utils
'''

# Import python libs
from __future__ import absolute_import
import sys

# Import salt libs
import salt.loader


def pack_dunder(name):
    '''
    Compatibility helper function to make __utils__ available on demand.
    '''
    # TODO: Deprecate starting with Beryllium

    mod = sys.modules[name]
    if not hasattr(mod, '__utils__'):
        setattr(mod, '__utils__', salt.loader.utils(mod.__opts__))
