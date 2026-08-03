import logging

import pytest

import salt.utils.functools
from salt.exceptions import SaltInvocationError
from tests.pytests.unit.utils.test_args import (
    _default,
    _defaults,
    _kwargs,
    _kwonly,
    _kwonly_reqs,
    _nodefault,
    _noparams,
    _posonly,
    _posonly_default,
    _posonly_default_no_regular,
)

log = logging.getLogger(__name__)


def _varargs(first, second=None, *args):
    return locals()


def _posonly_args(first, /, second, third="three", *args):
    return locals()


def _posonly_kwargs(first, second="two", /, third="three", **kwargs):
    return locals()


@pytest.mark.parametrize("in_kwargs", (False, True))
@pytest.mark.parametrize(
    "fun,args,kwargs,expected",
    (
        pytest.param(_noparams, [], {}, {}, id="no_params"),
        # Positional-or-keyword: positionally, by name, mixed
        pytest.param(
            _nodefault,
            [1, 2, 3],
            {},
            {"first": 1, "second": 2, "third": 3},
            id="posorkw_req_by_pos",
        ),
        pytest.param(
            _nodefault,
            [],
            {"first": 1, "second": 2, "third": 3},
            {"first": 1, "second": 2, "third": 3},
            id="posorkw_req_by_name",
        ),
        pytest.param(
            _nodefault,
            [1, 2],
            {"third": 3},
            {"first": 1, "second": 2, "third": 3},
            id="posorkw_req_by_mixed",
        ),
        # Defaults are applied, overridable positionally and by name
        pytest.param(
            _default,
            [1, 2],
            {},
            {"first": 1, "second": 2, "third": "3"},
            id="posorkw_default_preserved",
        ),
        pytest.param(
            _default,
            [1, 2, 4],
            {},
            {"first": 1, "second": 2, "third": 4},
            id="posorkw_default_override_by_name",
        ),
        pytest.param(
            _default,
            [1, 2],
            {"third": 4},
            {"first": 1, "second": 2, "third": 4},
            id="posorkw_default_override_by_pos",
        ),
        pytest.param(
            _default,
            [1],
            {"second": 2, "third": 4},
            {"first": 1, "second": 2, "third": 4},
            id="posorkw_req_by_mixed_default_override_by_name",
        ),
        # The first dict specifying a named argument wins
        pytest.param(
            _default,
            [1, 2, {"third": 31}, {"third": 32}],
            {},
            {"first": 1, "second": 2, "third": 31},
            id="named_param_first_arg_dict_wins",
        ),
        # A single dict can specify multiple named arguments
        pytest.param(
            _default,
            [{"first": 1, "second": 2, "third": 4}],
            {},
            {"first": 1, "second": 2, "third": 4},
            id="single_dict_multiple_kw",
        ),
        # Excess positional arguments flow into *args
        pytest.param(
            _varargs,
            [1, 2, 3, 4, 5],
            {},
            {"first": 1, "second": 2, "args": (3, 4, 5)},
            id="variadic_positional",
        ),
        # Unknown named arguments flow into **kwargs
        pytest.param(
            _kwargs,
            [1],
            {"second": 2, "third": 3, "fourth": 4, "fifth": 5},
            {"first": 1, "second": 2, "third": 3, "kwargs": {"fourth": 4, "fifth": 5}},
            id="variadic_kw",
        ),
        # Positional-only, required passed positionally and optional by name
        pytest.param(
            _posonly,
            [1],
            {"second": 2, "third": 3},
            {"first": 1, "second": 2, "third": 3, "fourth": 4},
            id="posonly_req_by_pos_default_override_by_name",
        ),
        # Positional-only defaults are applied ...
        pytest.param(
            _posonly_default,
            [1],
            {},
            {"first": 1, "second": "two", "third": "three"},
            id="posonly_req_by_pos_default_preserved",
        ),
        # ... overridable positionally ...
        pytest.param(
            _posonly_default,
            [1, 2, 3],
            {},
            {"first": 1, "second": 2, "third": 3},
            id="posonly_req_by_pos_default_override_by_pos",
        ),
        # ... and by name, in which case they are still passed positionally
        pytest.param(
            _posonly_default,
            [1],
            {"second": 2, "third": 3},
            {"first": 1, "second": 2, "third": 3},
            id="posonly_req_by_pos_default_override_by_name",
        ),
        pytest.param(
            _posonly_default_no_regular,
            [1],
            {"second": 22},
            {"first": 1, "second": 22},
            id="posonly_req_by_pos_default_override_by_name_no_poskw",
        ),
        pytest.param(
            _posonly_default_no_regular,
            [],
            {"first": 1},
            {"first": 1, "second": "two"},
            id="posonly_req_by_name_default_preserved_no_poskw",
        ),
        pytest.param(
            _posonly_default_no_regular,
            [1, 2],
            {},
            {"first": 1, "second": 2},
            id="posonly_req_by_pos_default_override_by_pos_no_poskw",
        ),
        # Positional-only combined with *args overflow
        pytest.param(
            _posonly_args,
            [1, 2, 3, 4, 5, 6],
            {},
            {"first": 1, "second": 2, "third": 3, "args": (4, 5, 6)},
            id="posonly_poskw_variadic_positional",
        ),
        # Everything by name, extras into **kwargs
        pytest.param(
            _posonly_kwargs,
            [],
            {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5},
            {"first": 1, "second": 2, "third": 3, "kwargs": {"fourth": 4, "fifth": 5}},
            id="posonly_req_default_poskw_variadic_keyword",
        ),
        # A named argument for an already filled positional-only slot goes
        # into **kwargs, mirroring Python calling conventions
        pytest.param(
            _posonly_kwargs,
            [1],
            {"first": 2},
            {"first": 1, "second": "two", "third": "three", "kwargs": {"first": 2}},
            id="posonly_req_by_pos_same_name_into_variadic_keyword",
        ),
        # Keyword-only arguments with *args/**kwargs present
        pytest.param(
            _kwonly,
            [1, 2, 3],
            {"second": 2, "third": 3, "fourth": 4},
            {
                "first": 1,
                "second": 2,
                "third": 3,
                "args": (2, 3),
                "kwargs": {"fourth": 4},
            },
            id="poskw_req_by_pos_variadic_positional_kwonly_req_variadic_keyword",
        ),
        pytest.param(
            _kwonly,
            [],
            {"first": 1, "second": 2},
            {"first": 1, "second": 2, "third": "three", "args": (), "kwargs": {}},
            id="poskw_req_by_name_kwonly_req_no_variadic_args",
        ),
        # Keyword-only arguments on a function without **kwargs
        pytest.param(
            _kwonly_reqs,
            [1],
            {"third": 3, "fourth": 4},
            {"first": 1, "second": None, "third": 3, "fourth": 4, "fifth": None},
            id="poskw_req_by_name_default_preserved_kwonly_req_default_override",
        ),
    ),
)
def test_call_function(fun, args, kwargs, expected, in_kwargs):
    if in_kwargs:
        pass_args = args
        pass_kwargs = kwargs
    else:
        pass_args = list(args) + list(dict((item,)) for item in kwargs.items())
        pass_kwargs = {}
    res = salt.utils.functools.call_function(fun, *pass_args, **pass_kwargs)
    assert res == expected


