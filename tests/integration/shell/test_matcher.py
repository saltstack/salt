# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import os
import shutil
import time

# Import Salt Testing libs
from tests.support.case import ShellCase
from tests.support.paths import TMP
from tests.support.mixins import ShellCaseCommonTestsMixin

# Import salt libs
import salt.utils.files
import salt.utils.yaml


def minion_in_returns(minion, lines):
    return bool([True for line in lines if line == '{0}:'.format(minion)])


class MatchTest(ShellCase, ShellCaseCommonTestsMixin):
    '''
    Test salt matchers
    '''
    _call_binary_ = 'salt'

    def test_list(self):
        '''
        test salt -L matcher
        '''
        data = self.run_salt('-L minion test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertNotIn('sub_minion', data)
        data = self.run_salt('-L minion,sub_minion test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertIn('sub_minion', data)

    def test_compound(self):
        '''
        test salt compound matcher
        '''
        data = self.run_salt('-C "min* and G@test_grain:cheese" test.ping')
        self.assertTrue(minion_in_returns('minion', data))
        self.assertFalse(minion_in_returns('sub_minion', data))
        time.sleep(2)
        data = self.run_salt('-C "min* and not G@test_grain:foo" test.ping')
        self.assertTrue(minion_in_returns('minion', data))
        self.assertFalse(minion_in_returns('sub_minion', data))
        time.sleep(2)
        data = self.run_salt('-C "min* not G@test_grain:foo" test.ping')
        self.assertTrue(minion_in_returns('minion', data))
        self.assertFalse(minion_in_returns('sub_minion', data))
        time.sleep(2)
        match = 'P@test_grain:^cheese$ and * and G@test_grain:cheese'
        data = self.run_salt('-t 1 -C \'{0}\' test.ping'.format(match))
        self.assertTrue(minion_in_returns('minion', data))
        self.assertFalse(minion_in_returns('sub_minion', data))
        time.sleep(2)
        match = 'L@sub_minion and E@.*'
        data = self.run_salt('-t 1 -C "{0}" test.ping'.format(match))
        self.assertTrue(minion_in_returns('sub_minion', data))
        self.assertFalse(minion_in_returns('minion', data))
        time.sleep(2)
        data = self.run_salt("-C 'not sub_minion' test.ping")
        self.assertTrue(minion_in_returns('minion', data))
        self.assertFalse(minion_in_returns('sub_minion', data))
        time.sleep(2)
        data = self.run_salt("-C '* and ( not G@test_grain:cheese )' test.ping")
        self.assertFalse(minion_in_returns('minion', data))
        self.assertTrue(minion_in_returns('sub_minion', data))
        time.sleep(2)
        data = self.run_salt("-C 'G%@planets%merc*' test.ping")
        self.assertTrue(minion_in_returns('minion', data))
        self.assertFalse(minion_in_returns('sub_minion', data))
        time.sleep(2)
        data = self.run_salt("-C 'P%@planets%^(mercury|saturn)$' test.ping")
        self.assertTrue(minion_in_returns('minion', data))
        self.assertTrue(minion_in_returns('sub_minion', data))
        time.sleep(2)
        data = self.run_salt("-C 'I%@companions%three%sarah*' test.ping")
        self.assertTrue(minion_in_returns('minion', data))
        self.assertTrue(minion_in_returns('sub_minion', data))
        time.sleep(2)
        data = self.run_salt("-C 'J%@knights%^(Lancelot|Galahad)$' test.ping")
        self.assertTrue(minion_in_returns('minion', data))
        self.assertTrue(minion_in_returns('sub_minion', data))

    def test_nodegroup(self):
        '''
        test salt nodegroup matcher
        '''
        data = self.run_salt('-N min test.ping')
        self.assertTrue(minion_in_returns('minion', data))
        self.assertFalse(minion_in_returns('sub_minion', data))
        time.sleep(2)
        data = self.run_salt('-N sub_min test.ping')
        self.assertFalse(minion_in_returns('minion', data))
        self.assertTrue(minion_in_returns('sub_minion', data))
        time.sleep(2)
        data = self.run_salt('-N mins test.ping')
        self.assertTrue(minion_in_returns('minion', data))
        self.assertTrue(minion_in_returns('sub_minion', data))
        time.sleep(2)
        data = self.run_salt('-N unknown_nodegroup test.ping')
        self.assertFalse(minion_in_returns('minion', data))
        self.assertFalse(minion_in_returns('sub_minion', data))
        time.sleep(2)
        data = self.run_salt('-N redundant_minions test.ping')
        self.assertTrue(minion_in_returns('minion', data))
        self.assertTrue(minion_in_returns('sub_minion', data))
        time.sleep(2)
        data = '\n'.join(self.run_salt('-N nodegroup_loop_a test.ping'))
        self.assertIn('No minions matched', data)
        time.sleep(2)
        data = self.run_salt("-N multiline_nodegroup test.ping")
        self.assertTrue(minion_in_returns('minion', data))
        self.assertTrue(minion_in_returns('sub_minion', data))

    def test_glob(self):
        '''
        test salt glob matcher
        '''
        data = self.run_salt('minion test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertNotIn('sub_minion', data)
        data = self.run_salt('"*" test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertIn('sub_minion', data)

    def test_regex(self):
        '''
        test salt regex matcher
        '''
        data = self.run_salt('-E "^minion$" test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertNotIn('sub_minion', data)
        data = self.run_salt('-E ".*" test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertIn('sub_minion', data)

    def test_grain(self):
        '''
        test salt grain matcher
        '''
        # Sync grains
        self.run_salt('-t1 "*" saltutil.sync_grains')
        # First-level grain (string value)
        data = self.run_salt('-t 1 -G "test_grain:cheese" test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertNotIn('sub_minion', data)
        data = self.run_salt('-G "test_grain:spam" test.ping')
        data = '\n'.join(data)
        self.assertIn('sub_minion', data)
        self.assertNotIn('minion', data.replace('sub_minion', 'stub'))
        # Custom grain
        data = self.run_salt('-t 1 -G "match:maker" test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertIn('sub_minion', data)
        # First-level grain (list member)
        data = self.run_salt('-t 1 -G "planets:earth" test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertNotIn('sub_minion', data)
        data = self.run_salt('-G "planets:saturn" test.ping')
        data = '\n'.join(data)
        self.assertIn('sub_minion', data)
        self.assertNotIn('minion', data.replace('sub_minion', 'stub'))
        data = self.run_salt('-G "planets:pluto" test.ping')
        expect = None
        if self.master_opts['transport'] in ('zeromq', 'tcp'):
            expect = (
                'No minions matched the target. '
                'No command was sent, no jid was '
                'assigned.'
            )
        elif self.master_opts['transport'] == 'raet':
            expect = ''
        self.assertEqual(
            ''.join(data),
            expect
        )
        # Nested grain (string value)
        data = self.run_salt('-t 1 -G "level1:level2:foo" test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertNotIn('sub_minion', data)
        data = self.run_salt('-G "level1:level2:bar" test.ping')
        data = '\n'.join(data)
        self.assertIn('sub_minion', data)
        self.assertNotIn('minion', data.replace('sub_minion', 'stub'))
        # Nested grain (list member)
        data = self.run_salt('-t 1 -G "companions:one:ian" test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertNotIn('sub_minion', data)
        data = self.run_salt('-G "companions:two:jamie" test.ping')
        data = '\n'.join(data)
        self.assertIn('sub_minion', data)
        self.assertNotIn('minion', data.replace('sub_minion', 'stub'))
        # Test for issue: https://github.com/saltstack/salt/issues/19651
        data = self.run_salt('-G "companions:*:susan" test.ping')
        data = '\n'.join(data)
        self.assertIn('minion:', data)
        self.assertNotIn('sub_minion', data)
        # Test to ensure wildcard at end works correctly
        data = self.run_salt('-G "companions:one:*" test.ping')
        data = '\n'.join(data)
        self.assertIn('minion:', data)
        self.assertNotIn('sub_minion', data)
        # Test to ensure multiple wildcards works correctly
        data = self.run_salt('-G "companions:*:*" test.ping')
        data = '\n'.join(data)
        self.assertIn('minion:', data)
        self.assertIn('sub_minion', data)

    def test_regrain(self):
        '''
        test salt grain matcher
        '''
        data = self.run_salt(
            '-t 1 --grain-pcre "test_grain:^cheese$" test.ping'
        )
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertNotIn('sub_minion', data)
        data = self.run_salt('--grain-pcre "test_grain:.*am$" test.ping')
        data = '\n'.join(data)
        self.assertIn('sub_minion', data)
        self.assertNotIn('minion', data.replace('sub_minion', 'stub'))

    def test_pillar(self):
        '''
        test pillar matcher
        '''
        # First-level pillar (string value)
        data = self.run_salt('-I "monty:python" test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertIn('sub_minion', data)
        # First-level pillar (string value, only in sub_minion)
        data = self.run_salt('-I "sub:sub_minion" test.ping')
        data = '\n'.join(data)
        self.assertIn('sub_minion', data)
        self.assertNotIn('minion', data.replace('sub_minion', 'stub'))
        # First-level pillar (list member)
        data = self.run_salt('-I "knights:Bedevere" test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertIn('sub_minion', data)
        # Nested pillar (string value)
        data = self.run_salt('-I "level1:level2:foo" test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertIn('sub_minion', data)
        # Nested pillar (list member)
        data = self.run_salt('-I "companions:three:sarah jane" test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertIn('sub_minion', data)

    def test_repillar(self):
        '''
        test salt pillar PCRE matcher
        '''
        data = self.run_salt('-J "monty:^(python|hall)$" test.ping')
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertIn('sub_minion', data)
        data = self.run_salt('--pillar-pcre "knights:^(Robin|Lancelot)$" test.ping')
        data = '\n'.join(data)
        self.assertIn('sub_minion', data)
        self.assertIn('minion', data.replace('sub_minion', 'stub'))

    def test_ipcidr(self):
        subnets_data = self.run_salt('--out yaml \'*\' network.subnets')
        yaml_data = salt.utils.yaml.safe_load('\n'.join(subnets_data))

        # We're just after the first defined subnet from 'minion'
        subnet = yaml_data['minion'][0]

        data = self.run_salt('-S {0} test.ping'.format(subnet))
        data = '\n'.join(data)
        self.assertIn('minion', data)
        self.assertIn('sub_minion', data)

    def test_static(self):
        '''
        test salt static call
        '''
        data = self.run_salt('minion test.ping --static')
        data = '\n'.join(data)
        self.assertIn('minion', data)

    def test_salt_documentation(self):
        '''
        Test to see if we're supporting --doc
        '''
        data = self.run_salt('-d "*" user')
        self.assertIn('user.add:', data)

    def test_salt_documentation_arguments_not_assumed(self):
        '''
        Test to see if we're not auto-adding '*' and 'sys.doc' to the call
        '''
        os_family = self.run_call('--local grains.get os_family')[1].strip()
        if os_family == 'Arch':
            self.skipTest('This test is failing in Arch due to a bug in salt-testing. '
                          'Skipping until salt-testing can be upgraded. For more information, '
                          'see https://github.com/saltstack/salt-jenkins/issues/324.')
        data = self.run_salt('-d -t 20')
        if data:
            self.assertIn('user.add:', data)
        data = self.run_salt('"*" -d -t 20')
        if data:
            self.assertIn('user.add:', data)
        data = self.run_salt('"*" -d user -t 20')
        self.assertIn('user.add:', data)
        data = self.run_salt('"*" sys.doc -d user -t 20')
        self.assertIn('user.add:', data)
        data = self.run_salt('"*" sys.doc user -t 20')
        self.assertIn('user.add:', data)

    def test_salt_documentation_too_many_arguments(self):
        '''
        Test to see if passing additional arguments shows an error
        '''
        data = self.run_salt('-d minion salt ldap.search "filter=ou=People"', catch_stderr=True)
        self.assertIn('You can only get documentation for one method at one time', '\n'.join(data[1]))

    def test_issue_7754(self):
        old_cwd = os.getcwd()
        config_dir = os.path.join(TMP, 'issue-7754')
        if not os.path.isdir(config_dir):
            os.makedirs(config_dir)

        os.chdir(config_dir)

        config_file_name = 'master'
        with salt.utils.files.fopen(self.get_config_file_path(config_file_name), 'r') as fhr:
            config = salt.utils.yaml.safe_load(fhr)
            config['log_file'] = 'file:///dev/log/LOG_LOCAL3'
            with salt.utils.files.fopen(os.path.join(config_dir, config_file_name), 'w') as fhw:
                salt.utils.yaml.safe_dump(config, fhw, default_flow_style=False)
        ret = self.run_script(
            self._call_binary_,
            '--config-dir {0} minion test.ping'.format(
                config_dir
            ),
            timeout=60,
            catch_stderr=True,
            with_retcode=True
        )
        try:
            self.assertIn('minion', '\n'.join(ret[0]))
            self.assertFalse(os.path.isdir(os.path.join(config_dir, 'file:')))
        except AssertionError:
            # We now fail when we're unable to properly set the syslog logger
            self.assertIn(
                'Failed to setup the Syslog logging handler', '\n'.join(ret[1])
            )
            self.assertEqual(ret[2], 2)
        finally:
            self.chdir(old_cwd)
            if os.path.isdir(config_dir):
                shutil.rmtree(config_dir)
