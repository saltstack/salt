# -*- coding: utf-8 -*-
'''
Utility functions to modify other functions
'''

from __future__ import absolute_import, unicode_literals, print_function

# Import Python libs
import types

# Import salt libs
from salt.exceptions import SaltInvocationError
import salt.utils.args
from salt.ext.six.moves import zip

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
        alias_fun.__doc__ = alias_msg + (fun.__doc__ or '')

    return alias_fun


def call_function(salt_function, **kwargs):
    '''
    Calls a function from the specified module.

    :param function salt_function: Function reference to call
    :param kwargs: args'n kwargs to pass to the function
    :return: The result of the function call
    '''
    argspec = salt.utils.args.get_function_argspec(salt_function)

    # func_kw is initialized to a dictionary of keyword arguments the function to be run accepts
    func_kw = dict(zip(argspec.args[-len(argspec.defaults or []):],  # pylint: disable=incompatible-py3-code
                   argspec.defaults or []))

    # func_args is initialized to a list of positional arguments that the function to be run accepts
    func_args = argspec.args[:len(argspec.args or []) - len(argspec.defaults or [])]
    arg_type, kw_to_arg_type, na_type, kw_type = [], {}, {}, False
    for funcset in reversed(kwargs.get('func_args') or []):
        if not isinstance(funcset, dict):
            # We are just receiving a list of args to the function to be run, so just append
            # those to the arg list that we will pass to the func.
            arg_type.append(funcset)
        else:
            for kwarg_key in six.iterkeys(funcset):
                # We are going to pass in a keyword argument. The trick here is to make certain
                # that if we find that in the *args* list that we pass it there and not as a kwarg
                if kwarg_key in func_args:
                    kw_to_arg_type[kwarg_key] = funcset[kwarg_key]
                    continue
                else:
                    # Otherwise, we're good and just go ahead and pass the keyword/value pair into
                    # the kwargs list to be run.
                    func_kw.update(funcset)
    arg_type.reverse()
    for arg in func_args:
        if arg in kw_to_arg_type:
            arg_type.append(kw_to_arg_type[arg])
    _exp_prm = len(argspec.args or []) - len(argspec.defaults or [])
    _passed_prm = len(arg_type)
    missing = []
    if na_type and _exp_prm > _passed_prm:
        for arg in argspec.args:
            if arg not in func_kw:
                missing.append(arg)
    if missing:
        raise SaltInvocationError('Missing arguments: {0}'.format(', '.join(missing)))
    elif _exp_prm > _passed_prm:
        raise SaltInvocationError('Function expects {0} parameters, got only {1}'.format(
            _exp_prm, _passed_prm))

    return salt_function(*arg_type, **func_kw)
