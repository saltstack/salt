# -*- coding: utf-8 -*-
'''
Compatibility functions for copying
'''

# Import python libs
from __future__ import absolute_import
import copy
import types


def deepcopy_bound(name):
    '''
    Compatibility helper function to allow copy.deepcopy copy bound methods
    which is broken on Python 2.6, due to the following bug:
    https://bugs.python.org/issue1515

    Warnings:
        - This method will mutate the global deepcopy dispatcher, which means that
        this function is NOT threadsafe!

        - Not Py3 compatable. The intended use case is deepcopy compat for Py2.6

    '''
    def _deepcopy_method(x, memo):
        return type(x)(x.im_func, copy.deepcopy(x.im_self, memo), x.im_class)  # pylint: disable=W1699
    try:
        pre_dispatch = copy._deepcopy_dispatch
        copy._deepcopy_dispatch[types.MethodType] = _deepcopy_method
        ret = copy.deepcopy(name)
    finally:
        copy._deepcopy_dispatch = pre_dispatch
    return ret
