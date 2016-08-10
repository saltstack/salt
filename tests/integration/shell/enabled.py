# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import
import os
import textwrap

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
import integration
import salt.utils


STATE_DIR = os.path.join(integration.FILES, 'file', 'base')


class EnabledTest(integration.ModuleCase):
    '''
    validate the use of shell processing for cmd.run on the salt command line
    and in templating
    '''
    cmd = ("printf '%s\n' first second third | wc -l ; "
           "export SALTY_VARIABLE='saltines' && echo $SALTY_VARIABLE ; "
           "echo duh &> /dev/null")

    def test_shell_default_enabled(self):
        '''
        ensure that python_shell defaults to True for cmd.run
        '''
        enabled_ret = '3\nsaltines'  # the result of running self.cmd in a shell
        ret = self.run_function('cmd.run', [self.cmd])
        self.assertEqual(ret.strip(), enabled_ret)

    def test_shell_disabled(self):
        '''
        test shell disabled output for cmd.run
        '''
        disabled_ret = ('first\nsecond\nthird\n|\nwc\n-l\n;\nexport\nSALTY_VARIABLE=saltines'
                        '\n&&\necho\n$SALTY_VARIABLE\n;\necho\nduh\n&>\n/dev/null')
        ret = self.run_function('cmd.run', [self.cmd], python_shell=False)
        self.assertEqual(ret, disabled_ret)

    def test_template_default_enabled(self):
        '''
        ensure that python_shell defaults to True for templates
        '''
        state_name = 'template_shell_enabled'
        state_filename = state_name + '.sls'
        state_file = os.path.join(STATE_DIR, state_filename)

        enabled_ret = '3 saltines'  # the result of running self.cmd in a shell
        ret_key = 'test_|-shell_enabled_|-{0}_|-configurable_test_state'.format(enabled_ret)

        try:
            salt.utils.fopen(state_file, 'w').write(textwrap.dedent('''\
                {{% set shell_enabled = salt['cmd.run']("{0}").strip() %}}

                shell_enabled:
                  test.configurable_test_state:
                    - name: '{{{{ shell_enabled }}}}'
                '''.format(self.cmd)))

            ret = self.run_function('state.sls', [state_name])
            self.assertEqual(ret[ret_key]['name'], enabled_ret)
        finally:
            os.remove(state_file)

    def test_template_disabled(self):
        '''
        test shell disabled output for templates
        '''
        state_name = 'template_shell_disabled'
        state_filename = state_name + '.sls'
        state_file = os.path.join(STATE_DIR, state_filename)

        # the result of running self.cmd not in a shell
        disabled_ret = ('first second third | wc -l ; export SALTY_VARIABLE=saltines '
                        '&& echo $SALTY_VARIABLE ; echo duh &> /dev/null')
        ret_key = 'test_|-shell_enabled_|-{0}_|-configurable_test_state'.format(disabled_ret)

        try:
            salt.utils.fopen(state_file, 'w').write(textwrap.dedent('''\
                {{% set shell_disabled = salt['cmd.run']("{0}", python_shell=False) %}}

                shell_enabled:
                  test.configurable_test_state:
                    - name: '{{{{ shell_disabled }}}}'
                '''.format(self.cmd)))

            ret = self.run_function('state.sls', [state_name])
            self.assertEqual(ret[ret_key]['name'], disabled_ret)
        finally:
            os.remove(state_file)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(EnabledTest)
