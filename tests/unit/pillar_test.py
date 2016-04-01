# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    tests.unit.pillar_test
    ~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
from __future__ import absolute_import
import tempfile

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch
ensure_in_syspath('../')

# Import salt libs
import salt.pillar


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PillarTestCase(TestCase):

    @patch('salt.pillar.compile_template')
    def test_malformed_pillar_sls(self, compile_template):
        opts = {
            'renderer': 'json',
            'state_top': '',
            'pillar_roots': [],
            'file_roots': [],
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

    @patch('salt.pillar.salt.fileclient.get_file_client', autospec=True)
    @patch('salt.pillar.salt.minion.Matcher')  # autospec=True disabled due to py3 mock bug
    def test_topfile_order(self, Matcher, get_file_client):
        opts = {
            'renderer': 'yaml',
            'state_top': '',
            'pillar_roots': [],
            'extension_modules': '',
            'environment': 'base',
            'file_roots': [],
        }
        grains = {
            'os': 'Ubuntu',
            'os_family': 'Debian',
            'oscodename': 'raring',
            'osfullname': 'Ubuntu',
            'osrelease': '13.04',
            'kernel': 'Linux'
        }
        # glob match takes precedence
        self._setup_test_topfile_mocks(Matcher, get_file_client, 1, 2)
        pillar = salt.pillar.Pillar(opts, grains, 'mocked-minion', 'base')
        self.assertEqual(pillar.compile_pillar()['ssh'], 'bar')
        # nodegroup match takes precedence
        self._setup_test_topfile_mocks(Matcher, get_file_client, 2, 1)
        pillar = salt.pillar.Pillar(opts, grains, 'mocked-minion', 'base')
        self.assertEqual(pillar.compile_pillar()['ssh'], 'foo')

    def _setup_test_topfile_mocks(self, Matcher, get_file_client,
            nodegroup_order, glob_order):
        # Write a simple topfile and two pillar state files
        self.top_file = tempfile.NamedTemporaryFile()
        s = '''
base:
    group:
        - match: nodegroup
        - order: {nodegroup_order}
        - ssh
        - generic
    '*':
        - generic
    minion:
        - order: {glob_order}
        - ssh.minion
        - generic.minion
'''.format(nodegroup_order=nodegroup_order, glob_order=glob_order)
        self.top_file.write(salt.utils.to_bytes(s))
        self.top_file.flush()
        self.ssh_file = tempfile.NamedTemporaryFile()
        self.ssh_file.write(b'''
ssh:
    foo
''')
        self.ssh_file.flush()
        self.ssh_minion_file = tempfile.NamedTemporaryFile()
        self.ssh_minion_file.write(b'''
ssh:
    bar
''')
        self.ssh_minion_file.flush()
        self.generic_file = tempfile.NamedTemporaryFile()
        self.generic_file.write(b'''
generic:
    key1:
      - value1
      - value2
    key2:
        sub_key1: []
''')
        self.generic_file.flush()
        self.generic_minion_file = tempfile.NamedTemporaryFile()
        self.generic_minion_file.write(b'''
generic:
    key1:
      - value3
    key2:
        sub_key2: []
''')
        self.generic_minion_file.flush()

        # Setup Matcher mock
        matcher = Matcher.return_value
        matcher.confirm_top.return_value = True

        # Setup fileclient mock
        client = get_file_client.return_value
        client.cache_file.return_value = self.top_file.name

        def get_state(sls, env):
            return {
                'ssh': {'path': '', 'dest': self.ssh_file.name},
                'ssh.minion': {'path': '', 'dest': self.ssh_minion_file.name},
                'generic': {'path': '', 'dest': self.generic_file.name},
                'generic.minion': {'path': '', 'dest': self.generic_minion_file.name},
            }[sls]

        client.get_state.side_effect = get_state

    def _setup_test_include_mocks(self, Matcher, get_file_client):
        self.top_file = top_file = tempfile.NamedTemporaryFile()
        top_file.write(b'''
base:
    '*':
        - order: 1
        - test.sub2
    minion:
        - order: 2
        - test
''')
        top_file.flush()
        self.init_sls = init_sls = tempfile.NamedTemporaryFile()
        init_sls.write(b'''
include:
   - test.sub1
   - test.sub2
''')
        init_sls.flush()
        self.sub1_sls = sub1_sls = tempfile.NamedTemporaryFile()
        sub1_sls.write(b'''
p1:
   - value1_1
   - value1_2
''')
        sub1_sls.flush()
        self.sub2_sls = sub2_sls = tempfile.NamedTemporaryFile()
        sub2_sls.write(b'''
p1:
   - value1_3
p2:
   - value2_1
   - value2_2
''')
        sub2_sls.flush()

        # Setup Matcher mock
        matcher = Matcher.return_value
        matcher.confirm_top.return_value = True

        # Setup fileclient mock
        client = get_file_client.return_value
        client.cache_file.return_value = self.top_file.name

        def get_state(sls, env):
            return {
                'test': {'path': '', 'dest': init_sls.name},
                'test.sub1': {'path': '', 'dest': sub1_sls.name},
                'test.sub2': {'path': '', 'dest': sub2_sls.name},
            }[sls]

        client.get_state.side_effect = get_state


if __name__ == '__main__':
    from integration import run_tests
    run_tests(PillarTestCase, needs_daemon=False)
