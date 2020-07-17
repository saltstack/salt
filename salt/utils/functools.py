# -*- coding: utf-8 -*-
"""
Utility functions to modify other functions
"""

from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import Python libs
import types

import salt.utils.args

# Import salt libs
from salt.exceptions import SaltInvocationError

# Import 3rd-party libs
from salt.ext import six
from salt.ext.six.moves import zip

log = logging.getLogger(__name__)


def namespaced_function(function, global_dict, defaults=None, preserve_context=False):
    """
    Redefine (clone) a function under a different globals() namespace scope

        preserve_context:
            Allow keeping the context taken from orignal namespace,
            and extend it with globals() taken from
            new targetted namespace.
    """
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
        closure=function.__closure__,
    )
    new_namespaced_function.__dict__.update(function.__dict__)
    return new_namespaced_function


def alias_function(fun, name, doc=None):
    """
    Copy a function
    """
    alias_fun = types.FunctionType(
        fun.__code__,
        fun.__globals__,
        str(name),  # future lint: disable=blacklisted-function
        fun.__defaults__,
        fun.__closure__,
    )
    alias_fun.__dict__.update(fun.__dict__)

    if doc and isinstance(doc, six.string_types):
        alias_fun.__doc__ = doc
    else:
        orig_name = fun.__name__
        alias_msg = "\nThis function is an alias of " "``{0}``.\n".format(orig_name)
        alias_fun.__doc__ = alias_msg + (fun.__doc__ or "")

    return alias_fun


def parse_function(function_arguments):
    """
    Helper function to parse function_arguments (module.run format)
    into args and kwargs.
    This function is similar to salt.utils.data.repack_dictlist, except that this
    handles mixed (i.e. dict and non-dict) arguments in the input list.

    :param list function_arguments: List of items and dicts with kwargs.

    :rtype: dict
    :return: Dictionary with ``args`` and ``kwargs`` keyword.
    """
    function_args = []
    function_kwargs = {}
    for item in function_arguments:
        if isinstance(item, dict):
            function_kwargs.update(item)
        else:
            function_args.append(item)
    return {"args": function_args, "kwargs": function_kwargs}


def call_function(salt_function, *args, **kwargs):
    """
    Calls a function from the specified module.

    :param function salt_function: Function reference to call
    :param any args: Arguments to pass to the salt_function.
        As this is called by states/module.py:run, this will accept
        dicts with (one or more) item(s) to be handled as a kwarg (or arg :P )
    :return: The result of the function call
    """
    # These go into the function call at the very end
    function_args, function_varargs, function_kwargs = {}, [], {}
    # First, find out things about the function that is to be called
    argspec = salt.utils.args.get_function_argspec(salt_function)
    num_args_or_kwargs = len(argspec.args or [])
    num_expected_kwargs = len(argspec.defaults or [])
    # expected_args is initialized to a list of positional arguments that the function to be run accepts
    expected_args = argspec.args[: num_args_or_kwargs - num_expected_kwargs]
    num_expected_args = len(expected_args)
    # expected_kwargs is initialized to a dictionary of keyword arguments the function to be run accepts
    expected_kwargs = dict(
        zip(argspec.args[-num_expected_kwargs:], argspec.defaults or [])
    )

    # First, go over all the args provided and save them in function_args
    # if the keyword is the currently expected arg. Complain about duplicates.
    # Process dict args as containing possibly multiple (but preferringly just
    # a single) kwarg(s) and store them in function_kwargs.
    duplicates = set()  # accumulate here for more specific error

    for idx, item in enumerate(args):
        if isinstance(item, dict):
            for kwarg, value in item.items():
                if kwarg in expected_args:
                    if kwarg in function_args:
                        duplicates.add(kwarg)
                        continue
                    function_args[kwarg] = value
                elif kwarg in expected_kwargs or argspec.keywords:
                    if kwarg in function_kwargs:
                        duplicates.add(kwarg)
                        continue
                    function_kwargs[kwarg] = value
                else:
                    raise SaltInvocationError(
                        "{}() got an unexpected keyword argument '{}'"
                        "".format(salt_function.__name__, kwarg)
                    )
        else:
            if idx >= num_expected_args and argspec.varargs:
                function_varargs.append(item)
                continue
            if idx >= num_args_or_kwargs:
                raise SaltInvocationError(
                    "Too many positional arguments supplied: {}, expected max {}"
                    "".format(idx, num_expected_args)
                )
            keyword = argspec.args[idx]
            if keyword in expected_args:
                if keyword in function_args:
                    duplicates.add(keyword)
                    continue
                function_args[keyword] = item
            else:  # elif keyword in expected_kwargs:
                if keyword in function_kwargs:
                    duplicates.add(keyword)
                    continue
                function_kwargs[keyword] = item

    # Process kwargs into function_args or arg_as_kwarg
    for keyword, value in (kwargs or {}).items():
        if keyword in expected_args:
            if keyword in function_args:
                duplicates.add(keyword)
                continue
            function_args[keyword] = value
        elif keyword in expected_kwargs or argspec.keywords:
            if keyword in function_kwargs:
                duplicates.add(keyword)
                continue
            function_kwargs[keyword] = value
        else:
            raise SaltInvocationError(
                "{}() got an unexpected keyword argument '{}'"
                "".format(salt_function.__name__, keyword)
            )

    if duplicates:
        # For niceness, present them in order of argspec.args
        raise SaltInvocationError(
            "Received multiple values for '{}'".format(
                ",".join([keyword for keyword in argspec.args if keyword in duplicates])
            )
        )

    # Now we check for missing args
    missing_args = [
        keyword for keyword in expected_args if keyword not in function_args
    ]
    if missing_args:
        raise SaltInvocationError(
            "Missing arguments: {}".format(",".join(missing_args))
        )

    return salt_function(
        *[function_args[keyword] for keyword in expected_args],
        *function_varargs,
        **function_kwargs
    )
