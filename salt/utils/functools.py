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
    if function.__kwdefaults__ is not None:
        # Only Py 3.13+ accept this in FunctionType.__new__
        new_namespaced_function.__kwdefaults__ = function.__kwdefaults__.copy()
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
    if fun.__kwdefaults__ is not None:
        # Only Py 3.13+ accept this in FunctionType.__new__
        alias_fun.__kwdefaults__ = fun.__kwdefaults__.copy()

    if doc and isinstance(doc, str):
        alias_fun.__doc__ = doc
    else:
        orig_name = fun.__name__
        alias_msg = f"\nThis function is an alias of ``{orig_name}``.\n"
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


def call_function(fun, *passed_args, **passed_kwargs):
    """
    Call a function.

    Variadic positional args to this function are parsed into positional and named
    arguments to the function. Anything but a dict becomes a positional argument.
    A dict specifies one or more named arguments. If multiple dicts specify the
    same named argument, the one that was passed first wins. Named arguments are
    not necessarily passed as keyword arguments - positional-only parameters and
    positional-or-keyword ones without defaults are always passed their values
    positionally, even if they were received in a dict.

    Variadic keyword args to this function are treated like a positional dict
    that was passed as the first one, overriding any named arg set by other dicts
    in the variadic positional args.

    This function handles all types of parameters - positional-only, keyword-only,
    positional-or-keyword, all with default values and without as well as variadic
    positional and keyword arguments.

    :param function fun: Function reference to call
    :return: Result of the function call
    """
    spec = salt.utils.args.get_function_argspec(fun)
    argreq, posonly = spec.argreq, spec.posonlyargs
    fargs, fkwargs, named_params = [], {}, {}
    kw_to_arg, kw_to_posarg = {}, {}

    # First, collect all arguments.
    # The previous implementation reversed the iteration, so be compatible and do the same.
    # That ensures the *first* dict that specifies a named argument wins, not the last.
    for arg in reversed(passed_args):
        if isinstance(arg, dict):
            named_params.update(arg)
        else:
            fargs.append(arg)
    fargs.reverse()

    # Make kwargs override anything set before. Usually, named params are meant to be passed either
    # as dicts in `passed_args` (module.run) or as passed_kwargs (mine.update), not both.
    named_params.update(passed_kwargs)
    # Now map params to their destination.
    # Parameters without defaults receive their arguments positionally.
    # We also want to support mapping named arguments to posonly args.
    for name, val in named_params.items():
        if name in posonly:
            kw_to_posarg[name] = val
        elif name in argreq:
            kw_to_arg[name] = val
        else:
            fkwargs[name] = val
    if len(fargs) > len(spec.args) and not spec.varargs:
        raise SaltInvocationError(
            f"{fun.__name__} only takes {len(spec.args)} positional parameters, got {(len(fargs))}"
        )

    missing_pos = []
    # Discover missing positional args without defaults in kwargs, otherwise fail.
    for arg in argreq[len(fargs) :]:
        if arg in kw_to_arg:
            fargs.append(kw_to_arg.pop(arg))
        elif arg in kw_to_posarg:
            fargs.append(kw_to_posarg.pop(arg))
        else:
            missing_pos.append(arg)
    if missing_pos:
        raise SaltInvocationError(f"Missing arguments: {', '.join(missing_pos)}")

    # Discover arguments to positional-only params with defaults
    posonly_defaults = spec.posonlydefaults
    for arg in posonly[len(fargs) :]:
        if arg in kw_to_posarg:
            fargs.append(kw_to_posarg.pop(arg))
        else:
            fargs.append(posonly_defaults[arg])

    # positional param names that already have an argument
    taken_pos = set(spec.args[: len(fargs)])
    # Set defaults of unspecified params that can receive a named argument in the parsed kwargs.
    # This seems redundant, but it's what the previous implementation did.
    for name, default in spec.kwdefaults.items():
        if name not in fkwargs and name not in taken_pos:
            fkwargs[name] = default

    # Ensure we have all required keyword-only args
    kwonlyreq = spec.kwonlyreq
    missing_kw = tuple(kw for kw in kwonlyreq if kw not in fkwargs)
    if missing_kw:
        missing_count = len(missing_kw)
        raise SaltInvocationError(
            "{} missing {} required keyword-only argument{}: {}".format(
                fun.__name__,
                missing_count,
                missing_count > 1 and "s" or "",
                ", ".join(f"'{missing}'" for missing in missing_kw),
            )
        )

    # Set of parameter names of positional-or-keyword ones that would receive both positional and kw args.
    duplicate_args = taken_pos.intersection(fkwargs)

    if spec.keywords and kw_to_posarg:
        # Python allows calling `def f(a, /, **kwargs)` with `f("foo", a="a")`
        # and puts `a` into kwargs. Let's mirror that.
        fkwargs.update(kw_to_posarg)
        kw_to_posarg.clear()

    if not (kw_to_arg or kw_to_posarg or duplicate_args):
        # If we did not receive args to the same parameter both positionally and by name, we're fine.
        return fun(*fargs, **fkwargs)

    # We want to fail here because we got multiple values for a single argument.
    # Python would fail with a TypeError anyways, but we can tell the user when it affects multiple args.
    duplicate_args = duplicate_args.union(kw_to_posarg).union(kw_to_arg)
    if len(duplicate_args) == 1:
        raise SaltInvocationError(
            f"{fun.__name__}() got multiple values for argument '{duplicate_args.pop()}'"
        )
    raise SaltInvocationError(
        f"{fun.__name__}() got multiple values for arguments "
        + ", ".join(f"'{arg}'" for arg in spec.args if arg in duplicate_args)
    )
