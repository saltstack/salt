"""
    :codeauthor: Bo Maryniuk (bo@suse.de)
    unit.utils.decorators_test
"""

import inspect

import salt.utils.decorators as decorators
from salt.exceptions import (
    CommandExecutionError,
    SaltConfigurationError,
    SaltInvocationError,
)
from salt.version import SaltStackVersion
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class DummyLogger:
    """
    Dummy logger accepts everything and simply logs
    """

    def __init__(self, messages):
        self._messages = messages

    def __getattr__(self, item):
        return self._log

    def _log(self, msg):
        self._messages.append(msg)


class DecoratorsTest(TestCase):
    """
    Testing decorators.
    """

    def old_function(self):
        return "old"

    def new_function(self):
        return "new"

    def _new_function(self):
        return "old"

    def _mk_version(self, name):
        """
        Make a version

        :return:
        """
        return name, SaltStackVersion.from_name(name)

    def arg_function(self, arg1=None, arg2=None, arg3=None):
        return "old"

    def setUp(self):
        """
        Setup a test
        :return:
        """
        self.globs = {
            "__virtualname__": "test",
            "__opts__": {},
            "__pillar__": {},
            "old_function": self.old_function,
            "new_function": self.new_function,
            "_new_function": self._new_function,
        }
        self.addCleanup(delattr, self, "globs")
        self.messages = list()
        self.addCleanup(delattr, self, "messages")
        patcher = patch.object(decorators, "log", DummyLogger(self.messages))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_is_deprecated_version_eol(self):
        """
        Use of is_deprecated will result to the exception,
        if the expiration version is lower than the current version.
        A successor function is not pointed out.

        :return:
        """
        depr = decorators.is_deprecated(self.globs, "Helium")
        depr._curr_version = self._mk_version("Beryllium")[1]
        with self.assertRaises(CommandExecutionError):
            depr(self.old_function)()
        self.assertEqual(
            self.messages, ['The lifetime of the function "old_function" expired.']
        )

    def test_is_deprecated_with_successor_eol(self):
        """
        Use of is_deprecated will result to the exception,
        if the expiration version is lower than the current version.
        A successor function is pointed out.

        :return:
        """
        depr = decorators.is_deprecated(
            self.globs, "Helium", with_successor="new_function"
        )
        depr._curr_version = self._mk_version("Beryllium")[1]
        with self.assertRaises(CommandExecutionError):
            depr(self.old_function)()
        self.assertEqual(
            self.messages,
            [
                'The lifetime of the function "old_function" expired. '
                'Please use its successor "new_function" instead.'
            ],
        )

    def test_is_deprecated(self):
        """
        Use of is_deprecated will result to the log message,
        if the expiration version is higher than the current version.
        A successor function is not pointed out.

        :return:
        """
        depr = decorators.is_deprecated(self.globs, "Beryllium")
        depr._curr_version = self._mk_version("Helium")[1]
        self.assertEqual(depr(self.old_function)(), self.old_function())
        self.assertEqual(
            self.messages,
            [
                'The function "old_function" is deprecated '
                'and will expire in version "Beryllium".'
            ],
        )

    def test_is_deprecated_with_successor(self):
        """
        Use of is_deprecated will result to the log message,
        if the expiration version is higher than the current version.
        A successor function is pointed out.

        :return:
        """
        depr = decorators.is_deprecated(
            self.globs, "Beryllium", with_successor="old_function"
        )
        depr._curr_version = self._mk_version("Helium")[1]
        self.assertEqual(depr(self.old_function)(), self.old_function())
        self.assertEqual(
            self.messages,
            [
                'The function "old_function" is deprecated '
                'and will expire in version "Beryllium". '
                'Use successor "old_function" instead.'
            ],
        )

    def test_with_deprecated_notfound(self):
        """
        Test with_deprecated should raise an exception, if a same name
        function with the "_" prefix not implemented.

        :return:
        """
        del self.globs["_new_function"]
        self.globs["__opts__"]["use_deprecated"] = ["test.new_function"]
        depr = decorators.with_deprecated(self.globs, "Beryllium")
        depr._curr_version = self._mk_version("Helium")[1]
        with self.assertRaises(CommandExecutionError):
            depr(self.new_function)()
        self.assertEqual(
            self.messages,
            [
                'The function "test.new_function" is using its deprecated '
                'version and will expire in version "Beryllium".'
            ],
        )

    def test_with_deprecated_notfound_in_pillar(self):
        """
        Test with_deprecated should raise an exception, if a same name
        function with the "_" prefix not implemented.

        :return:
        """
        del self.globs["_new_function"]
        self.globs["__pillar__"]["use_deprecated"] = ["test.new_function"]
        depr = decorators.with_deprecated(self.globs, "Beryllium")
        depr._curr_version = self._mk_version("Helium")[1]
        with self.assertRaises(CommandExecutionError):
            depr(self.new_function)()
        self.assertEqual(
            self.messages,
            [
                'The function "test.new_function" is using its deprecated '
                'version and will expire in version "Beryllium".'
            ],
        )

    def test_with_deprecated_found(self):
        """
        Test with_deprecated should not raise an exception, if a same name
        function with the "_" prefix is implemented, but should use
        an old version instead, if "use_deprecated" is requested.

        :return:
        """
        self.globs["__opts__"]["use_deprecated"] = ["test.new_function"]
        self.globs["_new_function"] = self.old_function
        depr = decorators.with_deprecated(self.globs, "Beryllium")
        depr._curr_version = self._mk_version("Helium")[1]
        self.assertEqual(depr(self.new_function)(), self.old_function())
        log_msg = [
            'The function "test.new_function" is using its deprecated version '
            'and will expire in version "Beryllium".'
        ]
        self.assertEqual(self.messages, log_msg)

    def test_with_deprecated_found_in_pillar(self):
        """
        Test with_deprecated should not raise an exception, if a same name
        function with the "_" prefix is implemented, but should use
        an old version instead, if "use_deprecated" is requested.

        :return:
        """
        self.globs["__pillar__"]["use_deprecated"] = ["test.new_function"]
        self.globs["_new_function"] = self.old_function
        depr = decorators.with_deprecated(self.globs, "Beryllium")
        depr._curr_version = self._mk_version("Helium")[1]
        self.assertEqual(depr(self.new_function)(), self.old_function())
        log_msg = [
            'The function "test.new_function" is using its deprecated version '
            'and will expire in version "Beryllium".'
        ]
        self.assertEqual(self.messages, log_msg)

    def test_with_deprecated_found_eol(self):
        """
        Test with_deprecated should raise an exception, if a same name
        function with the "_" prefix is implemented, "use_deprecated" is requested
        and EOL is reached.

        :return:
        """
        self.globs["__opts__"]["use_deprecated"] = ["test.new_function"]
        self.globs["_new_function"] = self.old_function
        depr = decorators.with_deprecated(self.globs, "Helium")
        depr._curr_version = self._mk_version("Beryllium")[1]
        with self.assertRaises(CommandExecutionError):
            depr(self.new_function)()
        self.assertEqual(
            self.messages,
            [
                'Although function "new_function" is called, an alias "new_function" is'
                " configured as its deprecated version. The lifetime of the function"
                ' "new_function" expired. Please use its successor "new_function"'
                " instead."
            ],
        )

    def test_with_deprecated_found_eol_in_pillar(self):
        """
        Test with_deprecated should raise an exception, if a same name
        function with the "_" prefix is implemented, "use_deprecated" is requested
        and EOL is reached.

        :return:
        """
        self.globs["__pillar__"]["use_deprecated"] = ["test.new_function"]
        self.globs["_new_function"] = self.old_function
        depr = decorators.with_deprecated(self.globs, "Helium")
        depr._curr_version = self._mk_version("Beryllium")[1]
        with self.assertRaises(CommandExecutionError):
            depr(self.new_function)()
        self.assertEqual(
            self.messages,
            [
                'Although function "new_function" is called, an alias "new_function" is'
                " configured as its deprecated version. The lifetime of the function"
                ' "new_function" expired. Please use its successor "new_function"'
                " instead."
            ],
        )

    def test_with_deprecated_no_conf(self):
        """
        Test with_deprecated should not raise an exception, if a same name
        function with the "_" prefix is implemented, but should use
        a new version instead, if "use_deprecated" is not requested.

        :return:
        """
        self.globs["_new_function"] = self.old_function
        depr = decorators.with_deprecated(self.globs, "Beryllium")
        depr._curr_version = self._mk_version("Helium")[1]
        self.assertEqual(depr(self.new_function)(), self.new_function())
        self.assertFalse(self.messages)

    def test_with_deprecated_with_name(self):
        """
        Test with_deprecated should not raise an exception, if a different name
        function is implemented and specified with the "with_name" parameter,
        but should use an old version instead and log a warning log message.

        :return:
        """
        self.globs["__opts__"]["use_deprecated"] = ["test.new_function"]
        depr = decorators.with_deprecated(
            self.globs, "Beryllium", with_name="old_function"
        )
        depr._curr_version = self._mk_version("Helium")[1]
        self.assertEqual(depr(self.new_function)(), self.old_function())
        self.assertEqual(
            self.messages,
            [
                'The function "old_function" is deprecated and will expire in version'
                ' "Beryllium". Use its successor "new_function" instead.'
            ],
        )

    def test_with_deprecated_with_name_eol(self):
        """
        Test with_deprecated should raise an exception, if a different name
        function is implemented and specified with the "with_name" parameter
        and EOL is reached.

        :return:
        """
        self.globs["__opts__"]["use_deprecated"] = ["test.new_function"]
        depr = decorators.with_deprecated(
            self.globs, "Helium", with_name="old_function"
        )
        depr._curr_version = self._mk_version("Beryllium")[1]
        with self.assertRaises(CommandExecutionError):
            depr(self.new_function)()
        self.assertEqual(
            self.messages,
            [
                'Although function "new_function" is called, '
                'an alias "old_function" is configured as its deprecated version. '
                'The lifetime of the function "old_function" expired. '
                'Please use its successor "new_function" instead.'
            ],
        )

    def test_with_deprecated_opt_in_default(self):
        """
        Test with_deprecated using opt-in policy,
        where newer function is not used, unless configured.

        :return:
        """
        depr = decorators.with_deprecated(
            self.globs, "Beryllium", policy=decorators._DeprecationDecorator.OPT_IN
        )
        depr._curr_version = self._mk_version("Helium")[1]
        assert depr(self.new_function)() == self.old_function()
        assert self.messages == [
            'The function "test.new_function" is using its '
            'deprecated version and will expire in version "Beryllium".'
        ]

    def test_with_deprecated_opt_in_use_superseded(self):
        """
        Test with_deprecated using opt-in policy,
        where newer function is used as per configuration.

        :return:
        """
        self.globs["__opts__"]["use_superseded"] = ["test.new_function"]
        depr = decorators.with_deprecated(
            self.globs, "Beryllium", policy=decorators._DeprecationDecorator.OPT_IN
        )
        depr._curr_version = self._mk_version("Helium")[1]
        assert depr(self.new_function)() == self.new_function()
        assert not self.messages

    def test_with_deprecated_opt_in_use_superseded_in_pillar(self):
        """
        Test with_deprecated using opt-in policy,
        where newer function is used as per configuration.

        :return:
        """
        self.globs["__pillar__"]["use_superseded"] = ["test.new_function"]
        depr = decorators.with_deprecated(
            self.globs, "Beryllium", policy=decorators._DeprecationDecorator.OPT_IN
        )
        depr._curr_version = self._mk_version("Helium")[1]
        assert depr(self.new_function)() == self.new_function()
        assert not self.messages

    def test_with_deprecated_opt_in_use_superseded_and_deprecated(self):
        """
        Test with_deprecated misconfiguration.

        :return:
        """
        self.globs["__opts__"]["use_deprecated"] = ["test.new_function"]
        self.globs["__opts__"]["use_superseded"] = ["test.new_function"]
        depr = decorators.with_deprecated(self.globs, "Beryllium")
        depr._curr_version = self._mk_version("Helium")[1]
        with self.assertRaises(SaltConfigurationError):
            assert depr(self.new_function)() == self.new_function()

    def test_with_deprecated_opt_in_use_superseded_and_deprecated_in_pillar(self):
        """
        Test with_deprecated misconfiguration.

        :return:
        """
        self.globs["__pillar__"]["use_deprecated"] = ["test.new_function"]
        self.globs["__pillar__"]["use_superseded"] = ["test.new_function"]
        depr = decorators.with_deprecated(self.globs, "Beryllium")
        depr._curr_version = self._mk_version("Helium")[1]
        with self.assertRaises(SaltConfigurationError):
            assert depr(self.new_function)() == self.new_function()

    def test_allow_one_of(self):
        """
        Test allow_one_of properly does not error when only one of the
        required arguments is passed.

        :return:
        """
        allow_one_of = decorators.allow_one_of("arg1", "arg2", "arg3")
        assert allow_one_of(self.arg_function)(arg1="good") == self.arg_function(
            arg1="good"
        )

    def test_allow_one_of_succeeds_when_no_arguments_supplied(self):
        """
        Test allow_one_of properly does not error when none of the allowed
        arguments are supplied.

        :return:
        """
        allow_one_of = decorators.allow_one_of("arg1", "arg2", "arg3")
        assert allow_one_of(self.arg_function)() == self.arg_function()

    def test_allow_one_of_raises_error_when_multiple_allowed_arguments_supplied(self):
        """
        Test allow_one_of properly does not error when only one of the
        required arguments is passed.

        :return:
        """
        allow_one_of = decorators.allow_one_of("arg1", "arg2", "arg3")
        with self.assertRaises(SaltInvocationError):
            allow_one_of(self.arg_function)(arg1="good", arg2="bad")

    def test_require_one_of(self):
        """
        Test require_one_of properly does not error when only one of the
        required arguments is passed.

        :return:
        """
        require_one_of = decorators.require_one_of("arg1", "arg2", "arg3")
        assert require_one_of(self.arg_function)(arg1="good") == self.arg_function(
            arg1="good"
        )

    def test_require_one_of_raises_error_when_none_of_allowed_arguments_supplied(self):
        """
        Test require_one_of properly raises an error when none of the required
        arguments are supplied.

        :return:
        """
        require_one_of = decorators.require_one_of("arg1", "arg2", "arg3")
        with self.assertRaises(SaltInvocationError):
            require_one_of(self.arg_function)()

    def test_require_one_of_raises_error_when_multiple_allowed_arguments_supplied(self):
        """
        Test require_one_of properly raises an error when multiples of the
        allowed arguments are supplied.

        :return:
        """
        require_one_of = decorators.require_one_of("arg1", "arg2", "arg3")
        with self.assertRaises(SaltInvocationError):
            require_one_of(self.new_function)(arg1="good", arg2="bad")

    def test_with_depreciated_should_wrap_function(self):
        wrapped = decorators.with_deprecated({}, "Beryllium")(self.old_function)
        assert wrapped.__module__ == self.old_function.__module__

    def test_is_deprecated_should_wrap_function(self):
        wrapped = decorators.is_deprecated({}, "Beryllium")(self.old_function)
        assert wrapped.__module__ == self.old_function.__module__

    def test_ensure_unicode_args_should_wrap_function(self):
        wrapped = decorators.ensure_unicode_args(self.old_function)
        assert wrapped.__module__ == self.old_function.__module__

    def test_ignores_kwargs_should_wrap_function(self):
        wrapped = decorators.ignores_kwargs("foo", "bar")(self.old_function)
        assert wrapped.__module__ == self.old_function.__module__

    def test_memoize_should_wrap_function(self):
        wrapped = decorators.memoize(self.old_function)
        assert wrapped.__module__ == self.old_function.__module__

    def timing_should_wrap_function(self):
        wrapped = decorators.timing(self.old_function)
        assert wrapped.__module__ == self.old_function.__module__


class DependsDecoratorTest(TestCase):
    def function(self):
        return "foo"

    def test_depends_get_previous_frame(self):
        """
        Confirms that we're not grabbing the entire stack every time the
        depends decorator is invoked.
        """
        # Simply using True as a conditon; we aren't testing the dependency,
        # but rather the functions called within the decorator.
        dep = decorators.depends(True)

        # By mocking both inspect.stack and inspect.currentframe with
        # MagicMocks that return themselves, we don't affect normal operation
        # of the decorator, and at the same time we get to peek at whether or
        # not either was called.
        stack_mock = MagicMock(return_value=inspect.stack)
        currentframe_mock = MagicMock(return_value=inspect.currentframe)

        with patch.object(inspect, "stack", stack_mock), patch.object(
            inspect, "currentframe", currentframe_mock
        ):
            dep(self.function)()

        stack_mock.assert_not_called()
        currentframe_mock.assert_called_once_with()
