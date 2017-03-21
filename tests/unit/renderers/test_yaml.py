# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.unit import TestCase

# Import Salt libs
import salt.renderers.yaml as yaml

yaml.__salt__ = {}
yaml.__opts__ = {}


class YAMLRendererTestCase(TestCase):
    def test_yaml_render_string(self):
        data = "string"
        result = yaml.render(data)

        self.assertEqual(result, data)

    def test_yaml_render_unicode(self):
        data = "!!python/unicode python unicode string"
        result = yaml.render(data)

        self.assertEqual(result, u"python unicode string")
