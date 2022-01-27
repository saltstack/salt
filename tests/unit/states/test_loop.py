"""
Tests for loop state(s)
"""

import pytest
import salt.states.loop
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class LoopTestCase(TestCase, LoaderModuleMockMixin):

    mock = MagicMock(return_value=True)
    func = "foo.bar"
    m_args = ["foo", "bar", "baz"]
    m_kwargs = {"hello": "world"}
    condition = "m_ret is True"
    period = 1
    timeout = 3

    def setup_loader_modules(self):
        return {
            salt.states.loop: {
                "__opts__": {"test": False},
                "__salt__": {self.func: self.mock},
            }
        }

    def setUp(self):
        self.mock.reset_mock()

    def test_until(self):
        ret = salt.states.loop.until(
            name=self.func,
            m_args=self.m_args,
            m_kwargs=self.m_kwargs,
            condition=self.condition,
            period=self.period,
            timeout=self.timeout,
        )
        assert ret["result"] is True
        self.mock.assert_called_once_with(*self.m_args, **self.m_kwargs)

    def test_until_without_args(self):
        ret = salt.states.loop.until(
            name=self.func,
            m_kwargs=self.m_kwargs,
            condition=self.condition,
            period=self.period,
            timeout=self.timeout,
        )
        assert ret["result"] is True
        self.mock.assert_called_once_with(**self.m_kwargs)

    def test_until_without_kwargs(self):
        ret = salt.states.loop.until(
            name=self.func,
            m_args=self.m_args,
            condition=self.condition,
            period=self.period,
            timeout=self.timeout,
        )
        assert ret["result"] is True
        self.mock.assert_called_once_with(*self.m_args)

    def test_until_without_args_or_kwargs(self):
        ret = salt.states.loop.until(
            name=self.func,
            condition=self.condition,
            period=self.period,
            timeout=self.timeout,
        )
        assert ret["result"] is True
        self.mock.assert_called_once_with()


