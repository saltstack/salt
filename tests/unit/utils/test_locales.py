# coding: utf-8

# Import Python libs
from __future__ import absolute_import, unicode_literals


# Import Salt libs
import salt.utils.locales as locales
from tests.support.unit import TestCase, skipIf
from tests.support.mock import patch, NO_MOCK, NO_MOCK_REASON

# Import 3rd-part libs
from salt.ext import six
from salt.ext.six.moves import reload_module


@skipIf(NO_MOCK, NO_MOCK_REASON)
class TestLocales(TestCase):
    def test_get_encodings(self):
        # reload locales modules before and after to defeat memoization of
        # get_encodings()
        reload_module(locales)
        with patch('sys.getdefaultencoding', return_value='xyzzy'):
            encodings = locales.get_encodings()
            for enc in (__salt_system_encoding__, 'xyzzy', 'utf-8', 'latin-1'):
                self.assertIn(enc, encodings)
        reload_module(locales)

    def test_sdecode(self):
        u = 'питон'
        b = u.encode('utf-8')
        if six.PY2:
            # Under Py3, the above `b` as bytes, will never decode as anything even comparable using `ascii`
            # but no unicode error will be raised, as such, sdecode will return the poorly decoded string
            with patch('salt.utils.locales.get_encodings', return_value=['ascii']):
                self.assertEqual(locales.sdecode(b), b)  # no decode
        with patch('salt.utils.locales.get_encodings', return_value=['utf-8']):
            self.assertEqual(locales.sdecode(b), u)
        # Non strings are left untouched
        with patch('salt.utils.locales.get_encodings', return_value=['utf-8']):
            self.assertEqual(locales.sdecode(1), 1)

    def test_split_locale(self):
        self.assertDictEqual(
                locales.split_locale('ca_ES.UTF-8@valencia utf-8'),
                {'charmap': 'utf-8',
                 'modifier': 'valencia',
                 'codeset': 'UTF-8',
                 'language': 'ca',
                 'territory': 'ES'})

    def test_join_locale(self):
        self.assertEqual(
                locales.join_locale(
                    {'charmap': 'utf-8',
                     'modifier': 'valencia',
                     'codeset': 'UTF-8',
                     'language': 'ca',
                     'territory': 'ES'}),
                'ca_ES.UTF-8@valencia utf-8')

    def test_normalize_locale(self):
        self.assertEqual(
                locales.normalize_locale('ca_es.UTF-8@valencia utf-8'),
                'ca_ES.utf8@valencia')
