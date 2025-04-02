"""
Functions used for CLI argument handling
"""

import copy
import fnmatch
import inspect
import logging
import re
import shlex
from collections import namedtuple

import salt.utils.data
import salt.utils.jid
import salt.utils.versions
import salt.utils.yaml
from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)


KWARG_REGEX = re.compile(r"^([^\d\W][\w.-]*)=(?!=)(.*)$", re.UNICODE)


def clean_kwargs(**kwargs):
    """
    Return a dict without any of the __pub* keys (or any other keys starting
    with a dunder) from the kwargs dict passed into the execution module
    functions. These keys are useful for tracking what was used to invoke
    the function call, but they may not be desirable to have if passing the
    kwargs forward wholesale.

    Usage example:

    .. code-block:: python

        kwargs = __utils__['args.clean_kwargs'](**kwargs)
    """
    ret = {}
    for key, val in kwargs.items():
        if not key.startswith("__"):
            ret[key] = val
    return ret


def invalid_kwargs(invalid_kwargs, raise_exc=True):
    """
    Raise a SaltInvocationError if invalid_kwargs is non-empty
    """
    if invalid_kwargs:
        if isinstance(invalid_kwargs, dict):
            new_invalid = [f"{x}={y}" for x, y in invalid_kwargs.items()]
            invalid_kwargs = new_invalid
    msg = "The following keyword arguments are not valid: {}".format(
        ", ".join(invalid_kwargs)
    )
    if raise_exc:
        raise SaltInvocationError(msg)
    else:
        return msg


def condition_input(args, kwargs):
    """
    Return a single arg structure for the publisher to safely use
    """
    ret = []
    for arg in args:
        if isinstance(arg, int) and salt.utils.jid.is_jid(str(arg)):
            ret.append(str(arg))
        else:
            ret.append(arg)
    if isinstance(kwargs, dict) and kwargs:
        kw_ = {"__kwarg__": True}
        for key, val in kwargs.items():
            kw_[key] = val
        return ret + [kw_]
    return ret


def parse_input(args, condition=True, no_parse=None):
    """
    Parse out the args and kwargs from a list of input values. Optionally,
    return the args and kwargs without passing them to condition_input().

    Don't pull args with key=val apart if it has a newline in it.
    """
    if no_parse is None:
        no_parse = ()
    _args = []
    _kwargs = {}
    for arg in args:
        if isinstance(arg, str):
            arg_name, arg_value = parse_kwarg(arg)
            if arg_name:
                _kwargs[arg_name] = (
                    yamlify_arg(arg_value) if arg_name not in no_parse else arg_value
                )
            else:
                _args.append(yamlify_arg(arg))
        elif isinstance(arg, dict):
            # Yes, we're popping this key off and adding it back if
            # condition_input is called below, but this is the only way to
            # gracefully handle both CLI and API input.
            if arg.pop("__kwarg__", False) is True:
                _kwargs.update(arg)
            else:
                _args.append(arg)
        else:
            _args.append(arg)
    if condition:
        return condition_input(_args, _kwargs)
    return _args, _kwargs


def parse_kwarg(string_):
    """
    Parses the string and looks for the following kwarg format:

    "{argument name}={argument value}"

    For example: "my_message=Hello world"

    Returns the kwarg name and value, or (None, None) if the regex was not
    matched.
    """
    try:
        return KWARG_REGEX.match(string_).groups()
    except AttributeError:
        return None, None


