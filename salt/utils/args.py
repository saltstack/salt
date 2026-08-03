"""
Functions used for CLI argument handling
"""

from __future__ import annotations

import fnmatch
import inspect
import logging
import re
import shlex
import sys
import typing
from collections import namedtuple

import salt.utils.data
import salt.utils.jid
import salt.utils.versions
import salt.utils.win_functions
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


class _ArgSpec(namedtuple("ArgSpec", "args varargs keywords defaults")):
    """
    A Python 2 getargspec-style function specification.

    Positional-only parameters are included in ``args`` and their defaults
    in ``defaults``, matching the behavior of ``inspect.getfullargspec``.

    Details about keyword-only and positional-only parameters are available
    via the ``kwonlyargs``, ``kwonlydefaults`` and ``posonlyargs`` attributes,
    which are not part of the tuple, keeping it unpackable as a 4-tuple for
    backwards-compatibility.

    Additional calculated properties expose different views on this data.
    """

    kwonlyargs: tuple[str, ...]
    _kwonlydefaults: tuple[tuple[str, typing.Any], ...]
    posonlyargs: tuple[str, ...]

    def __new__(
        cls,
        args: list[str],
        varargs: str | None,
        keywords: str | None,
        defaults: tuple[typing.Any, ...] | None,
        kwonlyargs: tuple[str, ...] | None = None,
        kwonlydefaults: tuple[tuple[str, typing.Any], ...] | None = None,
        posonlyargs: tuple[str, ...] | None = None,
    ):
        self = super().__new__(cls, args, varargs, keywords, defaults)
        self.kwonlyargs = kwonlyargs if kwonlyargs is not None else ()
        self._kwonlydefaults = kwonlydefaults if kwonlydefaults is not None else ()
        self.posonlyargs = posonlyargs if posonlyargs is not None else ()
        return self

    def __getnewargs__(self):
        # Preserve the extra attributes through copy/pickle
        return (*self, self.kwonlyargs, self._kwonlydefaults, self.posonlyargs)

    @property
    def argdefaults(self) -> dict[str, typing.Any]:
        """
        Mapping of name => default for any param that can be passed a positional argument.
        The iteration order follows the positional argument order.
        """
        if not self.defaults:
            return {}
        defaults = list(zip(self.args[::-1], self.defaults[::-1]))
        defaults.reverse()  # Since dicts are ordered (Py3.7+), ensure the order follows the params
        return dict(defaults)

    @property
    def kwdefaults(self) -> dict[str, typing.Any]:
        """
        Mapping of name => default for any param that can be passed a keyword argument.
        """
        pos_kw_cnt = len(self.args) - len(self.posonlyargs)
        if pos_kw_cnt < 1:
            return self.kwonlydefaults
        ret = dict(
            zip(
                self.args[-min(len(self.defaults or ()), pos_kw_cnt) :],
                (self.defaults or [])[-pos_kw_cnt:],
            )
        )
        ret.update(self._kwonlydefaults)
        return ret

    @property
    def posonlydefaults(self) -> dict[str, typing.Any]:
        """
        Mapping of name => default for any param that must be passed a positional argument.
        """
        return {
            name: default
            for name, default in self.argdefaults.items()
            if name in self.posonlyargs
        }

    @property
    def kwonlydefaults(self) -> dict:
        """
        Mapping of name => default for any param that must be passed a keyword argument.
        """
        return dict(self._kwonlydefaults)

    @property
    def alldefaults(self) -> dict[str, typing.Any]:
        """
        Mapping of name => default for any param that has a default.
        """
        return self.argdefaults | self.kwonlydefaults

    @property
    def argreq(self) -> tuple[str, ...]:
        """
        Tuple of positional parameters that have no default.
        """
        if not self.defaults:
            return tuple(self.args)
        return tuple(self.args[: -len(self.defaults)])

    @property
    def kwonlyreq(self) -> tuple[str, ...]:
        """
        Tuple of keyword-only parameters that have no default.
        """
        kwdefaults = self.kwonlydefaults
        return tuple(kw for kw in self.kwonlyargs if kw not in kwdefaults)


