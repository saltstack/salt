# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function, unicode_literals
import codecs
import glob
import logging
import os
import textwrap

import salt.loader
import salt.utils.data
import salt.utils.reactor as reactor
import salt.utils.yaml

from tests.support.unit import TestCase, skipIf
from tests.support.mixins import AdaptedConfigurationTestCaseMixin
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    patch,
    MagicMock,
    Mock,
    mock_open,
)

REACTOR_CONFIG = '''\
reactor:
  - old_runner:
    - /srv/reactor/old_runner.sls
  - old_wheel:
    - /srv/reactor/old_wheel.sls
  - old_local:
    - /srv/reactor/old_local.sls
  - old_cmd:
    - /srv/reactor/old_cmd.sls
  - old_caller:
    - /srv/reactor/old_caller.sls
  - new_runner:
    - /srv/reactor/new_runner.sls
  - new_wheel:
    - /srv/reactor/new_wheel.sls
  - new_local:
    - /srv/reactor/new_local.sls
  - new_cmd:
    - /srv/reactor/new_cmd.sls
  - new_caller:
    - /srv/reactor/new_caller.sls
'''

REACTOR_DATA = {
    'runner': {'data': {'message': 'This is an error'}},
    'wheel': {'data': {'id': 'foo'}},
    'local': {'data': {'pkg': 'zsh', 'repo': 'updates'}},
    'cmd': {'data': {'pkg': 'zsh', 'repo': 'updates'}},
    'caller': {'data': {'path': '/tmp/foo'}},
}

SLS = {
    '/srv/reactor/old_runner.sls': textwrap.dedent('''\
        raise_error:
          runner.error.error:
            - name: Exception
            - message: {{ data['data']['message'] }}
        '''),
    '/srv/reactor/old_wheel.sls': textwrap.dedent('''\
        remove_key:
          wheel.key.delete:
            - match: {{ data['data']['id'] }}
        '''),
    '/srv/reactor/old_local.sls': textwrap.dedent('''\
        install_zsh:
          local.state.single:
            - tgt: test
            - arg:
              - pkg.installed
              - {{ data['data']['pkg'] }}
            - kwarg:
                fromrepo: {{ data['data']['repo'] }}
        '''),
    '/srv/reactor/old_cmd.sls': textwrap.dedent('''\
        install_zsh:
          cmd.state.single:
            - tgt: test
            - arg:
              - pkg.installed
              - {{ data['data']['pkg'] }}
            - kwarg:
                fromrepo: {{ data['data']['repo'] }}
        '''),
    '/srv/reactor/old_caller.sls': textwrap.dedent('''\
        touch_file:
          caller.file.touch:
            - args:
              - {{ data['data']['path'] }}
        '''),
    '/srv/reactor/new_runner.sls': textwrap.dedent('''\
        raise_error:
          runner.error.error:
            - args:
              - name: Exception
              - message: {{ data['data']['message'] }}
        '''),
    '/srv/reactor/new_wheel.sls': textwrap.dedent('''\
        remove_key:
          wheel.key.delete:
            - args:
              - match: {{ data['data']['id'] }}
        '''),
    '/srv/reactor/new_local.sls': textwrap.dedent('''\
        install_zsh:
          local.state.single:
            - tgt: test
            - args:
              - fun: pkg.installed
              - name: {{ data['data']['pkg'] }}
              - fromrepo: {{ data['data']['repo'] }}
        '''),
    '/srv/reactor/new_cmd.sls': textwrap.dedent('''\
        install_zsh:
          cmd.state.single:
            - tgt: test
            - args:
              - fun: pkg.installed
              - name: {{ data['data']['pkg'] }}
              - fromrepo: {{ data['data']['repo'] }}
        '''),
    '/srv/reactor/new_caller.sls': textwrap.dedent('''\
        touch_file:
          caller.file.touch:
            - args:
              - name: {{ data['data']['path'] }}
        '''),
}

