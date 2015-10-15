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
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils


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
        ret = self.run_state('cmd.run', name='ls', cwd=tempfile.gettempdir())
        self.assertSaltTrueReturn(ret)

    def test_test_run_simple(self):
        '''
        cmd.run test interface
        '''
        ret = self.run_state('cmd.run', name='ls',
                             cwd=tempfile.gettempdir(), test=True)
        self.assertSaltNoneReturn(ret)

    def test_run_redirect(self):
        '''
        test cmd.run with shell redirect
        '''
        state_name = 'run_redirect'
        state_filename = state_name + '.sls'
        state_file = os.path.join(STATE_DIR, state_filename)

        date_file = tempfile.mkstemp()[1]
        state_key = 'cmd_|-date > {0}_|-date > {0}_|-run'.format(date_file)
        try:
            salt.utils.fopen(state_file, 'w').write(textwrap.dedent('''\
                date > {0}:
                  cmd.run
                '''.format(date_file)))

            ret = self.run_function('state.sls', [state_name])
            self.assertTrue(ret[state_key]['result'])
        finally:
            os.remove(state_file)
            os.remove(date_file)

    def test_run_unless(self):
        '''
        test cmd.run unless
        '''
        state_name = 'run_redirect'
        state_filename = state_name + '.sls'
        state_file = os.path.join(STATE_DIR, state_filename)

        unless_file = tempfile.mkstemp()[1]
        state_key = 'cmd_|-/var/log/messages_|-/var/log/messages_|-run'
        try:
            salt.utils.fopen(state_file, 'w').write(textwrap.dedent('''\
                /var/log/messages:
                  cmd.run:
                    - unless: echo cheese > {0}
                '''.format(unless_file)))

            ret = self.run_function('state.sls', [state_name])
            self.assertTrue(ret[state_key]['result'])
        finally:
            os.remove(state_file)
            os.remove(unless_file)

    def test_run_creates_exists(self):
        '''
        test cmd.run creates already there
        '''
        state_name = 'run_redirect'
        state_filename = state_name + '.sls'
        state_file = os.path.join(STATE_DIR, state_filename)

        creates_file = tempfile.mkstemp()[1]
        state_key = 'cmd_|-touch {0}_|-touch {0}_|-run'.format(creates_file)
        try:
            salt.utils.fopen(state_file, 'w').write(textwrap.dedent('''\
                touch {0}:
                  cmd.run:
                    - creates: {0}
                '''.format(creates_file)))

            ret = self.run_function('state.sls', [state_name])
            self.assertTrue(ret[state_key]['result'])
            self.assertEqual(len(ret[state_key]['changes']), 0)
        finally:
            os.remove(state_file)
            os.remove(creates_file)

    def test_run_creates_new(self):
        '''
        test cmd.run creates not there
        '''
        state_name = 'run_redirect'
        state_filename = state_name + '.sls'
        state_file = os.path.join(STATE_DIR, state_filename)

        creates_file = tempfile.mkstemp()[1]
        os.remove(creates_file)
        state_key = 'cmd_|-touch {0}_|-touch {0}_|-run'.format(creates_file)
        try:
            salt.utils.fopen(state_file, 'w').write(textwrap.dedent('''\
                touch {0}:
                  cmd.run:
                    - creates: {0}
                '''.format(creates_file)))

            ret = self.run_function('state.sls', [state_name])
            self.assertTrue(ret[state_key]['result'])
            self.assertEqual(len(ret[state_key]['changes']), 4)
        finally:
            os.remove(state_file)
            os.remove(creates_file)

    def test_run_watch(self):
        '''
        test cmd.run watch
        '''
        state_name = 'run_watch'
        state_filename = state_name + '.sls'
        state_file = os.path.join(STATE_DIR, state_filename)

        saltines_key = 'cmd_|-saltines_|-/bin/true_|-run'
        biscuits_key = 'cmd_|-biscuits_|-echo hello_|-wait'

        try:
            salt.utils.fopen(state_file, 'w').write(textwrap.dedent('''\
                saltines:
                  cmd.run:
                    - name: /bin/true
                    - cwd: /
                    - stateful: True

                biscuits:
                  cmd.wait:
                    - name: echo hello
                    - cwd: /
                    - watch:
                        - cmd: saltines
                '''))

            ret = self.run_function('state.sls', [state_name])
            self.assertTrue(ret[saltines_key]['result'])
            self.assertTrue(ret[biscuits_key]['result'])
        finally:
            os.remove(state_file)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(CMDTest)
