# -*- coding: utf-8 -*-
'''
Tests for the file state
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import textwrap
import tempfile

# Import Salt Testing libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.case import ModuleCase
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.unit import skipIf, WAR_ROOM_SKIP; skipIf(WAR_ROOM_SKIP, 'WAR ROOM TEMPORARY SKIP')  # pylint: disable=C0321,E8702

# Import Salt libs
import salt.utils.files
import salt.utils.platform

IS_WINDOWS = salt.utils.platform.is_windows()


class CMDTest(ModuleCase, SaltReturnAssertsMixin):
    '''
    Validate the cmd state
    '''
    @classmethod
    def setUpClass(cls):
        cls.cmd = 'dir' if IS_WINDOWS else 'ls'

    def test_run_simple(self):
        '''
        cmd.run
        '''
        ret = self.run_state(
            'cmd.run',
            name=self.cmd,
            cwd=tempfile.gettempdir())
        self.assertSaltTrueReturn(ret)

    def test_run_simple_test_true(self):
        '''
        cmd.run test interface
        '''
        ret = self.run_state(
            'cmd.run',
            name=self.cmd,
            cwd=tempfile.gettempdir(),
            test=True)
        self.assertSaltNoneReturn(ret)

    def test_run_hide_output(self):
        '''
        cmd.run with output hidden
        '''
        ret = self.run_state(
            u'cmd.run',
            name=self.cmd,
            hide_output=True)
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertEqual(ret[u'changes'][u'stdout'], u'')
        self.assertEqual(ret[u'changes'][u'stderr'], u'')


class CMDRunWatchTest(ModuleCase, SaltReturnAssertsMixin):
    '''
    Validate the cmd state of run_watch
    '''
    def setUp(self):
        self.state_name = 'run_watch'
        state_filename = self.state_name + '.sls'
        self.state_file = os.path.join(RUNTIME_VARS.TMP_STATE_TREE, state_filename)
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
