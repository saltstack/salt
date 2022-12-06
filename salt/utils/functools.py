"""
Utility functions to modify other functions
"""
import logging
import types

import salt.utils.args
import salt.utils.versions
from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)


def namespaced_function(function, global_dict, defaults=None, preserve_context=None):
    """
    Redefine (clone) a function under a different globals() namespace scope.

    Any keys missing in the passed ``global_dict`` that is present in the
    passed function ``__globals__`` attribute get's copied over into
    ``global_dict``, thus avoiding ``NameError`` from modules imported in
    the original function module.

    :param defaults:
        .. deprecated:: 3005

    :param preserve_context:
        .. deprecated:: 3005

        Allow keeping the context taken from orignal namespace,
        and extend it with globals() taken from
        new targetted namespace.
    """
    if defaults is not None:
        salt.utils.versions.warn_until(
            3008,
            "Passing 'defaults' to 'namespaced_function' is deprecated, slated "
            "for removal in {version} and no longer does anything for the "
            "function being namespaced.",
        )

    if preserve_context is not None:
        salt.utils.versions.warn_until(
            3008,
            "Passing 'preserve_context' to 'namespaced_function' is deprecated, "
            "slated for removal in {version} and no longer does anything for the "
            "function being namespaced.",
        )

    # Make sure that any key on the globals of the function being copied get's
    # added to the destination globals dictionary, if not present.
    for key, value in function.__globals__.items():
        if key not in global_dict:
            global_dict[key] = value

    new_namespaced_function = types.FunctionType(
        function.__code__,
        global_dict,
        name=function.__name__,
        argdefs=function.__defaults__,
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
        str(name),
        fun.__defaults__,
        fun.__closure__,
    )
    alias_fun.__dict__.update(fun.__dict__)

    if doc and isinstance(doc, str):
        alias_fun.__doc__ = doc
    else:
        orig_name = fun.__name__
        alias_msg = "\nThis function is an alias of ``{}``.\n".format(orig_name)
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
    :return: The result of the function call
    """
    argspec = salt.utils.args.get_function_argspec(salt_function)
    # function_kwargs is initialized to a dictionary of keyword arguments the function to be run accepts
    function_kwargs = dict(
        zip(
            argspec.args[
                -len(argspec.defaults or []) :
            ],  # pylint: disable=incompatible-py3-code
            argspec.defaults or [],
        )
    )
    # expected_args is initialized to a list of positional arguments that the function to be run accepts
    expected_args = argspec.args[
        : len(argspec.args or []) - len(argspec.defaults or [])
    ]
    function_args, kw_to_arg_type = [], {}
    for funcset in reversed(args or []):
        if not isinstance(funcset, dict):
            # We are just receiving a list of args to the function to be run, so just append
            # those to the arg list that we will pass to the func.
            function_args.append(funcset)
        else:
            for kwarg_key in funcset.keys():
                # We are going to pass in a keyword argument. The trick here is to make certain
                # that if we find that in the *args* list that we pass it there and not as a kwarg
                if kwarg_key in expected_args:
                    kw_to_arg_type[kwarg_key] = funcset[kwarg_key]
                else:
                    # Otherwise, we're good and just go ahead and pass the keyword/value pair into
                    # the kwargs list to be run.
                    function_kwargs.update(funcset)
    function_args.reverse()
    # Add kwargs passed as kwargs :)
    function_kwargs.update(kwargs)
    for arg in expected_args:
        if arg in kw_to_arg_type:
            function_args.append(kw_to_arg_type[arg])
    _exp_prm = len(argspec.args or []) - len(argspec.defaults or [])
    _passed_prm = len(function_args)
    missing = []
    if _exp_prm > _passed_prm:
        for arg in argspec.args[_passed_prm:]:
            if arg not in function_kwargs:
                missing.append(arg)
            else:
                # Found the expected argument as a keyword
                # increase the _passed_prm count
                _passed_prm += 1
    if missing:
        raise SaltInvocationError("Missing arguments: {}".format(", ".join(missing)))
    elif _exp_prm > _passed_prm:
        raise SaltInvocationError(
            "Function expects {} positional parameters, got only {}".format(
                _exp_prm, _passed_prm
            )
        )

    return salt_function(*function_args, **function_kwargs)
