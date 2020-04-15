# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import salt.utils.platform

# Import 3rd-party libs
from salt.ext import six

# Import Salt Testing libs
from tests.support.case import ModuleCase


class StdTest(ModuleCase):
    """
    Test standard client calls
    """

    def setUp(self):
        self.TIMEOUT = 600 if salt.utils.platform.is_windows() else 10

    def test_cli(self):
        """
        Test cli function
        """
        cmd_iter = self.client.cmd_cli(
            "minion", "test.arg", ["foo", "bar", "baz"], kwarg={"qux": "quux"}
        )
        for ret in cmd_iter:
            data = ret["minion"]["ret"]
            self.assertEqual(data["args"], ["foo", "bar", "baz"])
            self.assertEqual(data["kwargs"]["qux"], "quux")

    def test_iter(self):
        """
        test cmd_iter
        """
        cmd_iter = self.client.cmd_iter(
            "minion", "test.arg", ["foo", "bar", "baz"], kwarg={"qux": "quux"}
        )
        for ret in cmd_iter:
            data = ret["minion"]["ret"]
            self.assertEqual(data["args"], ["foo", "bar", "baz"])
            self.assertEqual(data["kwargs"]["qux"], "quux")

    def test_iter_no_block(self):
        """
        test cmd_iter_no_block
        """
        cmd_iter = self.client.cmd_iter_no_block(
            "minion", "test.arg", ["foo", "bar", "baz"], kwarg={"qux": "quux"}
        )
        for ret in cmd_iter:
            if ret is None:
                continue
            data = ret["minion"]["ret"]
            self.assertEqual(data["args"], ["foo", "bar", "baz"])
            self.assertEqual(data["kwargs"]["qux"], "quux")

    def test_full_returns(self):
        """
        test cmd_iter
        """
        ret = self.client.cmd_full_return(
            "minion",
            "test.arg",
            ["foo", "bar", "baz"],
            timeout=self.TIMEOUT,
            kwarg={"qux": "quux"},
        )
        data = ret["minion"]["ret"]
        self.assertEqual(data["args"], ["foo", "bar", "baz"])
        self.assertEqual(data["kwargs"]["qux"], "quux")

    def test_kwarg_type(self):
        """
        Test that kwargs end up on the client as the same type
        """
        terrible_yaml_string = 'foo: ""\n# \''
        ret = self.client.cmd_full_return(
            "minion",
            "test.arg_type",
            ["a", 1],
            kwarg={"outer": {"a": terrible_yaml_string}, "inner": "value"},
            timeout=self.TIMEOUT,
        )
        data = ret["minion"]["ret"]
        self.assertIn(six.text_type.__name__, data["args"][0])
        self.assertIn("int", data["args"][1])
        self.assertIn("dict", data["kwargs"]["outer"])
        self.assertIn(six.text_type.__name__, data["kwargs"]["inner"])

    def test_full_return_kwarg(self):
        ret = self.client.cmd(
            "minion", "test.ping", full_return=True, timeout=self.TIMEOUT,
        )
        for mid, data in ret.items():
            self.assertIn("retcode", data)

    def test_cmd_arg_kwarg_parsing(self):
        ret = self.client.cmd(
            "minion",
            "test.arg_clean",
            arg=["foo", "bar=off", "baz={qux: 123}"],
            kwarg={"quux": "Quux"},
            timeout=self.TIMEOUT,
        )
        self.assertEqual(
            ret["minion"],
            {
                "args": ["foo"],
                "kwargs": {"bar": False, "baz": {"qux": 123}, "quux": "Quux"},
            },
        )
