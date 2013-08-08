# -*- coding: utf-8 -*-
'''
    tests.unit.pillar_test
    ~~~~~~~~~~~~~~~~~~~~~~

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../')

# Import salt libs
import salt.pillar

# Import 3rd-party libs
try:
    from mock import MagicMock, patch
    HAS_MOCK = True
except ImportError:
    HAS_MOCK = False


@skipIf(HAS_MOCK is False, 'mock python module is unavailable')
class PillarTestCase(TestCase):

    @patch('salt.pillar.compile_template')
    def test_malformed_pillar_sls(self, compile_template):
        opts = {
            'renderer': 'json',
            'state_top': '',
            'pillar_roots': [],
            'extension_modules': ''
        }
        grains = {
            'os': 'Ubuntu',
            'os_family': 'Debian',
            'oscodename': 'raring',
            'osfullname': 'Ubuntu',
            'osrelease': '13.04',
            'kernel': 'Linux'
        }
        pillar = salt.pillar.Pillar(opts, grains, 'mocked-minion', 'base')
        # Mock getting the proper template files
        pillar.client.get_state = MagicMock(
            return_value={
                'dest': '/path/to/pillar/files/foo.sls',
                'source': 'salt://foo.sls'
            }
        )

        # Template compilation returned a string
        compile_template.return_value = 'BAHHH'
        self.assertEqual(
            pillar.render_pillar({'base': ['foo.sls']}),
            ({}, ['SLS \'foo.sls\' does not render to a dictionary'])
        )

        # Template compilation returned a list
        compile_template.return_value = ['BAHHH']
        self.assertEqual(
            pillar.render_pillar({'base': ['foo.sls']}),
            ({}, ['SLS \'foo.sls\' does not render to a dictionary'])
        )

        # Template compilation returned a dictionary, which is what's expected
        compile_template.return_value = {'foo': 'bar'}
        self.assertEqual(
            pillar.render_pillar({'base': ['foo.sls']}),
            ({'foo': 'bar'}, [])
        )

        # Test improper includes
        compile_template.side_effect = [
            {'foo': 'bar', 'include': 'blah'},
            {'foo2': 'bar2'}
        ]
        self.assertEqual(
            pillar.render_pillar({'base': ['foo.sls']}),
            ({'foo': 'bar', 'include': 'blah'},
             ["Include Declaration in SLS 'foo.sls' is not formed as a list"])
        )

        # Test includes as a list, which is what's expected
        compile_template.side_effect = [
            {'foo': 'bar', 'include': ['blah']},
            {'foo2': 'bar2'}
        ]
        self.assertEqual(
            pillar.render_pillar({'base': ['foo.sls']}),
            ({'foo': 'bar', 'foo2': 'bar2'}, [])
        )

        # Test includes as a list overriding data
        compile_template.side_effect = [
            {'foo': 'bar', 'include': ['blah']},
            {'foo': 'bar2'}
        ]
        self.assertEqual(
            pillar.render_pillar({'base': ['foo.sls']}),
            ({'foo': 'bar2'}, [])
        )
