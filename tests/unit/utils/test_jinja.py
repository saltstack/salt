# -*- coding: utf-8 -*-
'''
Tests for salt.utils.jinja
'''
# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt libs
import salt.utils.jinja
from tests.support.unit import TestCase


class JinjaTestCase(TestCase):
    def test_tojson(self):
        '''
        Test the tojson filter for those using Jinja < 2.9. Non-ascii unicode
        content should be dumped with ensure_ascii=True.
        '''
        data = {'Non-ascii words': ['süß', 'спам', 'яйца']}
        result = salt.utils.jinja.tojson(data)
        expected = '{"Non-ascii words": ["s\\u00fc\\u00df", "\\u0441\\u043f\\u0430\\u043c", "\\u044f\\u0439\\u0446\\u0430"]}'
        assert result == expected, result
