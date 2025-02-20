"""
    Unit tests for salt.utils.yamldumper
"""

import pytest
from yaml.constructor import ConstructorError

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

    def test_yaml_loader_with_opts(self):
        """
        Test SaltYamlSafeLoader with __opts__
        """
        yaml_data = "key: value\n"
        opts = {"some_key": "some_value"}
        loader = salt.utils.yamlloader.SaltYamlSafeLoader(yaml_data, opts=opts)
        data = loader.get_single_data()

        # Check that data is parsed correctly
        assert data == {"key": "value"}

        # Check that __opts__ is accessible
        assert loader.__opts__ == opts

    def test_construct_mapping_with_opts(self):
        """
        Test construct_mapping with __opts__
        """
        yaml_data = """
        key1: value1
        key2: value2
        """
        opts = {"custom_behavior": "test_value"}
        loader = salt.utils.yamlloader.SaltYamlSafeLoader(yaml_data, opts=opts)
        mapping = loader.get_single_data()

        # Ensure mapping was constructed correctly
        assert mapping == {"key1": "value1", "key2": "value2"}

        # Optionally, add logic to test how `__opts__` affects the loader
        assert loader.__opts__.get("custom_behavior") == "test_value"

    def test_allow_duplicate_includes(self):
        """
        Test allow_duplicate_includes=True
        """
        yaml_data = """
        include:
          - foo
          - bar
        include:
          - foo
          - bar
        """
        opts = {"allow_duplicate_includes": True}
        loader = salt.utils.yamlloader.SaltYamlSafeLoader(yaml_data, opts=opts)
        data = loader.get_single_data()

        assert data == {
            "include": ["foo", "bar"],
        }

    def test_allow_duplicate_includes_false(self):
        """
        Test allow_duplicate_includes=False
        """
        yaml_data = """
        include:
          - foo
          - bar
        include:
          - foo
          - bar
        """
        opts = {"allow_duplicate_includes": False}

        with pytest.raises(ConstructorError, match="found conflicting ID 'include'"):
            loader = salt.utils.yamlloader.SaltYamlSafeLoader(yaml_data, opts=opts)
            loader.get_single_data()
