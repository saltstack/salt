# -*- coding: utf-8 -*-
'''
Tests for salt.utils.data
'''

# Import Python libs
from __future__ import absolute_import
import textwrap

# Import Salt libs
import salt.utils.templates
from tests.support.unit import TestCase, LOREM_IPSUM


class TemplatesTestCase(TestCase):

    def test_get_context(self):
        expected_context = textwrap.dedent('''\
            ---
            Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque eget urna a arcu lacinia sagittis.
            Sed scelerisque, lacus eget malesuada vestibulum, justo diam facilisis tortor, in sodales dolor
            [...]
            ---''')
        ret = salt.utils.templates.get_context(LOREM_IPSUM, 1, num_lines=1)
        self.assertEqual(ret, expected_context)