def yamlify_arg(arg):
    """
    yaml.safe_load the arg
    """
    if not isinstance(arg, str):
        return arg

    # YAML loads empty (or all whitespace) strings as None:
    #
    # >>> import yaml
    # >>> yaml.load('') is None
    # True
    # >>> yaml.load('      ') is None
    # True
    #
    # Similarly, YAML document start/end markers would not load properly if
    # passed through PyYAML, as loading '---' results in None and '...' raises
    # an exception.
    #
    # Therefore, skip YAML loading for these cases and just return the string
    # that was passed in.
    if arg.strip() in ("", "---", "..."):
        return arg

    elif "_" in arg and all([x in "0123456789_" for x in arg.strip()]):
        # When the stripped string includes just digits and underscores, the
        # underscores are ignored and the digits are combined together and
        # loaded as an int. We don't want that, so return the original value.
        return arg

    else:
        if any(np_char in arg for np_char in ("\t", "\r", "\n")):
            # Don't mess with this CLI arg, since it has one or more
            # non-printable whitespace char. Since the CSafeLoader will
            # sanitize these chars rather than raise an exception, just
            # skip YAML loading of this argument and keep the argument as
            # passed on the CLI.
            return arg

    try:
        # Explicit late import to avoid circular import. DO NOT MOVE THIS.
        import salt.utils.yaml

        original_arg = arg
        if "#" in arg:
            # Only yamlify if it parses into a non-string type, to prevent
            # loss of content due to # as comment character
            parsed_arg = salt.utils.yaml.safe_load(arg)
            if isinstance(parsed_arg, str) or parsed_arg is None:
                return arg
            return parsed_arg
        if arg == "None":
            arg = None
        else:
            arg = salt.utils.yaml.safe_load(arg)

        if isinstance(arg, dict):
            # dicts must be wrapped in curly braces
            if isinstance(original_arg, str) and not original_arg.startswith("{"):
                return original_arg
            else:
                return arg

        elif isinstance(arg, list):
            # lists must be wrapped in brackets
            if isinstance(original_arg, str) and not original_arg.startswith("["):
                return original_arg
            else:
                return arg

        elif arg is None or isinstance(arg, (list, float, int, str)):
            # yaml.safe_load will load '|' and '!' as '', don't let it do that.
            if arg == "" and original_arg in ("|", "!"):
                return original_arg
            # yaml.safe_load will treat '#' as a comment, so a value of '#'
            # will become None. Keep this value from being stomped as well.
            elif arg is None and original_arg.strip().startswith("#"):
                return original_arg
            # Other times, yaml.safe_load will load '!' as None. Prevent that.
            elif arg is None and original_arg == "!":
                return original_arg
            else:
                return arg
        else:
            # we don't support this type
            return original_arg
    except Exception:  # pylint: disable=broad-except
        # In case anything goes wrong...
        return original_arg


def get_function_argspec(func, is_class_method=None):
    """
    A small wrapper around inspect.signature that also supports callable objects and wrapped functions

    If the given function is a wrapper around another function (i.e. has a
    ``__wrapped__`` attribute), return the functions specification of the underlying
    function.

    :param is_class_method: Pass True if you are sure that the function being passed
                            is an unbound method. The reason for this is that on
                            Python 3 unbound methods are classified as functions and
                            not methods, so ``self`` will not be removed from
                            the argspec unless ``is_class_method`` is True.
    """
    if not callable(func):
        raise TypeError(f"{func} is not a callable")

    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__

    try:
        sig = inspect.signature(func)
    except TypeError:
        raise TypeError(f"Cannot inspect argument list for '{func}'")

    # Build a namedtuple which looks like the result of a Python 2 argspec
    _ArgSpec = namedtuple("ArgSpec", "args varargs keywords defaults")
    args = []
    defaults = []
    varargs = keywords = None
    for param in sig.parameters.values():
        if param.kind in [param.POSITIONAL_OR_KEYWORD, param.KEYWORD_ONLY]:
            args.append(param.name)
            if param.default is not inspect._empty:
                defaults.append(param.default)
        elif param.kind == param.VAR_POSITIONAL:
            varargs = param.name
        elif param.kind == param.VAR_KEYWORD:
            keywords = param.name
    if is_class_method:
        del args[0]
    return _ArgSpec(args, varargs, keywords, tuple(defaults) or None)


def shlex_split(s, **kwargs):
    """
    Only split if variable is a string
    """
    if isinstance(s, str):
        # On PY2, shlex.split will fail with unicode types if there are
        # non-ascii characters in the string. So, we need to make sure we
        # invoke it with a str type, and then decode the resulting string back
        # to unicode to return it.
        return salt.utils.data.decode(
            shlex.split(salt.utils.stringutils.to_str(s), **kwargs)
        )
    else:
        return s


