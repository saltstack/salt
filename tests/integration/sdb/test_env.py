# -*- coding: utf-8 -*-
'''
Test case for env sdb module
'''
from __future__ import absolute_import
import os
import textwrap

# Import Salt Testing libs
import tests.integration as integration

# Import salt libs
import salt.utils

STATE_DIR = os.path.join(integration.FILES, 'file', 'base')


class EnvTestCase(integration.ModuleCase,
                  integration.SaltReturnAssertsMixin):

    def setUp(self):
        self.state_name = 'test_sdb_env'
        self.state_file_name = self.state_name + '.sls'
        self.state_file_set_var = os.path.join(STATE_DIR, self.state_file_name)
        salt.utils.fopen(self.state_file_set_var, 'w').write(textwrap.dedent('''\
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
                '''))

    def tearDown(self):
        os.remove(self.state_file_set_var)

    def test_env_module_sets_key(self):
        state_key = 'test_|-always-changes-and-succeeds_|-foo_|-succeed_with_changes'
        ret = self.run_function('state.sls', [self.state_name])
        self.assertTrue(ret[state_key]['result'])
