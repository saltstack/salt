# -*- coding: utf-8 -*-
'''
Tests for the file state
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import errno
import os
import textwrap
import tempfile

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.paths import TMP_STATE_TREE
from tests.support.mixins import SaltReturnAssertsMixin

# Import Salt libs
import salt.utils.files
import salt.utils.platform

IS_WINDOWS = salt.utils.platform.is_windows()


class CMDTest(ModuleCase, SaltReturnAssertsMixin):
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

    def test_run_hide_output(self):
        '''
        cmd.run with output hidden
        '''
        ret = self.run_state(
            u'cmd.run',
            name=u'ls',
            hide_output=True)
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertEqual(ret[u'changes'][u'stdout'], u'')
        self.assertEqual(ret[u'changes'][u'stderr'], u'')


class CMDRunRedirectTest(ModuleCase, SaltReturnAssertsMixin):
    '''
    Validate the cmd state of run_redirect
    '''
    def setUp(self):
        self.state_name = 'run_redirect'
        state_filename = self.state_name + '.sls'
        self.state_file = os.path.join(TMP_STATE_TREE, state_filename)

        # Create the testfile and release the handle
        fd, self.test_file = tempfile.mkstemp()
        try:
            os.close(fd)
        except OSError as exc:
            if exc.errno != errno.EBADF:
                raise exc

        # Create the testfile and release the handle
        fd, self.test_tmp_path = tempfile.mkstemp()
        try:
            os.close(fd)
        except OSError as exc:
            if exc.errno != errno.EBADF:
                raise exc

        super(CMDRunRedirectTest, self).setUp()

    def tearDown(self):
        for path in (self.state_file, self.test_tmp_path, self.test_file):
            try:
                os.remove(path)
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
        state_key = 'cmd_|-{0}_|-{0}_|-run'.format(self.test_tmp_path)
        with salt.utils.files.fopen(self.state_file, 'w') as fb_:
            fb_.write(salt.utils.stringutils.to_str(textwrap.dedent('''
                {0}:
                  cmd.run:
                    - unless: echo cheese > {1}
                '''.format(self.test_tmp_path, self.test_file))))

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
        # command in the state. If the comment reads "unless condition is true", or similar,
        # then the unless state run bailed out after the first unless command succeeded,
        # which is the bug we're regression testing for.
        self.assertEqual(sls['cmd_|-cmd_run_unless_multiple_|-echo "hello"_|-run']['comment'],
                         'Command "echo "hello"" run')

    def test_run_creates_exists(self):
        '''
        test cmd.run creates already there
        '''
        state_key = 'cmd_|-echo >> {0}_|-echo >> {0}_|-run'.format(self.test_file)
        with salt.utils.files.fopen(self.state_file, 'w') as fb_:
            fb_.write(salt.utils.stringutils.to_str(textwrap.dedent('''
                echo >> {0}:
                  cmd.run:
                    - creates: {0}
                '''.format(self.test_file))))

        ret = self.run_function('state.sls', [self.state_name])
        self.assertTrue(ret[state_key]['result'])
        self.assertEqual(len(ret[state_key]['changes']), 0)

    def test_run_creates_new(self):
        '''
        test cmd.run creates not there
        '''
        os.remove(self.test_file)
        state_key = 'cmd_|-echo >> {0}_|-echo >> {0}_|-run'.format(self.test_file)
        with salt.utils.files.fopen(self.state_file, 'w') as fb_:
            fb_.write(salt.utils.stringutils.to_str(textwrap.dedent('''
                echo >> {0}:
                  cmd.run:
                    - creates: {0}
                '''.format(self.test_file))))

        ret = self.run_function('state.sls', [self.state_name])
        self.assertTrue(ret[state_key]['result'])
        self.assertEqual(len(ret[state_key]['changes']), 4)

    def test_run_redirect(self):
        '''
        test cmd.run with shell redirect
        '''
        state_key = 'cmd_|-echo test > {0}_|-echo test > {0}_|-run'.format(self.test_file)
        with salt.utils.files.fopen(self.state_file, 'w') as fb_:
            fb_.write(salt.utils.stringutils.to_str(textwrap.dedent('''
                echo test > {0}:
                  cmd.run
                '''.format(self.test_file))))

        ret = self.run_function('state.sls', [self.state_name])
        self.assertTrue(ret[state_key]['result'])


class CMDRunWatchTest(ModuleCase, SaltReturnAssertsMixin):
    '''
    Validate the cmd state of run_watch
    '''
    def setUp(self):
        self.state_name = 'run_watch'
        state_filename = self.state_name + '.sls'
        self.state_file = os.path.join(TMP_STATE_TREE, state_filename)
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

        with salt.utils.files.fopen(self.state_file, 'w') as fb_:
            fb_.write(salt.utils.stringutils.to_str(textwrap.dedent('''
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
                ''')))

        ret = self.run_function('state.sls', [self.state_name])
        self.assertTrue(ret[saltines_key]['result'])
        self.assertTrue(ret[biscuits_key]['result'])
