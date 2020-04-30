# -*- coding: utf-8 -*-

from __future__ import absolute_import

import os
import textwrap

import pytest
import salt.utils.files
import salt.utils.platform
from tests.support.case import ModuleCase
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import skipIf


@pytest.mark.windows_whitelisted
class EnabledTest(ModuleCase):
    """
    validate the use of shell processing for cmd.run on the salt command line
    and in templating
    """

    cmd = (
        "printf '%s\\n' first second third | wc -l ; "
        "export SALTY_VARIABLE='saltines' && echo $SALTY_VARIABLE ; "
        "echo duh &> /dev/null"
    )

    @skipIf(salt.utils.platform.is_windows(), "Skip on Windows OS")
    def test_shell_default_enabled(self):
        """
        ensure that python_shell defaults to True for cmd.run
        """
        enabled_ret = "3\nsaltines"  # the result of running self.cmd in a shell
        ret = self.run_function("cmd.run", [self.cmd])
        self.assertEqual(ret.strip(), enabled_ret)

    @skipIf(salt.utils.platform.is_windows(), "Skip on Windows OS")
    def test_shell_disabled(self):
        """
        test shell disabled output for cmd.run
        """
        disabled_ret = (
            "first\nsecond\nthird\n|\nwc\n-l\n;\nexport\nSALTY_VARIABLE=saltines"
            "\n&&\necho\n$SALTY_VARIABLE\n;\necho\nduh\n&>\n/dev/null"
        )
        ret = self.run_function("cmd.run", [self.cmd], python_shell=False)
        self.assertEqual(ret, disabled_ret)

    @skipIf(salt.utils.platform.is_windows(), "Skip on Windows OS")
    def test_template_shell(self):
        """
        Test cmd.shell works correctly when using a template.

        Note: This test used to test that python_shell defaulted to True for templates
        in releases before 2017.7.0. The cmd.run --> cmd.shell aliasing was removed in
        2017.7.0. Templates should now be using cmd.shell.
        """
        state_name = "template_shell_enabled"
        state_filename = state_name + ".sls"
        state_file = os.path.join(RUNTIME_VARS.BASE_FILES, state_filename)

        enabled_ret = "3 saltines"  # the result of running self.cmd in a shell
        ret_key = "test_|-shell_enabled_|-{0}_|-configurable_test_state".format(
            enabled_ret
        )

        try:
            with salt.utils.files.fopen(state_file, "w") as fp_:
                fp_.write(
                    textwrap.dedent(
                        """\
                {{% set shell_enabled = salt['cmd.shell']("{0}").strip() %}}

                shell_enabled:
                  test.configurable_test_state:
                    - name: '{{{{ shell_enabled }}}}'
                """.format(
                            self.cmd
                        )
                    )
                )

            ret = self.run_function("state.sls", [state_name])
            self.assertEqual(ret[ret_key]["name"], enabled_ret)
        finally:
            os.remove(state_file)

    @skipIf(salt.utils.platform.is_windows(), "Skip on Windows OS")
    @skipIf(True, "SLOWTEST skip")
    def test_template_default_disabled(self):
        """
        test shell disabled output for templates (python_shell=False is the default
        beginning with the 2017.7.0 release).
        """
        state_name = "template_shell_disabled"
        state_filename = state_name + ".sls"
        state_file = os.path.join(RUNTIME_VARS.BASE_FILES, state_filename)

        # the result of running self.cmd not in a shell
        disabled_ret = (
            "first second third | wc -l ; export SALTY_VARIABLE=saltines "
            "&& echo $SALTY_VARIABLE ; echo duh &> /dev/null"
        )
        ret_key = "test_|-shell_enabled_|-{0}_|-configurable_test_state".format(
            disabled_ret
        )

        try:
            with salt.utils.files.fopen(state_file, "w") as fp_:
                fp_.write(
                    textwrap.dedent(
                        """\
                {{% set shell_disabled = salt['cmd.run']("{0}") %}}

                shell_enabled:
                  test.configurable_test_state:
                    - name: '{{{{ shell_disabled }}}}'
                """.format(
                            self.cmd
                        )
                    )
                )

            ret = self.run_function("state.sls", [state_name])
            self.assertEqual(ret[ret_key]["name"], disabled_ret)
        finally:
            os.remove(state_file)
