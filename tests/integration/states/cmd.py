# -*- coding: utf-8 -*-
'''
Tests for the file state
'''
# Import python libs
from __future__ import absolute_import
import os
import textwrap
import tempfile

# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils

IS_WINDOWS = salt.utils.is_windows()
STATE_DIR = os.path.join(integration.FILES, 'file', 'base')


class CMDTest(integration.ModuleCase,
              integration.SaltReturnAssertsMixIn):
    '''
    Validate the cmd state
    '''
    def test_run_simple(self):
        '''
        cmd.run
        '''
        cmd = 'dir' if IS_WINDOWS else 'ls'
        ret = self.run_state('cmd.run', name=cmd, cwd=tempfile.gettempdir())
        self.assertSaltTrueReturn(ret)

    def test_test_run_simple(self):
        '''
        cmd.run test interface
        '''
        ret = self.run_state('cmd.run', name='ls',
                             cwd=tempfile.gettempdir(), test=True)
        self.assertSaltNoneReturn(ret)


class CMDRunRedirectTest(integration.ModuleCase,
                         integration.SaltReturnAssertsMixIn):
    '''
    Validate the cmd state of run_redirect
    '''
    def setUp(self):
        self.state_name = 'run_redirect'
        state_filename = self.state_name + '.sls'
        self.state_file = os.path.join(STATE_DIR, state_filename)
        self.test_file = tempfile.mkstemp()[1]
        super(CMDRunRedirectTest, self).setUp()

    def tearDown(self):
        os.remove(self.state_file)
        os.remove(self.test_file)
        super(CMDRunRedirectTest, self).tearDown()

    @skipIf(IS_WINDOWS, 'Error 32 on Windows, file in use')
    def test_run_unless(self):
        '''
        test cmd.run unless
        '''
        state_key = 'cmd_|-/var/log/messages_|-/var/log/messages_|-run'
        with salt.utils.fopen(self.state_file, 'w') as fp_:
            fp_.write(textwrap.dedent('''\
            /var/log/messages:
              cmd.run:
                - unless: echo cheese > {0}
            '''.format(self.test_file)))

        ret = self.run_function('state.sls', [self.state_name])
        self.assertTrue(ret[state_key]['result'])

    @skipIf(IS_WINDOWS, 'Error 32 on Windows, file in use')
    def test_run_creates_exists(self):
        '''
        test cmd.run creates already there
        '''
        state_key = 'cmd_|-touch {0}_|-touch {0}_|-run'.format(self.test_file)
        with salt.utils.fopen(self.state_file, 'w') as fp_:
            fp_.write(textwrap.dedent('''\
            touch {0}:
              cmd.run:
                - creates: {0}
            '''.format(self.test_file)))

        ret = self.run_function('state.sls', [self.state_name])
        self.assertTrue(ret[state_key]['result'])
        self.assertEqual(len(ret[state_key]['changes']), 0)

    @skipIf(IS_WINDOWS, 'Error 32 on Windows, file in use')
    def test_run_creates_new(self):
        '''
        test cmd.run creates not there
        '''
        os.remove(self.test_file)
        state_key = 'cmd_|-touch {0}_|-touch {0}_|-run'.format(self.test_file)
        with salt.utils.fopen(self.state_file, 'w') as fp_:
            fp_.write(textwrap.dedent('''\
            touch {0}:
              cmd.run:
                - creates: {0}
            '''.format(self.test_file)))

        ret = self.run_function('state.sls', [self.state_name])
        self.assertTrue(ret[state_key]['result'])
        self.assertEqual(len(ret[state_key]['changes']), 4)

    @skipIf(IS_WINDOWS, 'Error 32 on Windows, file in use')
    def test_run_redirect(self):
        '''
        test cmd.run with shell redirect
        '''
        state_key = 'cmd_|-date > {0}_|-date > {0}_|-run'.format(self.test_file)
        with salt.utils.fopen(self.state_file, 'w') as fp_:
            fp_.write(textwrap.dedent('''\
            date > {0}:
              cmd.run
            '''.format(self.test_file)))

        ret = self.run_function('state.sls', [self.state_name])
        self.assertTrue(ret[state_key]['result'])


class CMDRunWatchTest(integration.ModuleCase,
                      integration.SaltReturnAssertsMixIn):
    '''
    Validate the cmd state of run_watch
    '''
    def setUp(self):
        self.state_name = 'run_watch'
        state_filename = self.state_name + '.sls'
        self.state_file = os.path.join(STATE_DIR, state_filename)
        super(CMDRunWatchTest, self).setUp()

    def tearDown(self):
        os.remove(self.state_file)
        super(CMDRunWatchTest, self).tearDown()

    @skipIf(IS_WINDOWS, 'Need to fix for Windows')
    def test_run_watch(self):
        '''
        test cmd.run watch
        '''
        saltines_key = 'cmd_|-saltines_|-echo_|-run'
        biscuits_key = 'cmd_|-biscuits_|-echo hello_|-wait'

        with salt.utils.fopen(self.state_file, 'w') as fp_:
            fp_.write(textwrap.dedent('''\
            saltines:
              cmd.run:
                - name: echo
                - cwd: /
                - stateful: True

            biscuits:
              cmd.wait:
                - name: echo hello
                - cwd: /
                - watch:
                    - cmd: saltines
            '''))

        ret = self.run_function('state.sls', [self.state_name])
        self.assertTrue(ret[saltines_key]['result'])
        self.assertTrue(ret[biscuits_key]['result'])


if __name__ == '__main__':
    from integration import run_tests
    run_tests([CMDTest, CMDRunRedirectTest, CMDRunWatchTest])
