# -*- coding: utf-8 -*-
"""
    Unit tests for salt.utils.yamldumper
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.ext.six
import salt.utils.yamldumper

# Import Salt Testing Libs
from tests.support.unit import TestCase


class YamlDumperTestCase(TestCase):
    """
    TestCase for salt.utils.yamldumper module
    """

    def test_yaml_dump(self):
        """
        Test yaml.dump a dict
        """
        data = {"foo": "bar"}

        if salt.ext.six.PY2:
            exp_yaml = "{!!python/unicode 'foo': !!python/unicode 'bar'}\n"
        else:
            exp_yaml = "{foo: bar}\n"

        assert salt.utils.yamldumper.dump(data) == exp_yaml

        assert salt.utils.yamldumper.dump(
            data, default_flow_style=False
        ) == exp_yaml.replace("{", "").replace("}", "")

    def test_yaml_safe_dump(self):
        """
        Test yaml.safe_dump a dict
        """
        data = {"foo": "bar"}
        assert salt.utils.yamldumper.safe_dump(data) == "{foo: bar}\n"

        assert (
            salt.utils.yamldumper.safe_dump(data, default_flow_style=False)
            == "foo: bar\n"
        )
