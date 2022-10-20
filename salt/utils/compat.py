"""
Compatibility functions for utils
"""


import copy
import importlib
import sys
import types

import salt.loader


def pack_dunder(name):
    """
    Compatibility helper function to make __utils__ available on demand.
    """
    # TODO: Deprecate starting with Beryllium

    mod = sys.modules[name]
    if not hasattr(mod, "__utils__"):
        setattr(
            mod, "__utils__", salt.loader.utils(mod.__opts__, pack_self="__utils__")
        )


def deepcopy_bound(name):
    """
    Compatibility helper function to allow copy.deepcopy copy bound methods
    which is broken on Python 2.6, due to the following bug:
    https://bugs.python.org/issue1515

    Warnings:
        - This method will mutate the global deepcopy dispatcher, which means that
        this function is NOT threadsafe!

        - Not Py3 compatible. The intended use case is deepcopy compat for Py2.6

    """

    def _deepcopy_method(x, memo):
        # pylint: disable=incompatible-py3-code
        return type(x)(x.im_func, copy.deepcopy(x.im_self, memo), x.im_class)
        # pylint: enable=incompatible-py3-code

    try:
        pre_dispatch = copy._deepcopy_dispatch
        copy._deepcopy_dispatch[types.MethodType] = _deepcopy_method
        ret = copy.deepcopy(name)
    finally:
        copy._deepcopy_dispatch = pre_dispatch
    return ret


def cmp(x, y):
    """
    Compatibility helper function to replace the ``cmp`` function from Python 2. The
    ``cmp`` function is no longer available in Python 3.

    cmp(x, y) -> integer

    Return negative if x<y, zero if x==y, positive if x>y.
    """
    return (x > y) - (x < y)


def reload(mod):
    """
    Compatibility helper function to replace the ``reload`` builtin from Python 2.
    """
    try:
        return importlib.reload(mod)
    except AttributeError:
        return reload(mod)