def arg_lookup(fun, aspec=None):
    """
    Return a dict containing the arguments and default arguments to the
    function.
    """
    ret = {"kwargs": {}}
    if aspec is None:
        aspec = get_function_argspec(fun)
    if aspec.defaults:
        ret["kwargs"] = dict(zip(aspec.args[::-1], aspec.defaults[::-1]))
    ret["args"] = [arg for arg in aspec.args if arg not in ret["kwargs"]]
    return ret


def argspec_report(functions, module=""):
    """
    Pass in a functions dict as it is returned from the loader and return the
    argspec function signatures
    """
    ret = {}
    if "*" in module or "." in module:
        for fun in fnmatch.filter(functions, module):
            try:
                aspec = get_function_argspec(functions[fun])
            except TypeError:
                # this happens if not callable
                continue

            args, varargs, kwargs, defaults = aspec

            ret[fun] = {}
            ret[fun]["args"] = args if args else None
            ret[fun]["defaults"] = defaults if defaults else None
            ret[fun]["varargs"] = True if varargs else None
            ret[fun]["kwargs"] = True if kwargs else None

    else:
        # "sys" should just match sys without also matching sysctl
        module_dot = module + "."

        for fun in functions:
            if fun.startswith(module_dot):
                try:
                    aspec = get_function_argspec(functions[fun])
                except TypeError:
                    # this happens if not callable
                    continue

                args, varargs, kwargs, defaults = aspec

                ret[fun] = {}
                ret[fun]["args"] = args if args else None
                ret[fun]["defaults"] = defaults if defaults else None
                ret[fun]["varargs"] = True if varargs else None
                ret[fun]["kwargs"] = True if kwargs else None

    return ret


def split_input(val, mapper=None):
    """
    Take an input value and split it into a list, returning the resulting list
    """
    if mapper is None:

        def mapper(x):
            return x

    if isinstance(val, list):
        return list(map(mapper, val))
    try:
        return list(map(mapper, [x.strip() for x in val.split(",")]))
    except AttributeError:
        return list(map(mapper, [x.strip() for x in str(val).split(",")]))


def test_mode(**kwargs):
    """
    Examines the kwargs passed and returns True if any kwarg which matching
    "Test" in any variation on capitalization (i.e. "TEST", "Test", "TeSt",
    etc) contains a True value (as determined by salt.utils.data.is_true).
    """
    # Once is_true is moved, remove this import and fix the ref below
    import salt.utils

    for arg, value in kwargs.items():
        try:
            if arg.lower() == "test" and salt.utils.data.is_true(value):
                return True
        except AttributeError:
            continue
    return False