class LoopTestCaseNoEval(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.loop
    """

    def setup_loader_modules(self):
        opts = salt.config.DEFAULT_MINION_OPTS.copy()
        utils = salt.loader.utils(opts)
        return {salt.states.loop: {"__opts__": opts, "__utils__": utils}}

    def test_test_mode(self):
        """
        Test response when test_mode is enabled.
        """
        with patch.dict(
            salt.states.loop.__salt__, {"foo.foo": True}  # pylint: disable=no-member
        ), patch.dict(
            salt.states.loop.__opts__, {"test": True}  # pylint: disable=no-member
        ):
            self.assertDictEqual(
                salt.states.loop.until(name="foo.foo", condition="m_ret"),
                {
                    "name": "foo.foo",
                    "result": None,
                    "changes": {},
                    "comment": "The execution module foo.foo will be run",
                },
            )
            self.assertDictEqual(
                salt.states.loop.until_no_eval(name="foo.foo", expected=2),
                {
                    "name": "foo.foo",
                    "result": None,
                    "changes": {},
                    "comment": 'Would have waited for "foo.foo" to produce "2".',
                },
            )

    @pytest.mark.slow_test
    def test_immediate_success(self):
        """
        Test for an immediate success.
        """
        with patch.dict(
            salt.states.loop.__salt__,
            {  # pylint: disable=no-member
                "foo.foo": lambda: 2,
                "foo.baz": lambda x, y: True,
            },
        ), patch.dict(
            salt.states.loop.__utils__,
            {"foo.baz": lambda x, y: True},  # pylint: disable=no-member
        ):
            self.assertDictEqual(
                salt.states.loop.until(name="foo.foo", condition="m_ret"),
                {
                    "name": "foo.foo",
                    "result": True,
                    "changes": {},
                    "comment": "Condition m_ret was met",
                },
            )
            # Using default compare_operator 'eq'
            self.assertDictEqual(
                salt.states.loop.until_no_eval(name="foo.foo", expected=2),
                {
                    "name": "foo.foo",
                    "result": True,
                    "changes": {},
                    "comment": "Call provided the expected results in 1 attempts",
                },
            )
            # Using compare_operator 'gt'
            self.assertDictEqual(
                salt.states.loop.until_no_eval(
                    name="foo.foo", expected=1, compare_operator="gt"  # Returns 2
                ),
                {
                    "name": "foo.foo",
                    "result": True,
                    "changes": {},
                    "comment": "Call provided the expected results in 1 attempts",
                },
            )
            # Using compare_operator 'ne'
            self.assertDictEqual(
                salt.states.loop.until_no_eval(
                    name="foo.foo", expected=3, compare_operator="ne"  # Returns 2
                ),
                {
                    "name": "foo.foo",
                    "result": True,
                    "changes": {},
                    "comment": "Call provided the expected results in 1 attempts",
                },
            )
            # Using __utils__['foo.baz'] as compare_operator
            self.assertDictEqual(
                salt.states.loop.until_no_eval(
                    name="foo.foo",
                    expected="anything, mocked compare_operator returns True anyway",
                    compare_operator="foo.baz",
                ),
                {
                    "name": "foo.foo",
                    "result": True,
                    "changes": {},
                    "comment": "Call provided the expected results in 1 attempts",
                },
            )
            # Using __salt__['foo.baz]' as compare_operator
            self.assertDictEqual(
                salt.states.loop.until_no_eval(
                    name="foo.foo",
                    expected="anything, mocked compare_operator returns True anyway",
                    compare_operator="foo.baz",
                ),
                {
                    "name": "foo.foo",
                    "result": True,
                    "changes": {},
                    "comment": "Call provided the expected results in 1 attempts",
                },
            )

    def test_immediate_failure(self):
        """
        Test for an immediate failure.
        Period and timeout will be set to 0.01 to assume one attempt.
        """
        with patch.dict(
            salt.states.loop.__salt__, {"foo.bar": lambda: False}
        ):  # pylint: disable=no-member
            self.assertDictEqual(
                salt.states.loop.until(
                    name="foo.bar", condition="m_ret", period=0.01, timeout=0.01
                ),
                {
                    "name": "foo.bar",
                    "result": False,
                    "changes": {},
                    "comment": "Timed out while waiting for condition m_ret",
                },
            )

            self.assertDictEqual(
                salt.states.loop.until_no_eval(
                    name="foo.bar", expected=True, period=0.01, timeout=0.01
                ),
                {
                    "name": "foo.bar",
                    "result": False,
                    "changes": {},
                    "comment": (
                        "Call did not produce the expected result after 1 attempts"
                    ),
                },
            )

    def test_eval_exceptions(self):
        """
        Test a couple of eval exceptions.
        """
        with patch.dict(
            salt.states.loop.__salt__, {"foo.bar": lambda: None}
        ):  # pylint: disable=no-member
            self.assertRaises(
                SyntaxError,
                salt.states.loop.until,
                name="foo.bar",
                condition='raise NameError("FOO")',
            )
            self.assertRaises(
                NameError, salt.states.loop.until, name="foo.bar", condition="foo"
            )

    def test_no_eval_exceptions(self):
        """
        Test exception handling in until_no_eval.
        """
        with patch.dict(
            salt.states.loop.__salt__,  # pylint: disable=no-member
            {"foo.bar": MagicMock(side_effect=KeyError("FOO"))},
        ):
            self.assertDictEqual(
                salt.states.loop.until_no_eval(name="foo.bar", expected=True),
                {
                    "name": "foo.bar",
                    "result": False,
                    "changes": {},
                    "comment": (
                        "Exception occurred while executing foo.bar: {}:{}".format(
                            type(KeyError()), "'FOO'"
                        )
                    ),
                },
            )

    def test_retried_success(self):
        """
        Test if the function does indeed return after a fixed amount of retries.

        Note: Do not merge these two tests in one with-block, as the side_effect
        iterator is shared.
        """
        with patch.dict(
            salt.states.loop.__salt__,  # pylint: disable=no-member
            {
                "foo.bar": MagicMock(side_effect=range(1, 7))
            },  # pylint: disable=incompatible-py3-code
        ):
            self.assertDictEqual(
                salt.states.loop.until(
                    name="foo.bar", condition="m_ret == 5", period=0, timeout=1
                ),
                {
                    "name": "foo.bar",
                    "result": True,
                    "changes": {},
                    "comment": "Condition m_ret == 5 was met",
                },
            )

        with patch.dict(
            salt.states.loop.__salt__,  # pylint: disable=no-member
            {
                "foo.bar": MagicMock(side_effect=range(1, 7))
            },  # pylint: disable=incompatible-py3-code
        ):
            self.assertDictEqual(
                salt.states.loop.until_no_eval(
                    name="foo.bar", expected=5, period=0, timeout=1
                ),
                {
                    "name": "foo.bar",
                    "result": True,
                    "changes": {},
                    "comment": "Call provided the expected results in 5 attempts",
                },
            )

    def test_retried_failure(self):
        """
        Test if the function fails after the designated timeout.
        """
        with patch.dict(
            salt.states.loop.__salt__,  # pylint: disable=no-member
            {
                "foo.bar": MagicMock(side_effect=range(1, 7))
            },  # pylint: disable=incompatible-py3-code
        ):
            self.assertDictEqual(
                salt.states.loop.until(
                    name="foo.bar", condition="m_ret == 5", period=0.01, timeout=0.03
                ),
                {
                    "name": "foo.bar",
                    "result": False,
                    "changes": {},
                    "comment": "Timed out while waiting for condition m_ret == 5",
                },
            )

        # period and timeout below has been increased to keep windows machines from
        # returning a lower number of attempts (because it's slower).
        with patch.dict(
            salt.states.loop.__salt__,  # pylint: disable=no-member
            {
                "foo.bar": MagicMock(side_effect=range(1, 7))
            },  # pylint: disable=incompatible-py3-code
        ):
            self.assertDictEqual(
                salt.states.loop.until_no_eval(
                    name="foo.bar", expected=5, period=0.2, timeout=0.5
                ),
                {
                    "name": "foo.bar",
                    "result": False,
                    "changes": {},
                    "comment": (
                        "Call did not produce the expected result after 3 attempts"
                    ),
                },
            )
