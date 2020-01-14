# -*- coding: utf-8 -*-
'''
Unit tests for salt.utils.color.py
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.unit import TestCase

# Import Salt libs
import salt.utils.color
from salt.ext import six


class ColorUtilsTestCase(TestCase):

    def test_get_colors(self):
        ret = salt.utils.color.get_colors()
        assert '\x1b[0;37m' == six.text_type(ret['LIGHT_GRAY'])

        ret = salt.utils.color.get_colors(use=False)
        assert dict(ret, **{'LIGHT_GRAY': ''}) == ret

        ret = salt.utils.color.get_colors(use='LIGHT_GRAY')
        # LIGHT_YELLOW now == LIGHT_GRAY
        assert six.text_type(ret['LIGHT_YELLOW']) == six.text_type(ret['LIGHT_GRAY'])
