# -*- coding: utf-8 -*-
'''
Compatibility functions for utils
'''

# Import python libs
from __future__ import absolute_import
import sys
import copy
import types

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


def deepcopy_bound(name):
    '''
    Compatibility helper function to allow copy.deepcopy copy bound methods
    which is broken on Python 2.6, due to the following bug:
    https://bugs.python.org/issue1515

    Warnings:
        - This method will mutate the global deepcopy dispatcher, which means that
        this function is NOT threadsafe!

        - Not Py3 compatible. The intended use case is deepcopy compat for Py2.6

    '''
    def _deepcopy_method(x, memo):
        return type(x)(x.im_func, copy.deepcopy(x.im_self, memo), x.im_class)
    try:
        pre_dispatch = copy._deepcopy_dispatch
        copy._deepcopy_dispatch[types.MethodType] = _deepcopy_method
        ret = copy.deepcopy(name)
    finally:
        copy._deepcopy_dispatch = pre_dispatch
    return ret
