# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
from collections import namedtuple

import salt.utils.args

# Import Salt Libs
from salt.exceptions import SaltInvocationError
from salt.ext import six
from tests.support.mock import DEFAULT, patch

# Import Salt Testing Libs
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class ArgsTestCase(TestCase):
    """
    TestCase for salt.utils.args module
    """

    def test_condition_input_string(self):
        """
        Test passing a jid on the command line
        """
        cmd = salt.utils.args.condition_input(
            ["*", "foo.bar", 20141020201325675584], None
        )
        self.assertIsInstance(cmd[2], six.text_type)

    def test_clean_kwargs(self):
        self.assertDictEqual(salt.utils.args.clean_kwargs(foo="bar"), {"foo": "bar"})
        self.assertDictEqual(salt.utils.args.clean_kwargs(__pub_foo="bar"), {})
        self.assertDictEqual(salt.utils.args.clean_kwargs(__foo_bar="gwar"), {})
        self.assertDictEqual(
            salt.utils.args.clean_kwargs(foo_bar="gwar"), {"foo_bar": "gwar"}
        )

    def test_get_function_argspec(self):
        def dummy_func(first, second, third, fourth="fifth"):
            pass

        expected_argspec = namedtuple("ArgSpec", "args varargs keywords defaults")(
            args=["first", "second", "third", "fourth"],
            varargs=None,
            keywords=None,
            defaults=("fifth",),
        )
        ret = salt.utils.args.get_function_argspec(dummy_func)

        self.assertEqual(ret, expected_argspec)

    def test_parse_kwarg(self):
        ret = salt.utils.args.parse_kwarg("foo=bar")
        self.assertEqual(ret, ("foo", "bar"))

        ret = salt.utils.args.parse_kwarg("foobar")
        self.assertEqual(ret, (None, None))

    def test_arg_lookup(self):
        def dummy_func(first, second, third, fourth="fifth"):
            pass

        expected_dict = {
            "args": ["first", "second", "third"],
            "kwargs": {"fourth": "fifth"},
        }
        ret = salt.utils.args.arg_lookup(dummy_func)
        self.assertEqual(expected_dict, ret)

    def test_format_call(self):
        with patch("salt.utils.args.arg_lookup") as arg_lookup:

            def dummy_func(first=None, second=None, third=None):
                pass

            arg_lookup.return_value = {
                "args": ["first", "second", "third"],
                "kwargs": {},
            }
            get_function_argspec = DEFAULT
            get_function_argspec.return_value = namedtuple(
                "ArgSpec", "args varargs keywords defaults"
            )(
                args=["first", "second", "third", "fourth"],
                varargs=None,
                keywords=None,
                defaults=("fifth",),
            )

            # Make sure we raise an error if we don't pass in the requisite number of arguments
            self.assertRaises(
                SaltInvocationError, salt.utils.args.format_call, dummy_func, {"1": 2}
            )

            # Make sure we warn on invalid kwargs
            self.assertRaises(
                SaltInvocationError,
                salt.utils.args.format_call,
                dummy_func,
                {"first": 2, "seconds": 2, "third": 3},
            )

            ret = salt.utils.args.format_call(
                dummy_func,
                {"first": 2, "second": 2, "third": 3},
                expected_extra_kws=("first", "second", "third"),
            )
            self.assertDictEqual(ret, {"args": [], "kwargs": {}})

    def test_format_call_simple_args(self):
        def foo(one, two=2, three=3):
            pass

        self.assertEqual(
            salt.utils.args.format_call(foo, dict(one=10, two=20, three=30)),
            {"args": [10], "kwargs": dict(two=20, three=30)},
        )
        self.assertEqual(
            salt.utils.args.format_call(foo, dict(one=10, two=20)),
            {"args": [10], "kwargs": dict(two=20, three=3)},
        )
        self.assertEqual(
            salt.utils.args.format_call(foo, dict(one=2)),
            {"args": [2], "kwargs": dict(two=2, three=3)},
        )

    def test_format_call_mimic_typeerror_exceptions(self):
        def foo(one, two=2, three=3):
            pass

        def foo2(one, two, three=3):
            pass

        with self.assertRaisesRegex(
            SaltInvocationError, r"foo takes at least 1 argument \(0 given\)"
        ):
            salt.utils.args.format_call(foo, dict(two=3))

        with self.assertRaisesRegex(
            TypeError, r"foo2 takes at least 2 arguments \(1 given\)"
        ):
            salt.utils.args.format_call(foo2, dict(one=1))

    def test_argspec_report(self):
        def _test_spec(arg1, arg2, kwarg1=None):
            pass

        test_functions = {"test_module.test_spec": _test_spec}
        ret = salt.utils.args.argspec_report(test_functions, "test_module.test_spec")
        self.assertDictEqual(
            ret,
            {
                "test_module.test_spec": {
                    "kwargs": None,
                    "args": ["arg1", "arg2", "kwarg1"],
                    "defaults": (None,),
                    "varargs": None,
                }
            },
        )

    def test_test_mode(self):
        self.assertTrue(salt.utils.args.test_mode(test=True))
        self.assertTrue(salt.utils.args.test_mode(Test=True))
        self.assertTrue(salt.utils.args.test_mode(tEsT=True))

    def test_parse_function_no_args(self):
        fun, args, kwargs = salt.utils.args.parse_function("amod.afunc()")
        self.assertEqual(fun, "amod.afunc")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {})

    def test_parse_function_args_only(self):
        fun, args, kwargs = salt.utils.args.parse_function("amod.afunc(str1, str2)")
        self.assertEqual(fun, "amod.afunc")
        self.assertEqual(args, ["str1", "str2"])
        self.assertEqual(kwargs, {})

    def test_parse_function_kwargs_only(self):
        fun, args, kwargs = salt.utils.args.parse_function(
            "amod.afunc(kw1=val1, kw2=val2)"
        )
        self.assertEqual(fun, "amod.afunc")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"kw1": "val1", "kw2": "val2"})

    def test_parse_function_args_kwargs(self):
        fun, args, kwargs = salt.utils.args.parse_function(
            "amod.afunc(str1, str2, kw1=val1, kw2=val2)"
        )
        self.assertEqual(fun, "amod.afunc")
        self.assertEqual(args, ["str1", "str2"])
        self.assertEqual(kwargs, {"kw1": "val1", "kw2": "val2"})

    def test_parse_function_malformed_no_name(self):
        fun, args, kwargs = salt.utils.args.parse_function(
            "(str1, str2, kw1=val1, kw2=val2)"
        )
        self.assertIsNone(fun)
        self.assertIsNone(args)
        self.assertIsNone(kwargs)

    def test_parse_function_malformed_not_fun_def(self):
        fun, args, kwargs = salt.utils.args.parse_function("foo bar, some=text")
        self.assertIsNone(fun)
        self.assertIsNone(args)
        self.assertIsNone(kwargs)

    def test_parse_function_wrong_bracket_style(self):
        fun, args, kwargs = salt.utils.args.parse_function(
            "amod.afunc[str1, str2, kw1=val1, kw2=val2]"
        )
        self.assertIsNone(fun)
        self.assertIsNone(args)
        self.assertIsNone(kwargs)

    def test_parse_function_brackets_unballanced(self):
        fun, args, kwargs = salt.utils.args.parse_function(
            "amod.afunc(str1, str2, kw1=val1, kw2=val2"
        )
        self.assertIsNone(fun)
        self.assertIsNone(args)
        self.assertIsNone(kwargs)
        fun, args, kwargs = salt.utils.args.parse_function(
            "amod.afunc(str1, str2, kw1=val1, kw2=val2]"
        )
        self.assertIsNone(fun)
        self.assertIsNone(args)
        self.assertIsNone(kwargs)
        fun, args, kwargs = salt.utils.args.parse_function(
            "amod.afunc(str1, str2, kw1=(val1[val2)], kw2=val2)"
        )
        self.assertIsNone(fun)
        self.assertIsNone(args)
        self.assertIsNone(kwargs)

    def test_parse_function_brackets_in_quotes(self):
        fun, args, kwargs = salt.utils.args.parse_function(
            'amod.afunc(str1, str2, kw1="(val1[val2)]", kw2=val2)'
        )
        self.assertEqual(fun, "amod.afunc")
        self.assertEqual(args, ["str1", "str2"])
        self.assertEqual(kwargs, {"kw1": "(val1[val2)]", "kw2": "val2"})

    def test_parse_function_quotes(self):
        fun, args, kwargs = salt.utils.args.parse_function(
            'amod.afunc("double \\" single \'", \'double " single \\\'\', kw1="equal=equal", kw2=val2)'
        )
        self.assertEqual(fun, "amod.afunc")
        self.assertEqual(args, ["double \" single '", "double \" single '"])
        self.assertEqual(kwargs, {"kw1": "equal=equal", "kw2": "val2"})

    def test_yamlify_arg(self):
        """
        Test that we properly yamlify CLI input. In several of the tests below
        assertIs is used instead of assertEqual. This is because we want to
        confirm that the return value is not a copy of the original, but the
        same instance as the original.
        """

        def _yamlify_arg(item):
            log.debug("Testing yamlify_arg with %r", item)
            return salt.utils.args.yamlify_arg(item)

        # Make sure non-strings are just returned back
        for item in (True, False, None, 123, 45.67, ["foo"], {"foo": "bar"}):
            self.assertIs(_yamlify_arg(item), item)

        # Make sure whitespace-only isn't loaded as None
        for item in ("", "\t", " "):
            self.assertIs(_yamlify_arg(item), item)

        # This value would be loaded as an int (123), the underscores would be
        # ignored. Test that we identify this case and return the original
        # value.
        item = "1_2_3"
        self.assertIs(_yamlify_arg(item), item)

        # The '#' is treated as a comment when not part of a data structure, we
        # don't want that behavior
        for item in ("# hash at beginning", "Hello world! # hash elsewhere"):
            self.assertIs(_yamlify_arg(item), item)

        # However we _do_ want the # to be intact if it _is_ within a data
        # structure.
        item = '["foo", "bar", "###"]'
        self.assertEqual(_yamlify_arg(item), ["foo", "bar", "###"])
        item = '{"foo": "###"}'
        self.assertEqual(_yamlify_arg(item), {"foo": "###"})

        # The string "None" should load _as_ None
        self.assertIs(_yamlify_arg("None"), None)

        # Leading dashes, or strings containing colons, will result in lists
        # and dicts, and we only want to load lists and dicts when the strings
        # look like data structures.
        for item in ("- foo", "foo: bar"):
            self.assertIs(_yamlify_arg(item), item)

        # Make sure we don't load '|' as ''
        item = "|"
        self.assertIs(_yamlify_arg(item), item)

        # Make sure we don't load '!' as something else (None in 2018.3, '' in newer)
        item = "!"
        self.assertIs(_yamlify_arg(item), item)

        # Make sure we load ints, floats, and strings correctly
        self.assertEqual(_yamlify_arg("123"), 123)
        self.assertEqual(_yamlify_arg("45.67"), 45.67)
        self.assertEqual(_yamlify_arg("foo"), "foo")

        # We tested list/dict loading above, but there is separate logic when
        # the string contains a '#', so we need to test again here.
        self.assertEqual(_yamlify_arg('["foo", "bar"]'), ["foo", "bar"])
        self.assertEqual(_yamlify_arg('{"foo": "bar"}'), {"foo": "bar"})


class KwargRegexTest(TestCase):
    def test_arguments_regex(self):
        argument_matches = (
            ("pip=1.1", ("pip", "1.1")),
            ("pip==1.1", None),
            ("pip=1.2=1", ("pip", "1.2=1")),
        )
        for argument, match in argument_matches:
            if match is None:
                self.assertIsNone(salt.utils.args.KWARG_REGEX.match(argument))
            else:
                self.assertEqual(
                    salt.utils.args.KWARG_REGEX.match(argument).groups(), match
                )
