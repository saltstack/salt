import collections
import textwrap

import salt.renderers.yaml as yaml
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import patch
from tests.support.unit import TestCase


class YAMLRendererTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {yaml: {}}

    def assert_unicode(self, value):
        """
        Make sure the entire data structure is unicode
        """
        if isinstance(value, str):
            if not isinstance(value, str):
                self.raise_error(value)
        elif isinstance(value, collections.Mapping):
            for k, v in value.items():
                self.assert_unicode(k)
                self.assert_unicode(v)
        elif isinstance(value, collections.Iterable):
            for item in value:
                self.assert_unicode(item)

    def assert_matches(self, ret, expected):
        self.assertEqual(ret, expected)
        self.assert_unicode(ret)

    def test_yaml_render_string(self):
        data = "string"
        result = yaml.render(data)

        self.assertEqual(result, data)

    def test_yaml_render_unicode(self):
        data = "!!python/unicode python unicode string"
        result = yaml.render(data)

        self.assertEqual(result, "python unicode string")

    def test_yaml_render_old_unicode(self):
        config = {"use_yamlloader_old": True}
        with patch.dict(yaml.__opts__, config):  # pylint: disable=no-member
            self.assert_matches(
                yaml.render(
                    textwrap.dedent(
                        """\
                    foo:
                      a: Д
                      b: {'a': u'\\u0414'}"""
                    )
                ),
                {"foo": {"a": "\u0414", "b": {"a": "\u0414"}}},
            )
