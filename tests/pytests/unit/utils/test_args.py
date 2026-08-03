import copy
import functools
import logging
import pickle

import pytest

import salt.utils.args
from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)


def test_condition_input_string():
    """
    Test passing a jid on the command line
    """
    cmd = salt.utils.args.condition_input(["*", "foo.bar", 20141020201325675584], None)
    assert isinstance(cmd[2], str)


def test_clean_kwargs():
    assert salt.utils.args.clean_kwargs(foo="bar") == {"foo": "bar"}
    assert salt.utils.args.clean_kwargs(__pub_foo="bar") == {}
    assert salt.utils.args.clean_kwargs(__foo_bar="gwar") == {}
    assert salt.utils.args.clean_kwargs(foo_bar="gwar") == {"foo_bar": "gwar"}


class _CallableClass:
    def __init__(self, first):
        pass

    def __call__(self, first):
        pass


def _noparams():
    return locals()


def _nodefault(first, second, third):
    return locals()


def _default(first, second, third="3"):
    return locals()


def _defaults(first, second=2, third=3):
    return locals()


def _alldefault(first=None, second=None, third=None):
    return locals()


def _varargs_keywords(*args, **kwargs):
    return locals()


def _annotations(first: int, second: str) -> bool:
    return locals()


def _kwargs(first, second=None, third=None, **kwargs):
    return locals()


def _posonly(first, second, /, third, fourth=4):
    return locals()


def _posonly_default(first, second="two", /, third="three"):
    return locals()


def _posonly_default_no_regular(first, second="two", /):
    return locals()


def _posonly_no_default(first, second, /):
    return locals()


def _kwonly(first, *args, second, third="three", **kwargs):
    return locals()


def _kwonly_req(first, second=None, *, third):
    return locals()


def _kwonly_reqs(first, second=None, *, third, fourth, fifth=None):
    return locals()


def _kwonly_no_pos(*, second, third="three"):
    return locals()


def _posonly_kwonly(first, /, *, second, third="three"):
    return locals()


def _all(
    first,
    second=None,
    /,
    third=3,
    *varargs,
    fourth,
    fifth,
    sixth="6",
    seventh=2.72,
    **kvarargs,
):
    return locals()


