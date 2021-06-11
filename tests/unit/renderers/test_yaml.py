# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import collections
import textwrap

# Import Salt libs
import salt.renderers.yaml as yaml
from salt.ext import six

# Import Salt Testing libs
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
        if six.PY3:
            return
        if isinstance(value, six.string_types):
            if not isinstance(value, six.text_type):
                self.raise_error(value)
        elif isinstance(value, collections.Mapping):
            for k, v in six.iteritems(value):
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
