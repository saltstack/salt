"""
    Unit tests for salt.utils.yamlloader.SaltYamlSafeLoader
"""

import textwrap

from yaml.constructor import ConstructorError

import salt.utils.files
from salt.utils.yamlloader import SaltYamlSafeLoader, yaml
from tests.support.mock import mock_open, patch
from tests.support.unit import TestCase


class YamlLoaderTestCase(TestCase):
    """
    TestCase for salt.utils.yamlloader module
    """

    @staticmethod
    def render_yaml(data):
        """
        Takes a YAML string, puts it into a mock file, passes that to the YAML
        SaltYamlSafeLoader and then returns the rendered/parsed YAML data
        """
        with patch("salt.utils.files.fopen", mock_open(read_data=data)) as mocked_file:
            with salt.utils.files.fopen(mocked_file) as mocked_stream:
                return SaltYamlSafeLoader(mocked_stream).get_data()

    def test_yaml_basics(self):
        """
        Test parsing an ordinary path
        """
        self.assertEqual(
            self.render_yaml(
                textwrap.dedent(
                    """\
                p1:
                  - alpha
                  - beta"""
                )
            ),
            {"p1": ["alpha", "beta"]},
        )

    def test_yaml_merge(self):
        """
        Test YAML anchors
        """
        # Simple merge test
        self.assertEqual(
            self.render_yaml(
                textwrap.dedent(
                    """\
                p1: &p1
                  v1: alpha
                p2:
                  <<: *p1
                  v2: beta"""
                )
            ),
            {"p1": {"v1": "alpha"}, "p2": {"v1": "alpha", "v2": "beta"}},
        )

        # Test that keys/nodes are overwritten
        self.assertEqual(
            self.render_yaml(
                textwrap.dedent(
                    """\
                p1: &p1
                  v1: alpha
                p2:
                  <<: *p1
                  v1: new_alpha"""
                )
            ),
            {"p1": {"v1": "alpha"}, "p2": {"v1": "new_alpha"}},
        )

        # Test merging of lists
        self.assertEqual(
            self.render_yaml(
                textwrap.dedent(
                    """\
                p1: &p1
                  v1: &v1
                    - t1
                    - t2
                p2:
                  v2: *v1"""
                )
            ),
            {"p2": {"v2": ["t1", "t2"]}, "p1": {"v1": ["t1", "t2"]}},
        )

    def test_yaml_duplicates(self):
        """
        Test that duplicates still throw an error
        """
        with self.assertRaises(ConstructorError):
            self.render_yaml(
                textwrap.dedent(
                    """\
                p1: alpha
                p1: beta"""
                )
            )

        with self.assertRaises(ConstructorError):
            self.render_yaml(
                textwrap.dedent(
                    """\
                p1: &p1
                  v1: alpha
                p2:
                  <<: *p1
                  v2: beta
                  v2: betabeta"""
                )
            )

    def test_yaml_with_plain_scalars(self):
        """
        Test that plain (i.e. unqoted) string and non-string scalars are
        properly handled
        """
        self.assertEqual(
            self.render_yaml(
                textwrap.dedent(
                    """\
                foo:
                  b: {foo: bar, one: 1, list: [1, two, 3]}"""
                )
            ),
            {"foo": {"b": {"foo": "bar", "one": 1, "list": [1, "two", 3]}}},
        )

    def test_not_yaml_monkey_patching(self):
        if hasattr(yaml, "CSafeLoader"):
            assert yaml.SafeLoader != yaml.CSafeLoader