@pytest.mark.parametrize(
    "fun,expected",
    (
        # Callable class instance, inspected via __call__
        pytest.param(
            _CallableClass("foo"),
            {"args": ["first"], "argreq": ("first",)},
            id="callable_class",
        ),
        # Function without any parameters
        pytest.param(_noparams, {}, id="no_params"),
        # Positional-or-keyword parameters only, no defaults
        pytest.param(
            _nodefault,
            {
                "args": ["first", "second", "third"],
                "argreq": ("first", "second", "third"),
            },
            id="poskw_nodefault",
        ),
        # Positional-or-keyword parameters, one default
        pytest.param(
            _default,
            {
                "args": ["first", "second", "third"],
                "defaults": ("3",),
                "argreq": ("first", "second"),
                "kwdefaults": {"third": "3"},
                "argdefaults": {"third": "3"},
                "alldefaults": {"third": "3"},
            },
            id="poskw_default",
        ),
        # Annotations don't influence the spec
        pytest.param(
            _annotations,
            {"args": ["first", "second"], "argreq": ("first", "second")},
            id="annotations",
        ),
        # Variadic args/kwargs only
        pytest.param(
            _varargs_keywords,
            {"varargs": "args", "keywords": "kwargs"},
            id="args_kwargs_only",
        ),
        # Positional-only without defaults, mixed with positional-or-keyword
        pytest.param(
            _posonly,
            {
                "args": ["first", "second", "third", "fourth"],
                "defaults": (4,),
                "posonlyargs": ("first", "second"),
                "argreq": ("first", "second", "third"),
                "argdefaults": {"fourth": 4},
                "kwdefaults": {"fourth": 4},
                "alldefaults": {"fourth": 4},
            },
            id="posonly_req_poskw_default",
        ),
        # Positional-only without defaults and no other parameters
        pytest.param(
            _posonly_no_default,
            {
                "args": ["first", "second"],
                "posonlyargs": ("first", "second"),
                "argreq": ("first", "second"),
            },
            id="posonly_only_nodefault",
        ),
        # Positional-only with default, defaults spanning the `/` boundary
        pytest.param(
            _posonly_default,
            {
                "args": ["first", "second", "third"],
                "defaults": ("two", "three"),
                "posonlyargs": ("first", "second"),
                "argreq": ("first",),
                "argdefaults": {"second": "two", "third": "three"},
                "kwdefaults": {"third": "three"},
                "posonlydefaults": {"second": "two"},
                "alldefaults": {"second": "two", "third": "three"},
            },
            id="posonly_default_poskw_default",
        ),
        # Positional-only with default and no other parameters -
        # nothing can be passed a keyword argument
        pytest.param(
            _posonly_default_no_regular,
            {
                "args": ["first", "second"],
                "defaults": ("two",),
                "posonlyargs": ("first", "second"),
                "argreq": ("first",),
                "argdefaults": {"second": "two"},
                "kwdefaults": {},
                "posonlydefaults": {"second": "two"},
                "alldefaults": {"second": "two"},
            },
            id="posonly_only_default",
        ),
        # Keyword-only, required and with default, plus variadic args/kwargs
        pytest.param(
            _kwonly,
            {
                "args": ["first"],
                "varargs": "args",
                "keywords": "kwargs",
                "argreq": ("first",),
                "kwonlyargs": ("second", "third"),
                "kwonlyreq": ("second",),
                "kwonlydefaults": {"third": "three"},
                "kwdefaults": {"third": "three"},
                "alldefaults": {"third": "three"},
            },
            id="poskw_req_kwonly_req_and_default_args_kwargs",
        ),
        # Keyword-only without any positional parameters
        pytest.param(
            _kwonly_no_pos,
            {
                "kwonlyargs": ("second", "third"),
                "kwonlyreq": ("second",),
                "kwonlydefaults": {"third": "three"},
                "kwdefaults": {"third": "three"},
                "alldefaults": {"third": "three"},
            },
            id="kwonly_only_req_and_default",
        ),
        # Positional-only and keyword-only without positional-or-keyword ones
        pytest.param(
            _posonly_kwonly,
            {
                "args": ["first"],
                "posonlyargs": ("first",),
                "argreq": ("first",),
                "kwonlyargs": ("second", "third"),
                "kwonlyreq": ("second",),
                "kwonlydefaults": {"third": "three"},
                "kwdefaults": {"third": "three"},
                "alldefaults": {"third": "three"},
            },
            id="no_poskw",
        ),
        # All parameter kinds combined
        pytest.param(
            _all,
            {
                "args": ["first", "second", "third"],
                "varargs": "varargs",
                "keywords": "kvarargs",
                "defaults": (None, 3),
                "posonlyargs": ("first", "second"),
                "kwonlyargs": ("fourth", "fifth", "sixth", "seventh"),
                "kwonlydefaults": {"sixth": "6", "seventh": 2.72},
                "kwonlyreq": ("fourth", "fifth"),
                "argreq": ("first",),
                "argdefaults": {"second": None, "third": 3},
                "kwdefaults": {"third": 3, "sixth": "6", "seventh": 2.72},
                "posonlydefaults": {"second": None},
                "alldefaults": {
                    "second": None,
                    "third": 3,
                    "sixth": "6",
                    "seventh": 2.72,
                },
            },
            id="all_param_kinds",
        ),
    ),
)
def test_get_function_argspec(fun, expected):
    defaults = {
        "args": [],
        "varargs": None,
        "keywords": None,
        "defaults": None,
        "posonlyargs": (),
        "kwonlyargs": (),
        "kwonlydefaults": {},
        "kwonlyreq": (),
        "argreq": (),
        "argdefaults": {},
        "kwdefaults": {},
        "posonlydefaults": {},
        "alldefaults": {},
    }
    expected = defaults | expected
    spec = salt.utils.args.get_function_argspec(fun)
    for attr, exp in expected.items():
        assert getattr(spec, attr) == exp
    if expected["argdefaults"]:
        argdefault_order = list(spec.argdefaults)
        expected_order = expected["args"][-len(argdefault_order) :]
        assert argdefault_order == expected_order


