# -*- coding: utf-8 -*-
"""
Test case for env sdb module
"""
from __future__ import absolute_import, print_function, unicode_literals

import os
import textwrap

# Import salt libs
import salt.utils.files

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.runtests import RUNTIME_VARS


class EnvTestCase(ModuleCase, SaltReturnAssertsMixin):
    def setUp(self):
        self.state_name = "test_sdb_env"
        self.state_file_name = self.state_name + ".sls"
        self.state_file_set_var = os.path.join(
            RUNTIME_VARS.BASE_FILES, self.state_file_name
        )
        with salt.utils.files.fopen(self.state_file_set_var, "w") as wfh:
            wfh.write(
                textwrap.dedent(
                    """\
                set some env var:
                  cmd.run:
                    - name: echo {{ salt['sdb.set']('sdb://osenv/foo', 'bar') }}
                    - order: 1

                {% if salt['sdb.get']('sdb://osenv/foo') == 'bar' %}
                always-changes-and-succeeds:
                  test.succeed_with_changes:
                    - name: foo
                {% else %}
                always-changes-and-fails:
                  test.fail_with_changes:
                    - name: foo
                {% endif  %}
                """
                )
            )

    def tearDown(self):
        os.remove(self.state_file_set_var)

    def test_env_module_sets_key(self):
        state_key = "test_|-always-changes-and-succeeds_|-foo_|-succeed_with_changes"
        ret = self.run_function("state.sls", [self.state_name])
        self.assertTrue(ret[state_key]["result"])
