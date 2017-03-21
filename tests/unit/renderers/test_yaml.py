# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase

# Import Salt libs
import salt.renderers.yaml as yaml


class YAMLRendererTestCase(TestCase, LoaderModuleMockMixin):

    loader_module = yaml

    def test_yaml_render_string(self):
        data = "string"
        result = yaml.render(data)

        self.assertEqual(result, data)

    def test_yaml_render_unicode(self):
        data = "!!python/unicode python unicode string"
        result = yaml.render(data)

        self.assertEqual(result, u"python unicode string")