def test_get_function_argspec_is_class_method():
    # Test that is_class_method=True is respected. Note that we don't
    # actually have a decorated function from rest_tornado here to test
    # this case, but we're testing for the behavior we expect, which is
    # that the first argument is popped off of the args.
    expected_argspec = salt.utils.args._ArgSpec(
        args=["second", "third"],
        varargs=None,
        keywords=None,
        defaults=None,
    )
    ret = salt.utils.args.get_function_argspec(_nodefault, is_class_method=True)
    assert ret == expected_argspec


def test_get_function_argspec_wrapped():
    """
    Wrappers with a ``__wrapped__`` attribute are unwrapped,
    the spec describes the innermost function.
    """

    @functools.wraps(_posonly_kwonly)
    def _wrapper(*args, **kwargs):
        return _posonly_kwonly(*args, **kwargs)

    spec = salt.utils.args.get_function_argspec(_wrapper)
    assert spec.args == ["first"]
    assert spec.posonlyargs == ("first",)
    assert spec.kwonlyargs == ("second", "third")
    assert spec.kwonlydefaults == {"third": "three"}


def test_get_function_argspec_not_callable():
    with pytest.raises(TypeError, match="is not a callable"):
        salt.utils.args.get_function_argspec("not_a_callable")


def test_get_function_argspec_copy_preserves_extras():
    """
    The extra attributes are not part of the tuple, ensure they survive
    copy/pickle roundtrips via __getnewargs__.
    """
    spec = salt.utils.args.get_function_argspec(_posonly_kwonly)
    for copied in (
        copy.copy(spec),
        copy.deepcopy(spec),
        pickle.loads(pickle.dumps(spec)),
    ):
        assert copied == spec
        assert copied.posonlyargs == spec.posonlyargs
        assert copied.kwonlyargs == spec.kwonlyargs
        assert copied.kwonlydefaults == spec.kwonlydefaults


def test_parse_kwarg():
    ret = salt.utils.args.parse_kwarg("foo=bar")
    assert ret == ("foo", "bar")

    ret = salt.utils.args.parse_kwarg("foobar")
    assert ret == (None, None)


def test_arg_lookup():
    expected_dict = {
        "args": ["first", "second"],
        "kwargs": {"third": "3"},
    }
    ret = salt.utils.args.arg_lookup(_default)
    assert ret == expected_dict

    # Keyword-only defaults are part of kwargs, positional-only
    # parameters of args
    expected_dict = {
        "args": ["first"],
        "kwargs": {"third": "three"},
    }
    ret = salt.utils.args.arg_lookup(_posonly_kwonly)
    assert ret == expected_dict