def get_function_argspec(func, is_class_method=None) -> _ArgSpec:
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
    args = []
    defaults = []
    kwonlyargs = []
    kwonlydefaults = []
    posonlyargs = []
    varargs = keywords = None
    for param in sig.parameters.values():
        if param.kind in (param.POSITIONAL_ONLY, param.POSITIONAL_OR_KEYWORD):
            args.append(param.name)
            if param.kind == param.POSITIONAL_ONLY:
                posonlyargs.append(param.name)
            if param.default is not inspect._empty:
                defaults.append(param.default)
        elif param.kind == param.KEYWORD_ONLY:
            kwonlyargs.append(param.name)
            if param.default is not inspect._empty:
                kwonlydefaults.append((param.name, param.default))
        elif param.kind == param.VAR_POSITIONAL:
            varargs = param.name
        elif param.kind == param.VAR_KEYWORD:
            keywords = param.name
    if is_class_method:
        del args[0]
    return _ArgSpec(
        args,
        varargs,
        keywords,
        tuple(defaults) or None,
        tuple(kwonlyargs),
        tuple(kwonlydefaults),
        tuple(posonlyargs),
    )


def shlex_split(s, **kwargs):
    """
    Only split if the variable is a string
    """
    if isinstance(s, str):
        if sys.platform == "win32":
            return salt.utils.win_functions.shlex_split(s)
        else:
            return shlex.split(s, **kwargs)
    else:
        return s


def arg_lookup(fun, aspec: _ArgSpec | None = None):
    """
    Return a dict containing the arguments and default arguments to the
    function.
    """
    if aspec is None:
        aspec = get_function_argspec(fun)
    ret = {
        "args": list(aspec.argreq),
        "kwargs": aspec.alldefaults,
    }
    return ret


def argspec_report(functions, module=""):
    """
    Pass in a functions dict as it is returned from the loader and return the
    argspec function signatures
    """
    ret = {}

    def _render(fun):
        try:
            aspec = get_function_argspec(functions[fun])
        except TypeError:
            # this happens if not callable
            return
        ret[fun] = {
            "args": aspec.args if aspec.args else None,
            "varargs": True if aspec.varargs else None,
            "kwargs": True if aspec.keywords else None,
            "defaults": aspec.defaults if aspec.defaults else None,
            "posonlyargs": aspec.posonlyargs or None,
            "kwonlyargs": aspec.kwonlyargs or None,
            "kwonlydefaults": aspec.kwonlydefaults or None,
        }

    if "*" in module or "." in module:
        for fun in fnmatch.filter(functions, module):
            _render(fun)
    else:
        # "sys" should just match sys without also matching sysctl
        module_dot = module + "."
        for fun in (func for func in functions if func.startswith(module_dot)):
            _render(fun)

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
    # Since we WILL be changing the data dictionary, let's change a copy of it
    data = data.copy()

    kwargs = aspec.kwdefaults
    missing_kwargs = []
    for key in kwargs:
        try:
            kwargs[key] = data.pop(key)
        except KeyError:
            # Let's leave the default value in place
            pass

    for key in aspec.kwonlyreq:
        try:
            kwargs[key] = data.pop(key)
        except KeyError:
            # This is a required, keyword-only parameter
            missing_kwargs.append(key)
    if missing_kwargs:
        missing_count = len(missing_kwargs)
        missing_list = ", ".join(f"'{kw}'" for kw in missing_kwargs)
        raise SaltInvocationError(
            "{} missing {} required keyword-only argument{}: {}".format(
                fun.__name__,
                missing_count,
                missing_count > 1 and "s" or "",
                missing_list,
            )
        )

    missing_args = []
    for arg in aspec.argreq:
        try:
            ret["args"].append(data.pop(arg))
        except KeyError:
            missing_args.append(arg)
    if missing_args:
        args_count = len(aspec.argreq)
        raise SaltInvocationError(
            "{} takes at least {} argument{} ({} given). Missing: {}".format(
                fun.__name__,
                args_count,
                args_count > 1 and "s" or "",
                len(ret["args"]),
                ", ".join(f"'{missing}'" for missing in missing_args),
            )
        )

    # Positional-or-keyword parameters with defaults are handled in `kwargs`,
    # which are all of them if any positional-only parameter has a default.
    # We can thus simply append to `args`.
    for name, default in aspec.posonlydefaults.items():
        try:
            val = data.pop(name)
        except KeyError:
            val = default
        ret["args"].append(val)

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
    extra = tuple(key for key in data if key not in expected_extra_kws)
    if not extra:
        return ret

    # Found unexpected keyword arguments, raise an error to the user
    if len(extra) == 1:
        msg = "'{}' is an invalid keyword argument for '{}'".format(
            extra[0],
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
            extra[-1],
            ret.get(
                # In case this is being called for a state module
                "full",
                # Not a state module, build the name
                f"{fun.__module__}.{fun.__name__}",
            ),
        )
    raise SaltInvocationError(msg)


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
            _brackets = {"[": "]", "{": "}", "(": ")"}
            if not brackets or token != _brackets[brackets.pop()]:
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