def format_call(
    fun, data, initial_ret=None, expected_extra_kws=(), is_class_method=None
):
    """
    Build the required arguments and keyword arguments required for the passed
    function.

    :param fun: The function to get the argspec from
    :param data: A dictionary containing the required data to build the
                 arguments and keyword arguments.
    :param initial_ret: The initial return data pre-populated as dictionary or
                        None
    :param expected_extra_kws: Any expected extra keyword argument names which
                               should not trigger a :ref:`SaltInvocationError`
    :param is_class_method: Pass True if you are sure that the function being passed
                            is a class method. The reason for this is that on Python 3
                            ``inspect.ismethod`` only returns ``True`` for bound methods,
                            while on Python 2, it returns ``True`` for bound and unbound
                            methods. So, on Python 3, in case of a class method, you'd
                            need the class to which the function belongs to be instantiated
                            and this is not always wanted.
    :returns: A dictionary with the function required arguments and keyword
              arguments.
    """
    ret = initial_ret is not None and initial_ret or {}

    ret["args"] = []
    ret["kwargs"] = {}

    aspec = get_function_argspec(fun, is_class_method=is_class_method)

    arg_data = arg_lookup(fun, aspec)
    args = arg_data["args"]
    kwargs = arg_data["kwargs"]

    # Since we WILL be changing the data dictionary, let's change a copy of it
    data = data.copy()

    missing_args = []

    for key in kwargs:
        try:
            kwargs[key] = data.pop(key)
        except KeyError:
            # Let's leave the default value in place
            pass

    while args:
        arg = args.pop(0)
        try:
            ret["args"].append(data.pop(arg))
        except KeyError:
            missing_args.append(arg)

    if missing_args:
        used_args_count = len(ret["args"]) + len(args)
        args_count = used_args_count + len(missing_args)
        raise SaltInvocationError(
            "{} takes at least {} argument{} ({} given)".format(
                fun.__name__, args_count, args_count > 1 and "s" or "", used_args_count
            )
        )

    ret["kwargs"].update(kwargs)

    if aspec.keywords:
        # The function accepts **kwargs, any non expected extra keyword
        # arguments will made available.
        for key, value in data.items():
            if key in expected_extra_kws:
                continue
            ret["kwargs"][key] = value

        # No need to check for extra keyword arguments since they are all
        # **kwargs now. Return
        return ret

    # Did not return yet? Lets gather any remaining and unexpected keyword
    # arguments
    extra = {}
    for key, value in data.items():
        if key in expected_extra_kws:
            continue
        extra[key] = copy.deepcopy(value)

    if extra:
        # Found unexpected keyword arguments, raise an error to the user
        if len(extra) == 1:
            msg = "'{0[0]}' is an invalid keyword argument for '{1}'".format(
                list(extra.keys()),
                ret.get(
                    # In case this is being called for a state module
                    "full",
                    # Not a state module, build the name
                    f"{fun.__module__}.{fun.__name__}",
                ),
            )
        else:
            msg = "{} and '{}' are invalid keyword arguments for '{}'".format(
                ", ".join([f"'{e}'" for e in extra][:-1]),
                list(extra.keys())[-1],
                ret.get(
                    # In case this is being called for a state module
                    "full",
                    # Not a state module, build the name
                    f"{fun.__module__}.{fun.__name__}",
                ),
            )

        raise SaltInvocationError(msg)
    return ret


def parse_function(s):
    """
    Parse a python-like function call syntax.

    For example: module.function(arg, arg, kw=arg, kw=arg)

    This function takes care only about the function name and arguments list carying on quoting
    and bracketing. It doesn't perform identifiers and other syntax validity check.

    Returns a tuple of three values: function name string, arguments list and keyword arguments
    dictionary.
    """
    sh = shlex.shlex(s, posix=True)
    sh.escapedquotes = "\"'"
    word = []
    args = []
    kwargs = {}
    brackets = []
    key = None
    token = None
    for token in sh:
        if token == "(":
            break
        word.append(token)
    if not word or token != "(":
        return None, None, None
    fname = "".join(word)
    word = []
    good = False
    for token in sh:
        if token in "[{(":
            word.append(token)
            brackets.append(token)
        elif (token == "," or token == ")") and not brackets:
            if key:
                kwargs[key] = "".join(word)
            elif word:
                args.append("".join(word))
            if token == ")":
                good = True
                break
            key = None
            word = []
        elif token in "]})":
            _tokens = {"[": "]", "{": "}", "(": ")"}
            if not brackets or token != _tokens[brackets.pop()]:
                break
            word.append(token)
        elif token == "=" and not brackets:
            key = "".join(word)
            word = []
            continue
        else:
            word.append(token)
    if good:
        return fname, args, kwargs
    else:
        return None, None, None


def prepare_kwargs(all_kwargs, class_init_kwargs):
    """
    Filter out the kwargs used for the init of the class and the kwargs used to
    invoke the command required.

    all_kwargs
        All the kwargs the Execution Function has been invoked.

    class_init_kwargs
        The kwargs of the ``__init__`` of the class.
    """
    fun_kwargs = {}
    init_kwargs = {}
    for karg, warg in all_kwargs.items():
        if karg not in class_init_kwargs:
            if warg is not None:
                fun_kwargs[karg] = warg
            continue
        if warg is not None:
            init_kwargs[karg] = warg
    return init_kwargs, fun_kwargs