@pytest.mark.parametrize(
    "fun,data,exp_extra,expected",
    (
        # Positional-or-keyword: required passed positionally, defaults
        # overridden / partially overridden / fully materialized
        pytest.param(
            _defaults,
            {"first": 10, "second": 20, "third": 30},
            (),
            {"args": [10], "kwargs": {"second": 20, "third": 30}},
            id="poskw_default_override_full",
        ),
        pytest.param(
            _defaults,
            {"first": 10, "second": 20},
            (),
            {"args": [10], "kwargs": {"second": 20, "third": 3}},
            id="poskw_default_override_partial",
        ),
        pytest.param(
            _defaults,
            {"first": 10},
            (),
            {"args": [10], "kwargs": {"second": 2, "third": 3}},
            id="poskw_default_preserved",
        ),
        # expected_extra_kws that are absent from data are ignored
        pytest.param(
            _nodefault,
            {"first": 2, "second": 2, "third": 3},
            ("fourth", "fifth"),
            {"args": [2, 2, 3], "kwargs": {}},
            id="poskw_req_expected_extra_kws_irrelevant",
        ),
        pytest.param(
            _alldefault,
            {"first": 2, "second": 2, "third": 3},
            ("fourth", "fifth"),
            {"args": [], "kwargs": {"first": 2, "second": 2, "third": 3}},
            id="poskw_default_expected_extra_kws_irrelevant",
        ),
        # Extra data keys are packed into **kwargs
        pytest.param(
            _kwargs,
            {"first": 2, "second": 2, "third": 3, "fourth": 4},
            (),
            {"args": [2], "kwargs": {"second": 2, "third": 3, "fourth": 4}},
            id="kwargs_extra_kws_passed",
        ),
        # Extra data keys matching expected_extra_kws are excluded from **kwargs
        pytest.param(
            _kwargs,
            {"first": 2, "second": 2, "third": 3, "fourth": 4},
            ("fourth", "fifth"),
            {"args": [2], "kwargs": {"second": 2, "third": 3}},
            id="kwargs_expected_extra_kws_filtered",
        ),
        # Required keyword-only argument, remaining defaults materialized
        pytest.param(
            _kwonly_req,
            {"first": 1, "third": 3},
            (),
            {"args": [1], "kwargs": {"second": None, "third": 3}},
            id="poskw_req_and_default_preserved_kwonly_req",
        ),
        # expected_extra_kws don't shadow actual parameter names
        pytest.param(
            _kwonly_req,
            {"first": 1, "third": 3},
            ("second", "third"),
            {"args": [1], "kwargs": {"second": None, "third": 3}},
            id="expected_extra_kw_dont_shadow_params_poskw_kwonly",
        ),
        # Multiple required keyword-only arguments
        pytest.param(
            _kwonly_reqs,
            {"first": 1, "third": 3, "fourth": 4},
            (),
            {
                "args": [1],
                "kwargs": {"second": None, "third": 3, "fourth": 4, "fifth": None},
            },
            id="kwonly_req_multi",
        ),
        # Required positional-only arguments are bound by name,
        # but passed positionally
        pytest.param(
            _posonly,
            {"first": 1, "second": 2, "third": 3},
            (),
            {"args": [1, 2, 3], "kwargs": {"fourth": 4}},
            id="posonly_req_poskw_req_and_default_preserved",
        ),
        pytest.param(
            _posonly,
            {"first": 1, "second": 2, "third": 3},
            ("first", "second"),
            {"args": [1, 2, 3], "kwargs": {"fourth": 4}},
            id="expected_extra_kw_dont_shadow_params_posonly",
        ),
        # Positional-only default is materialized positionally
        pytest.param(
            _posonly_default,
            {"first": 1},
            (),
            {"args": [1, "two"], "kwargs": {"third": "three"}},
            id="posonly_req_and_default_preserved_poskw_default_preserved",
        ),
        # Positional-only default overridden by name, passed positionally
        pytest.param(
            _posonly_default,
            {"first": 1, "second": 22, "third": 33},
            (),
            {"args": [1, 22], "kwargs": {"third": 33}},
            id="posonly_req_and_default_override_poskw_default_override",
        ),
        # Positional-only only: defaults never end up in kwargs
        pytest.param(
            _posonly_default_no_regular,
            {"first": 1},
            (),
            {"args": [1, "two"], "kwargs": {}},
            id="posonly_req_and_default_preserved",
        ),
        pytest.param(
            _posonly_default_no_regular,
            {"first": 1, "second": 22},
            (),
            {"args": [1, 22], "kwargs": {}},
            id="posonly_req_and_default_override",
        ),
        # Keyword-only without positional parameters: defaults overridable
        pytest.param(
            _kwonly_no_pos,
            {"second": 2, "third": 33},
            (),
            {"args": [], "kwargs": {"second": 2, "third": 33}},
            id="kwonly_only_req_and_default_override",
        ),
        # ... and materialized when not supplied
        pytest.param(
            _kwonly_no_pos,
            {"second": 2},
            (),
            {"args": [], "kwargs": {"second": 2, "third": "three"}},
            id="kwonly_only_req_and_default_preserved",
        ),
        # Positional-only plus keyword-only, no positional-or-keyword ones
        pytest.param(
            _posonly_kwonly,
            {"first": 1, "second": 2, "third": 33},
            (),
            {"args": [1], "kwargs": {"second": 2, "third": 33}},
            id="posonly_req_kwonly_req_and_default_override",
        ),
        # All parameter kinds: extra data keys packed into **kwargs
        pytest.param(
            _all,
            {
                "first": 1,
                "second": 2,
                "fourth": 4,
                "fifth": 5,
                "seventh": 7,
                "eighth": 8,
                "ninth": 9,
            },
            (),
            {
                "args": [1, 2],
                "kwargs": {
                    "third": 3,
                    "fourth": 4,
                    "fifth": 5,
                    "sixth": "6",
                    "seventh": 7,
                    "eighth": 8,
                    "ninth": 9,
                },
            },
            id="all_param_kinds_extra_kws_passed",
        ),
        # All parameter kinds with expected_extra_kws filtering
        pytest.param(
            _all,
            {
                "first": 1,
                "second": 2,
                "fourth": 4,
                "fifth": 5,
                "seventh": 7,
                "eighth": 8,
                "ninth": 9,
            },
            ("eighth",),
            {
                "args": [1, 2],
                "kwargs": {
                    "third": 3,
                    "fourth": 4,
                    "fifth": 5,
                    "sixth": "6",
                    "seventh": 7,
                    "ninth": 9,
                },
            },
            id="all_param_kinds_expected_extra_kws_filtered",
        ),
    ),
)
def test_format_call(fun, data, exp_extra, expected):
    ret = salt.utils.args.format_call(fun, data, expected_extra_kws=exp_extra)
    assert ret == expected