@pytest.mark.parametrize(
    "fun,args,kwargs,expected",
    (
        # Kwargs to `call_function` override named arguments passed as dicts
        pytest.param(
            _defaults,
            [{"first": 1}],
            {"first": 11},
            {"first": 11, "second": 2, "third": 3},
            id="override_poskw",
        ),
        pytest.param(
            _default,
            [1, 2, {"third": 3}],
            {"third": 4},
            {"first": 1, "second": 2, "third": 4},
            id="override_poskw_default",
        ),
        pytest.param(
            _posonly_default,
            [{"first": 1}],
            {"first": 11},
            {"first": 11, "second": "two", "third": "three"},
            id="override_posonly",
        ),
        pytest.param(
            _posonly_default,
            [1, {"second": 2}],
            {"second": 22},
            {"first": 1, "second": 22, "third": "three"},
            id="override_posonly_default",
        ),
        pytest.param(
            _kwonly,
            [1, {"second": 2}],
            {"second": 22},
            {"first": 1, "second": 22, "third": "three", "args": (), "kwargs": {}},
            id="override_kwonly",
        ),
        pytest.param(
            _kwonly,
            [1, {"second": 2}, {"third": 3}],
            {"third": 33},
            {"first": 1, "second": 2, "third": 33, "args": (), "kwargs": {}},
            id="override_kwonly_default",
        ),
    ),
)
def test_call_function_kwarg_overrides(fun, args, kwargs, expected):
    res = salt.utils.functools.call_function(fun, *args, **kwargs)
    assert res == expected


@pytest.mark.parametrize(
    "fun,args,kwargs,ctx",
    (
        # Too many positional arguments without *args to receive them
        pytest.param(
            _posonly,
            (1, 2, 3, 4, 5, 6),
            {},
            pytest.raises(
                SaltInvocationError, match=".*only takes 4 positional parameters, got 6"
            ),
            id="posonly_poskw_too_many_positional",
        ),
        # Missing required positional arguments
        pytest.param(
            _posonly,
            (1,),
            {},
            pytest.raises(
                SaltInvocationError, match="Missing arguments: second, third"
            ),
            id="posonly_req_poskw_req_missing",
        ),
        # Missing required keyword-only argument (singular message)
        pytest.param(
            _kwonly,
            (1,),
            {},
            pytest.raises(
                SaltInvocationError,
                match=r"_kwonly missing 1 required keyword-only argument: 'second'",
            ),
            id="kwonly_missing",
        ),
        # Missing required keyword-only arguments (plural message)
        pytest.param(
            _kwonly_reqs,
            (1,),
            {},
            pytest.raises(
                SaltInvocationError,
                match=r"_kwonly_reqs missing 2 required keyword-only arguments: 'third', 'fourth'",
            ),
            id="kwonly_missing_multi",
        ),
        # Positional-or-keyword argument passed both positionally and by name
        pytest.param(
            _posonly_kwargs,
            (1, 2, 3),
            {"first": "ends_up_in_kwargs", "third": "boom"},
            pytest.raises(
                SaltInvocationError,
                match=r"_posonly_kwargs\(\) got multiple values for argument 'third'",
            ),
            id="poskw_duplicate_arguments",
        ),
        # Positional-only arg passed both positionally and by name, without **kwargs
        pytest.param(
            _posonly_default,
            [1],
            {"first": 2},
            pytest.raises(
                SaltInvocationError,
                match=r"_posonly_default\(\) got multiple values for argument 'first'",
            ),
            id="posonly_duplicate_arguments",
        ),
        # Multiple duplicated arguments are reported together, without **kwargs
        # to route the positional-only one into
        pytest.param(
            _posonly,
            (1, 2, 3, 4),
            {"first": 11, "third": 33, "fourth": 44},
            pytest.raises(
                SaltInvocationError,
                match=r"_posonly\(\) got multiple values for arguments 'first', 'third', 'fourth'",
            ),
            id="posonly_and_poskw_duplicate_arguments_multi",
        ),
    ),
)
def test_call_function_exceptions(fun, args, kwargs, ctx):
    with ctx:
        salt.utils.functools.call_function(
            fun, *args, *(dict((item,)) for item in kwargs.items())
        )
