"""
    Unit tests for salt.utils.yamldumper
"""

import salt.utils.yamldumper
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