@pytest.mark.parametrize(
    "func,args,ctx",
    (
        # Missing required positional-or-keyword argument (singular message)
        pytest.param(
            _defaults,
            {"second": 3},
            pytest.raises(
                SaltInvocationError,
                match=r"_defaults takes at least 1 argument \(0 given\). Missing: 'first'",
            ),
            id="posorkw_req_missing",
        ),
        # Missing required positional-or-keyword argument (plural message)
        pytest.param(
            _nodefault,
            {"first": 1},
            pytest.raises(
                SaltInvocationError,
                match=r"_nodefault takes at least 3 arguments \(1 given\). Missing: 'second', 'third'",
            ),
            id="posorkw_req_missing_multi",
        ),
        # Missing required positional-only argument counts as well
        pytest.param(
            _posonly,
            {"second": 2, "third": 3},
            pytest.raises(
                SaltInvocationError,
                match=r"_posonly takes at least 3 arguments \(2 given\). Missing: 'first'",
            ),
            id="posonly_posorkw_req_missing",
        ),
        # Unknown key in data without **kwargs to receive it (single)
        pytest.param(
            _alldefault,
            {"first": 2, "seconds": 2, "third": 3},
            pytest.raises(
                SaltInvocationError,
                match=r"'seconds' is an invalid keyword argument for.*_alldefault",
            ),
            id="unknown_kwarg",
        ),
        # Unknown keys in data without **kwargs to receive them (multiple)
        pytest.param(
            _alldefault,
            {"firsts": 2, "seconds": 2, "thirds": 3},
            pytest.raises(
                SaltInvocationError,
                match=r"'firsts', 'seconds' and 'thirds' are invalid keyword arguments for.*_alldefault",
            ),
            id="unknown_kwarg_multi",
        ),
        # Missing required keyword-only argument (singular message)
        pytest.param(
            _kwonly_req,
            {"first": 1},
            pytest.raises(
                SaltInvocationError,
                match=r"_kwonly_req missing 1 required keyword-only argument: 'third'",
            ),
            id="kwonly_req_missing",
        ),
        # Missing required keyword-only arguments (plural message)
        pytest.param(
            _kwonly_reqs,
            {"first": 1},
            pytest.raises(
                SaltInvocationError,
                match=r"_kwonly_reqs missing 2 required keyword-only arguments: 'third', 'fourth'",
            ),
            id="kwonly_req_missing_multi",
        ),
    ),
)
def test_format_call_exceptions(func, args, ctx):
    with ctx:
        salt.utils.args.format_call(func, args)