LOW_CHUNKS = {
    # Note that the "name" value in the chunk has been overwritten by the
    # "name" argument in the SLS. This is one reason why the new schema was
    # needed.
    'old_runner': [{
        'state': 'runner',
        '__id__': 'raise_error',
        '__sls__': '/srv/reactor/old_runner.sls',
        'order': 1,
        'fun': 'error.error',
        'name': 'Exception',
        'message': 'This is an error',
    }],
    'old_wheel': [{
        'state': 'wheel',
        '__id__': 'remove_key',
        'name': 'remove_key',
        '__sls__': '/srv/reactor/old_wheel.sls',
        'order': 1,
        'fun': 'key.delete',
        'match': 'foo',
    }],
    'old_local': [{
        'state': 'local',
        '__id__': 'install_zsh',
        'name': 'install_zsh',
        '__sls__': '/srv/reactor/old_local.sls',
        'order': 1,
        'tgt': 'test',
        'fun': 'state.single',
        'arg': ['pkg.installed', 'zsh'],
        'kwarg': {'fromrepo': 'updates'},
    }],
    'old_cmd': [{
        'state': 'local',  # 'cmd' should be aliased to 'local'
        '__id__': 'install_zsh',
        'name': 'install_zsh',
        '__sls__': '/srv/reactor/old_cmd.sls',
        'order': 1,
        'tgt': 'test',
        'fun': 'state.single',
        'arg': ['pkg.installed', 'zsh'],
        'kwarg': {'fromrepo': 'updates'},
    }],
    'old_caller': [{
        'state': 'caller',
        '__id__': 'touch_file',
        'name': 'touch_file',
        '__sls__': '/srv/reactor/old_caller.sls',
        'order': 1,
        'fun': 'file.touch',
        'args': ['/tmp/foo'],
    }],
    'new_runner': [{
        'state': 'runner',
        '__id__': 'raise_error',
        'name': 'raise_error',
        '__sls__': '/srv/reactor/new_runner.sls',
        'order': 1,
        'fun': 'error.error',
        'args': [
            {'name': 'Exception'},
            {'message': 'This is an error'},
        ],
    }],
    'new_wheel': [{
        'state': 'wheel',
        '__id__': 'remove_key',
        'name': 'remove_key',
        '__sls__': '/srv/reactor/new_wheel.sls',
        'order': 1,
        'fun': 'key.delete',
        'args': [
            {'match': 'foo'},
        ],
    }],
    'new_local': [{
        'state': 'local',
        '__id__': 'install_zsh',
        'name': 'install_zsh',
        '__sls__': '/srv/reactor/new_local.sls',
        'order': 1,
        'tgt': 'test',
        'fun': 'state.single',
        'args': [
            {'fun': 'pkg.installed'},
            {'name': 'zsh'},
            {'fromrepo': 'updates'},
        ],
    }],
    'new_cmd': [{
        'state': 'local',
        '__id__': 'install_zsh',
        'name': 'install_zsh',
        '__sls__': '/srv/reactor/new_cmd.sls',
        'order': 1,
        'tgt': 'test',
        'fun': 'state.single',
        'args': [
            {'fun': 'pkg.installed'},
            {'name': 'zsh'},
            {'fromrepo': 'updates'},
        ],
    }],
    'new_caller': [{
        'state': 'caller',
        '__id__': 'touch_file',
        'name': 'touch_file',
        '__sls__': '/srv/reactor/new_caller.sls',
        'order': 1,
        'fun': 'file.touch',
        'args': [
            {'name': '/tmp/foo'},
        ],
    }],
}

