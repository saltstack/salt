# -*- coding: utf-8 -*-
'''
Tests for the file state
'''
# Import python libs
from __future__ import absolute_import
import errno
import os
import textwrap
import tempfile

# Import Salt Testing libs
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

        # Create the testfile and release the handle
        self.fd, self.test_file = tempfile.mkstemp()
        try:
            os.close(self.fd)
        except OSError as exc:
            if exc.errno != errno.EBADF:
                raise exc

        super(CMDRunRedirectTest, self).setUp()

    def tearDown(self):
        try:
            os.remove(self.state_file)
            os.remove(self.test_file)
        except OSError:
            # Not all of the tests leave files around that we want to remove
            # As some of the tests create the sls files in the test itself,
            # And some are using files in the integration test file state tree.
            pass
        super(CMDRunRedirectTest, self).tearDown()

    def test_run_unless(self):
        '''
        test cmd.run unless
        '''
        state_key = 'cmd_|-/var/log/messages_|-/var/log/messages_|-run'
        with salt.utils.fopen(self.state_file, 'w') as fb_:
            fb_.write(textwrap.dedent('''
                /var/log/messages:
                  cmd.run:
                    - unless: echo cheese > {0}
                '''.format(self.test_file)))

        ret = self.run_function('state.sls', [self.state_name])
        self.assertTrue(ret[state_key]['result'])

    def test_run_unless_multiple_cmds(self):
        '''
        test cmd.run using multiple unless options where the first cmd in the
        list will pass, but the second will fail. This tests the fix for issue
        #35384. (The fix is in PR #35545.)
        '''
        sls = self.run_function('state.sls', mods='issue-35384')
        self.assertSaltTrueReturn(sls)
        # We must assert against the comment here to make sure the comment reads that the
        # command "echo "hello"" was run. This ensures that we made it to the last unless
        # command in the state. If the comment reads "unless execution succeeded", or similar,
        # then the unless state run bailed out after the first unless command succeeded,
        # which is the bug we're regression testing for.
        self.assertEqual(sls['cmd_|-cmd_run_unless_multiple_|-echo "hello"_|-run']['comment'],
                         'Command "echo "hello"" run')

    def test_run_creates_exists(self):
        '''
        test cmd.run creates already there
        '''
        state_key = 'cmd_|-echo >> {0}_|-echo >> {0}_|-run'.format(self.test_file)
        with salt.utils.fopen(self.state_file, 'w') as fb_:
            fb_.write(textwrap.dedent('''
                echo >> {0}:
                  cmd.run:
                    - creates: {0}
                '''.format(self.test_file)))

        ret = self.run_function('state.sls', [self.state_name])
        self.assertTrue(ret[state_key]['result'])
        self.assertEqual(len(ret[state_key]['changes']), 0)

    def test_run_creates_new(self):
        '''
        test cmd.run creates not there
        '''
        os.remove(self.test_file)
        state_key = 'cmd_|-echo >> {0}_|-echo >> {0}_|-run'.format(self.test_file)
        with salt.utils.fopen(self.state_file, 'w') as fb_:
            fb_.write(textwrap.dedent('''
                echo >> {0}:
                  cmd.run:
                    - creates: {0}
                '''.format(self.test_file)))

        ret = self.run_function('state.sls', [self.state_name])
        self.assertTrue(ret[state_key]['result'])
        self.assertEqual(len(ret[state_key]['changes']), 4)

    def test_run_redirect(self):
        '''
        test cmd.run with shell redirect
        '''
        state_key = 'cmd_|-echo test > {0}_|-echo test > {0}_|-run'.format(self.test_file)
        with salt.utils.fopen(self.state_file, 'w') as fb_:
            fb_.write(textwrap.dedent('''
                echo test > {0}:
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

    def test_run_watch(self):
        '''
        test cmd.run watch
        '''
        saltines_key = 'cmd_|-saltines_|-echo changed=true_|-run'
        biscuits_key = 'cmd_|-biscuits_|-echo biscuits_|-wait'

        with salt.utils.fopen(self.state_file, 'w') as fb_:
            fb_.write(textwrap.dedent('''
                saltines:
                  cmd.run:
                    - name: echo changed=true
                    - cwd: /
                    - stateful: True

                biscuits:
                  cmd.wait:
                    - name: echo biscuits
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