def test_argspec_report():
    test_functions = {"test_module.test_spec": _default}
    ret = salt.utils.args.argspec_report(test_functions, "test_module.test_spec")
    assert ret == {
        "test_module.test_spec": {
            "kwargs": None,
            "args": ["first", "second", "third"],
            "defaults": ("3",),
            "varargs": None,
            "posonlyargs": None,
            "kwonlyargs": None,
            "kwonlydefaults": None,
        }
    }


def test_test_mode():
    assert salt.utils.args.test_mode(test=True)
    assert salt.utils.args.test_mode(Test=True)
    assert salt.utils.args.test_mode(tEsT=True)


def test_parse_function_no_args():
    fun, args, kwargs = salt.utils.args.parse_function("amod.afunc()")
    assert fun == "amod.afunc"
    assert args == []
    assert kwargs == {}


def test_parse_function_args_only():
    fun, args, kwargs = salt.utils.args.parse_function("amod.afunc(str1, str2)")
    assert fun == "amod.afunc"
    assert args == ["str1", "str2"]
    assert kwargs == {}


def test_parse_function_kwargs_only():
    fun, args, kwargs = salt.utils.args.parse_function("amod.afunc(kw1=val1, kw2=val2)")
    assert fun == "amod.afunc"
    assert args == []
    assert kwargs == {"kw1": "val1", "kw2": "val2"}


def test_parse_function_args_kwargs():
    fun, args, kwargs = salt.utils.args.parse_function(
        "amod.afunc(str1, str2, kw1=val1, kw2=val2)"
    )
    assert fun == "amod.afunc"
    assert args == ["str1", "str2"]
    assert kwargs == {"kw1": "val1", "kw2": "val2"}


def test_parse_function_malformed_no_name():
    fun, args, kwargs = salt.utils.args.parse_function(
        "(str1, str2, kw1=val1, kw2=val2)"
    )
    assert fun is None
    assert args is None
    assert kwargs is None


def test_parse_function_malformed_not_fun_def():
    fun, args, kwargs = salt.utils.args.parse_function("foo bar, some=text")
    assert fun is None
    assert args is None
    assert kwargs is None


def test_parse_function_wrong_bracket_style():
    fun, args, kwargs = salt.utils.args.parse_function(
        "amod.afunc[str1, str2, kw1=val1, kw2=val2]"
    )
    assert fun is None
    assert args is None
    assert kwargs is None


def test_parse_function_brackets_unbalanced():
    fun, args, kwargs = salt.utils.args.parse_function(
        "amod.afunc(str1, str2, kw1=val1, kw2=val2"
    )
    assert fun is None
    assert args is None
    assert kwargs is None
    fun, args, kwargs = salt.utils.args.parse_function(
        "amod.afunc(str1, str2, kw1=val1, kw2=val2]"
    )
    assert fun is None
    assert args is None
    assert kwargs is None
    fun, args, kwargs = salt.utils.args.parse_function(
        "amod.afunc(str1, str2, kw1=(val1[val2)], kw2=val2)"
    )
    assert fun is None
    assert args is None
    assert kwargs is None


def test_parse_function_brackets_in_quotes():
    fun, args, kwargs = salt.utils.args.parse_function(
        'amod.afunc(str1, str2, kw1="(val1[val2)]", kw2=val2)'
    )
    assert fun == "amod.afunc"
    assert args == ["str1", "str2"]
    assert kwargs == {"kw1": "(val1[val2)]", "kw2": "val2"}


