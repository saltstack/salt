# -*- coding: utf-8 -*-
'''
Tests for salt.utils.yamlencoding
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
import salt.utils.yaml
import salt.utils.yamlencoding
from tests.support.unit import TestCase
import pytest


class YamlEncodingTestCase(TestCase):

    def test_yaml_dquote(self):
        for teststr in (r'"\ []{}"',):
            assert teststr == salt.utils.yaml.safe_load(salt.utils.yamlencoding.yaml_dquote(teststr))

    def test_yaml_dquote_doesNotAddNewLines(self):
        teststr = '"' * 100
        assert '\n' not in salt.utils.yamlencoding.yaml_dquote(teststr)

    def test_yaml_squote(self):
        ret = salt.utils.yamlencoding.yaml_squote(r'"')
        assert ret == r"""'"'"""

    def test_yaml_squote_doesNotAddNewLines(self):
        teststr = "'" * 100
        assert '\n' not in salt.utils.yamlencoding.yaml_squote(teststr)

    def test_yaml_encode(self):
        for testobj in (None, True, False, '[7, 5]', '"monkey"', 5, 7.5, "2014-06-02 15:30:29.7"):
            assert testobj == salt.utils.yaml.safe_load(salt.utils.yamlencoding.yaml_encode(testobj))

        for testobj in ({}, [], set()):
            with pytest.raises(TypeError):
                salt.utils.yamlencoding.yaml_encode(testobj)
