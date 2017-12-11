# -*- coding: utf-8 -*-
'''
Utility functions to modify other functions
'''

from __future__ import absolute_import

# Import Python libs
import types

# Import 3rd-party libs
from salt.ext import six


def namespaced_function(function, global_dict, defaults=None, preserve_context=False):
    '''
    Redefine (clone) a function under a different globals() namespace scope

        preserve_context:
            Allow keeping the context taken from orignal namespace,
            and extend it with globals() taken from
            new targetted namespace.
    '''
    if defaults is None:
        defaults = function.__defaults__

    if preserve_context:
        _global_dict = function.__globals__.copy()
        _global_dict.update(global_dict)
        global_dict = _global_dict
    new_namespaced_function = types.FunctionType(
        function.__code__,
        global_dict,
        name=function.__name__,
        argdefs=defaults,
        closure=function.__closure__
    )
    new_namespaced_function.__dict__.update(function.__dict__)
    return new_namespaced_function


def alias_function(fun, name, doc=None):
    '''
    Copy a function
    '''
    alias_fun = types.FunctionType(fun.__code__,
                                   fun.__globals__,
                                   str(name),  # future lint: disable=blacklisted-function
                                   fun.__defaults__,
                                   fun.__closure__)
    alias_fun.__dict__.update(fun.__dict__)

    if doc and isinstance(doc, six.string_types):
        alias_fun.__doc__ = doc
    else:
        orig_name = fun.__name__
        alias_msg = ('\nThis function is an alias of '
                     '``{0}``.\n'.format(orig_name))
        alias_fun.__doc__ = alias_msg + fun.__doc__

    return alias_fun
