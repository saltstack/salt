# coding: utf-8

# python libs
from __future__ import absolute_import

# salt testing libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import patch, NO_MOCK, NO_MOCK_REASON

# salt libs
ensure_in_syspath('../../')
import salt.ext.six as six
from salt.ext.six.moves import reload_module
from salt.utils import locales


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
        b = '\xe7\xb9\x81\xe4\xbd\x93' if six.PY2 else bytes((0xe7, 0xb9, 0x81, 0xe4, 0xbd, 0x93))
        u = u'\u7e41\u4f53'
        with patch('salt.utils.locales.get_encodings', return_value=['ascii']):
            self.assertEqual(locales.sdecode(b), b)  # no decode
        with patch('salt.utils.locales.get_encodings', return_value=['utf-8']):
            self.assertEqual(locales.sdecode(b), u)

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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(TestLocales, needs_daemon=False)