WRAPPER_CALLS = {
    'old_runner': (
        'error.error',
        {
            '__state__': 'runner',
            '__id__': 'raise_error',
            '__sls__': '/srv/reactor/old_runner.sls',
            '__user__': 'Reactor',
            'order': 1,
            'arg': [],
            'kwarg': {
                'name': 'Exception',
                'message': 'This is an error',
            },
            'name': 'Exception',
            'message': 'This is an error',
        },
    ),
    'old_wheel': (
        'key.delete',
        {
            '__state__': 'wheel',
            '__id__': 'remove_key',
            'name': 'remove_key',
            '__sls__': '/srv/reactor/old_wheel.sls',
            'order': 1,
            '__user__': 'Reactor',
            'arg': ['foo'],
            'kwarg': {},
            'match': 'foo',
        },
    ),
    'old_local': {
        'args': ('test', 'state.single'),
        'kwargs': {
            'state': 'local',
            '__id__': 'install_zsh',
            'name': 'install_zsh',
            '__sls__': '/srv/reactor/old_local.sls',
            'order': 1,
            'arg': ['pkg.installed', 'zsh'],
            'kwarg': {'fromrepo': 'updates'},
        },
    },
    'old_cmd': {
        'args': ('test', 'state.single'),
        'kwargs': {
            'state': 'local',
            '__id__': 'install_zsh',
            'name': 'install_zsh',
            '__sls__': '/srv/reactor/old_cmd.sls',
            'order': 1,
            'arg': ['pkg.installed', 'zsh'],
            'kwarg': {'fromrepo': 'updates'},
        },
    },
    'old_caller': {
        'args': ('file.touch', '/tmp/foo'),
        'kwargs': {},
    },
    'new_runner': (
        'error.error',
        {
            '__state__': 'runner',
            '__id__': 'raise_error',
            'name': 'raise_error',
            '__sls__': '/srv/reactor/new_runner.sls',
            '__user__': 'Reactor',
            'order': 1,
            'arg': (),
            'kwarg': {
                'name': 'Exception',
                'message': 'This is an error',
            },
        },
    ),
    'new_wheel': (
        'key.delete',
        {
            '__state__': 'wheel',
            '__id__': 'remove_key',
            'name': 'remove_key',
            '__sls__': '/srv/reactor/new_wheel.sls',
            'order': 1,
            '__user__': 'Reactor',
            'arg': (),
            'kwarg': {'match': 'foo'},
        },
    ),
    'new_local': {
        'args': ('test', 'state.single'),
        'kwargs': {
            'state': 'local',
            '__id__': 'install_zsh',
            'name': 'install_zsh',
            '__sls__': '/srv/reactor/new_local.sls',
            'order': 1,
            'arg': (),
            'kwarg': {
                'fun': 'pkg.installed',
                'name': 'zsh',
                'fromrepo': 'updates',
            },
        },
    },
    'new_cmd': {
        'args': ('test', 'state.single'),
        'kwargs': {
            'state': 'local',
            '__id__': 'install_zsh',
            'name': 'install_zsh',
            '__sls__': '/srv/reactor/new_cmd.sls',
            'order': 1,
            'arg': (),
            'kwarg': {
                'fun': 'pkg.installed',
                'name': 'zsh',
                'fromrepo': 'updates',
            },
        },
    },
    'new_caller': {
        'args': ('file.touch',),
        'kwargs': {'name': '/tmp/foo'},
    },
}

log = logging.getLogger(__name__)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class TestReactor(TestCase, AdaptedConfigurationTestCaseMixin):
    '''
    Tests for constructing the low chunks to be executed via the Reactor
    '''
    @classmethod
    def setUpClass(cls):
        '''
        Load the reactor config for mocking
        '''
        cls.opts = cls.get_temp_config('master')
        reactor_config = salt.utils.yaml.safe_load(REACTOR_CONFIG)
        cls.opts.update(reactor_config)
        cls.reactor = reactor.Reactor(cls.opts)
        cls.reaction_map = salt.utils.data.repack_dictlist(reactor_config['reactor'])
        renderers = salt.loader.render(cls.opts, {})
        cls.render_pipe = [(renderers[x], '') for x in ('jinja', 'yaml')]

    @classmethod
    def tearDownClass(cls):
        del cls.opts
        del cls.reactor
        del cls.render_pipe

    def test_list_reactors(self):
        '''
        Ensure that list_reactors() returns the correct list of reactor SLS
        files for each tag.
        '''
        for schema in ('old', 'new'):
            for rtype in REACTOR_DATA:
                tag = '_'.join((schema, rtype))
                self.assertEqual(
                    self.reactor.list_reactors(tag),
                    self.reaction_map[tag]
                )

    def test_reactions(self):
        '''
        Ensure that the correct reactions are built from the configured SLS
        files and tag data.
        '''
        for schema in ('old', 'new'):
            for rtype in REACTOR_DATA:
                tag = '_'.join((schema, rtype))
                log.debug('test_reactions: processing %s', tag)
                reactors = self.reactor.list_reactors(tag)
                log.debug('test_reactions: %s reactors: %s', tag, reactors)
                # No globbing in our example SLS, and the files don't actually
                # exist, so mock glob.glob to just return back the path passed
                # to it.
                with patch.object(
                        glob,
                        'glob',
                        MagicMock(side_effect=lambda x: [x])):
                    # The below four mocks are all so that
                    # salt.template.compile_template() will read the templates
                    # we've mocked up in the SLS global variable above.
                    with patch.object(
                            os.path, 'isfile',
                            MagicMock(return_value=True)):
                        with patch.object(
                                salt.utils, 'is_empty',
                                MagicMock(return_value=False)):
                            with patch.object(
                                    codecs, 'open',
                                    mock_open(read_data=SLS[reactors[0]])):
                                with patch.object(
                                        salt.template, 'template_shebang',
                                        MagicMock(return_value=self.render_pipe)):
                                    reactions = self.reactor.reactions(
                                        tag,
                                        REACTOR_DATA[rtype],
                                        reactors,
                                    )
                                    log.debug(
                                        'test_reactions: %s reactions: %s',
                                        tag, reactions
                                    )
                                    self.assertEqual(reactions, LOW_CHUNKS[tag])


