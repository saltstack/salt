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
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch
from tests.support.paths import TMP

# Import salt libs
import salt.pillar


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PillarTestCase(TestCase):

    def tearDown(self):
        for attrname in ('generic_file', 'generic_minion_file', 'ssh_file', 'ssh_minion_file', 'top_file'):
            try:
                delattr(self, attrname)
            except AttributeError:
                continue

    def test_pillarenv_from_saltenv(self):
        with patch('salt.pillar.compile_template') as compile_template:
            opts = {
                'renderer': 'json',
                'renderer_blacklist': [],
                'renderer_whitelist': [],
                'state_top': '',
                'pillar_roots': ['dev', 'base'],
                'file_roots': ['dev', 'base'],
                'extension_modules': '',
                'pillarenv_from_saltenv': True
            }
            grains = {
                'os': 'Ubuntu',
            }
            pillar = salt.pillar.Pillar(opts, grains, 'mocked-minion', 'dev')
            self.assertEqual(pillar.opts['environment'], 'dev')
            self.assertEqual(pillar.opts['pillarenv'], 'dev')

    def test_dynamic_pillarenv(self):
        opts = {
            'renderer': 'json',
            'renderer_blacklist': [],
            'renderer_whitelist': [],
            'state_top': '',
            'pillar_roots': {'__env__': '/srv/pillar/__env__', 'base': '/srv/pillar/base'},
            'file_roots': {'base': '/srv/salt/base', 'dev': '/svr/salt/dev'},
            'extension_modules': '',
        }
        pillar = salt.pillar.Pillar(opts, {}, 'mocked-minion', 'base', pillarenv='dev')
        self.assertEqual(pillar.opts['file_roots'],
                         {'base': '/srv/pillar/base', 'dev': '/srv/pillar/__env__'})

    def test_ignored_dynamic_pillarenv(self):
        opts = {
            'renderer': 'json',
            'renderer_blacklist': [],
            'renderer_whitelist': [],
            'state_top': '',
            'pillar_roots': {'__env__': '/srv/pillar/__env__', 'base': '/srv/pillar/base'},
            'file_roots': {'base': '/srv/salt/base', 'dev': '/svr/salt/dev'},
            'extension_modules': '',
        }
        pillar = salt.pillar.Pillar(opts, {}, 'mocked-minion', 'base', pillarenv='base')
        self.assertEqual(pillar.opts['file_roots'], {'base': '/srv/pillar/base'})

    def test_malformed_pillar_sls(self):
        with patch('salt.pillar.compile_template') as compile_template:
            opts = {
                'renderer': 'json',
                'renderer_blacklist': [],
                'renderer_whitelist': [],
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
                ({'foo': 'bar'}, [])
            )

            # Test includes using empty key directive
            compile_template.side_effect = [
                {'foo': 'bar', 'include': [{'blah': {'key': ''}}]},
                {'foo': 'bar2'}
            ]
            self.assertEqual(
                pillar.render_pillar({'base': ['foo.sls']}),
                ({'foo': 'bar'}, [])
            )

            # Test includes using simple non-nested key
            compile_template.side_effect = [
                {'foo': 'bar', 'include': [{'blah': {'key': 'nested'}}]},
                {'foo': 'bar2'}
            ]
            self.assertEqual(
                pillar.render_pillar({'base': ['foo.sls']}),
                ({'foo': 'bar', 'nested': {'foo': 'bar2'}}, [])
            )

            # Test includes using nested key
            compile_template.side_effect = [
                {'foo': 'bar', 'include': [{'blah': {'key': 'nested:level'}}]},
                {'foo': 'bar2'}
            ]
            self.assertEqual(
                pillar.render_pillar({'base': ['foo.sls']}),
                ({'foo': 'bar', 'nested': {'level': {'foo': 'bar2'}}}, [])
            )

    def test_topfile_order(self):
        with patch('salt.pillar.salt.fileclient.get_file_client', autospec=True) as get_file_client, \
                patch('salt.pillar.salt.minion.Matcher') as Matcher:  # autospec=True disabled due to py3 mock bug
            opts = {
                'renderer': 'yaml',
                'renderer_blacklist': [],
                'renderer_whitelist': [],
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
        self.top_file = tempfile.NamedTemporaryFile(dir=TMP, delete=False)
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
        self.ssh_file = tempfile.NamedTemporaryFile(dir=TMP, delete=False)
        self.ssh_file.write(b'''
ssh:
    foo
''')
        self.ssh_file.flush()
        self.ssh_minion_file = tempfile.NamedTemporaryFile(dir=TMP, delete=False)
        self.ssh_minion_file.write(b'''
ssh:
    bar
''')
        self.ssh_minion_file.flush()
        self.generic_file = tempfile.NamedTemporaryFile(dir=TMP, delete=False)
        self.generic_file.write(b'''
generic:
    key1:
      - value1
      - value2
    key2:
        sub_key1: []
''')
        self.generic_file.flush()
        self.generic_minion_file = tempfile.NamedTemporaryFile(dir=TMP, delete=False)
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
        self.top_file = top_file = tempfile.NamedTemporaryFile(dir=TMP, delete=False)
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
        self.init_sls = init_sls = tempfile.NamedTemporaryFile(dir=TMP, delete=False)
        init_sls.write(b'''
include:
   - test.sub1
   - test.sub2
''')
        init_sls.flush()
        self.sub1_sls = sub1_sls = tempfile.NamedTemporaryFile(dir=TMP, delete=False)
        sub1_sls.write(b'''
p1:
   - value1_1
   - value1_2
''')
        sub1_sls.flush()
        self.sub2_sls = sub2_sls = tempfile.NamedTemporaryFile(dir=TMP, delete=False)
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