def test_parse_function_quotes():
    fun, args, kwargs = salt.utils.args.parse_function(
        "amod.afunc(\"double \\\" single '\", 'double \" single \\'',"
        ' kw1="equal=equal", kw2=val2)'
    )
    assert fun == "amod.afunc"
    assert args == ["double \" single '", "double \" single '"]
    assert kwargs == {"kw1": "equal=equal", "kw2": "val2"}


def test_yamlify_arg():
    """
    Test that we properly yamlify CLI input. In several of the tests below `is`
    is used instead of ==. This is because we want to confirm that the return
    value is not a copy of the original, but the same instance as the original.
    """

    def _yamlify_arg(item):
        log.debug("Testing yamlify_arg with %r", item)
        return salt.utils.args.yamlify_arg(item)

    # Make sure non-strings are just returned back
    for item in (True, False, None, 123, 45.67, ["foo"], {"foo": "bar"}):
        assert _yamlify_arg(item) is item

    # Make sure whitespace-only isn't loaded as None
    for item in ("", "\t", " "):
        assert _yamlify_arg(item) is item

    # This value would be loaded as an int (123), the underscores would be
    # ignored. Test that we identify this case and return the original
    # value.
    item = "1_2_3"
    assert _yamlify_arg(item) is item

    # The '#' is treated as a comment when not part of a data structure, we
    # don't want that behavior
    for item in ("# hash at beginning", "Hello world! # hash elsewhere"):
        assert _yamlify_arg(item) is item

    # However we _do_ want the # to be intact if it _is_ within a data
    # structure.
    item = '["foo", "bar", "###"]'
    assert _yamlify_arg(item) == ["foo", "bar", "###"]
    item = '{"foo": "###"}'
    assert _yamlify_arg(item) == {"foo": "###"}

    # The string "None" should load _as_ None
    assert _yamlify_arg("None") is None

    # Leading dashes, or strings containing colons, will result in lists
    # and dicts, and we only want to load lists and dicts when the strings
    # look like data structures.
    for item in ("- foo", "foo: bar"):
        assert _yamlify_arg(item) is item

    # Make sure we don't load '|' as ''
    item = "|"
    assert _yamlify_arg(item) is item

    # Make sure we don't load '!' as something else (None in 2018.3, '' in newer)
    item = "!"
    assert _yamlify_arg(item) is item

    # Make sure we load ints, floats, and strings correctly
    assert _yamlify_arg("123") == 123
    assert _yamlify_arg("45.67") == 45.67
    assert _yamlify_arg("foo") == "foo"

    # We tested list/dict loading above, but there is separate logic when
    # the string contains a '#', so we need to test again here.
    assert _yamlify_arg('["foo", "bar"]') == ["foo", "bar"]
    assert _yamlify_arg('{"foo": "bar"}') == {"foo": "bar"}

    # Make sure that an empty string is loaded properly.
    assert _yamlify_arg("   ") == "   "

    # Make sure that we don't improperly load strings that would be
    # interpreted by PyYAML as YAML document start/end.
    assert _yamlify_arg("---") == "---"
    assert _yamlify_arg("--- ") == "--- "
    assert _yamlify_arg("...") == "..."
    assert _yamlify_arg(" ...") == " ..."

    # Make sure that non-printable whitespace is not YAML-loaded
    assert _yamlify_arg("foo\t\nbar") == "foo\t\nbar"


def test_arguments_regex():
    argument_matches = (
        ("pip=1.1", ("pip", "1.1")),
        ("pip==1.1", None),
        ("pip=1.2=1", ("pip", "1.2=1")),
    )
    for argument, match in argument_matches:
        if match is None:
            assert salt.utils.args.KWARG_REGEX.match(argument) is None
        else:
            assert salt.utils.args.KWARG_REGEX.match(argument).groups() == match