@skipIf(NO_MOCK, NO_MOCK_REASON)
class TestReactWrap(TestCase, AdaptedConfigurationTestCaseMixin):
    '''
    Tests that we are formulating the wrapper calls properly
    '''
    @classmethod
    def setUpClass(cls):
        cls.wrap = reactor.ReactWrap(cls.get_temp_config('master'))

    @classmethod
    def tearDownClass(cls):
        del cls.wrap

    def test_runner(self):
        '''
        Test runner reactions using both the old and new config schema
        '''
        for schema in ('old', 'new'):
            tag = '_'.join((schema, 'runner'))
            chunk = LOW_CHUNKS[tag][0]
            thread_pool = Mock()
            thread_pool.fire_async = Mock()
            with patch.object(self.wrap, 'pool', thread_pool):
                self.wrap.run(chunk)
            thread_pool.fire_async.assert_called_with(
                self.wrap.client_cache['runner'].low,
                args=WRAPPER_CALLS[tag]
            )

    def test_wheel(self):
        '''
        Test wheel reactions using both the old and new config schema
        '''
        for schema in ('old', 'new'):
            tag = '_'.join((schema, 'wheel'))
            chunk = LOW_CHUNKS[tag][0]
            thread_pool = Mock()
            thread_pool.fire_async = Mock()
            with patch.object(self.wrap, 'pool', thread_pool):
                self.wrap.run(chunk)
            thread_pool.fire_async.assert_called_with(
                self.wrap.client_cache['wheel'].low,
                args=WRAPPER_CALLS[tag]
            )

    def test_local(self):
        '''
        Test local reactions using both the old and new config schema
        '''
        for schema in ('old', 'new'):
            tag = '_'.join((schema, 'local'))
            chunk = LOW_CHUNKS[tag][0]
            client_cache = {'local': Mock()}
            client_cache['local'].cmd_async = Mock()
            with patch.object(self.wrap, 'client_cache', client_cache):
                self.wrap.run(chunk)
            client_cache['local'].cmd_async.assert_called_with(
                *WRAPPER_CALLS[tag]['args'],
                **WRAPPER_CALLS[tag]['kwargs']
            )

    def test_cmd(self):
        '''
        Test cmd reactions (alias for 'local') using both the old and new
        config schema
        '''
        for schema in ('old', 'new'):
            tag = '_'.join((schema, 'cmd'))
            chunk = LOW_CHUNKS[tag][0]
            client_cache = {'local': Mock()}
            client_cache['local'].cmd_async = Mock()
            with patch.object(self.wrap, 'client_cache', client_cache):
                self.wrap.run(chunk)
            client_cache['local'].cmd_async.assert_called_with(
                *WRAPPER_CALLS[tag]['args'],
                **WRAPPER_CALLS[tag]['kwargs']
            )

    def test_caller(self):
        '''
        Test caller reactions using both the old and new config schema
        '''
        for schema in ('old', 'new'):
            tag = '_'.join((schema, 'caller'))
            chunk = LOW_CHUNKS[tag][0]
            client_cache = {'caller': Mock()}
            client_cache['caller'].cmd = Mock()
            with patch.object(self.wrap, 'client_cache', client_cache):
                self.wrap.run(chunk)
            client_cache['caller'].cmd.assert_called_with(
                *WRAPPER_CALLS[tag]['args'],
                **WRAPPER_CALLS[tag]['kwargs']
            )
