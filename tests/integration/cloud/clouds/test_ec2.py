# -*- coding: utf-8 -*-
'''
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import yaml

# Import Salt Libs
from salt.config import cloud_providers_config
import salt.utils.cloud
import salt.utils.files
import salt.utils.yaml

# Import Salt Testing Libs
from tests.support.case import ShellCase
from tests.support.runtests import RUNTIME_VARS
from tests.support.helpers import expensiveTest, generate_random_name
from tests.support.unit import skipIf, WAR_ROOM_SKIP
from tests.support import win_installer


# Create the cloud instance name to be used throughout the tests
INSTANCE_NAME = generate_random_name('CLOUD-TEST-')
PROVIDER_NAME = 'ec2'
HAS_WINRM = salt.utils.cloud.HAS_WINRM and salt.utils.cloud.HAS_SMB
TIMEOUT = 1200


class EC2Test(CloudTest):
    '''
    Integration tests for the EC2 cloud provider in Salt-Cloud
    '''
    PROVIDER = 'ec2'
    REQUIRED_PROVIDER_CONFIG_ITEMS = ('id', 'key', 'keyname', 'private_key', 'location')

    @expensiveTest
    def setUp(self):
        '''
        Sets up the test requirements
        '''
        group_or_subnet = self.provider_config.get('securitygroup')
        if not group_or_subnet:
            group_or_subnet = self.provider_config.get('subnetid')

        if not group_or_subnet:
            self.skipTest('securitygroup or subnetid missing for {} config'.format(self.PROVIDER))

        for item in conf_items:
            if item == '':
                missing_conf_item.append(item)

        if missing_conf_item:
            self.skipTest(
                'An id, key, keyname, security group, private key, and location must '
                'be provided to run these tests. One or more of these elements is '
                'missing. Check tests/integration/files/conf/cloud.providers.d/{0}.conf'
                .format(PROVIDER_NAME)
            )
        self.INSTALLER = self._ensure_installer()

    def override_profile_config(self, name, data):
        conf_path = os.path.join(self.config_dir, 'cloud.profiles.d', 'ec2.conf')
        with salt.utils.files.fopen(conf_path, 'r') as fp:
            conf = yaml.safe_load(fp)
        conf[name].update(data)
        with salt.utils.files.fopen(conf_path, 'w') as fp:
            salt.utils.yaml.safe_dump(conf, fp)

    def copy_file(self, name):
        '''
        Copy a file from tests/integration/files to a test's temporary
        configuration directory. The path to the file which is created will be
        returned.
        '''
        src = os.path.join(RUNTIME_VARS.FILES, name)
        dst = os.path.join(self.config_dir, name)
        with salt.utils.files.fopen(src, 'rb') as sfp:
            with salt.utils.files.fopen(dst, 'wb') as dfp:
                dfp.write(sfp.read())
        return dst

    def _test_instance(self, profile='ec2-test', debug=False, timeout=TIMEOUT):
        '''
        Tests creating and deleting an instance on EC2 (classic)
        '''

        # create the instance
        cmd = '-p {0}'.format(profile)
        if debug:
            cmd += ' -l debug'
        cmd += ' {0}'.format(INSTANCE_NAME)
        instance = self.run_cloud(cmd, timeout=timeout)
        ret_str = '{0}:'.format(INSTANCE_NAME)

        # check if instance returned with salt installed
        try:
            self.assertIn(ret_str, instance)
        except AssertionError:
            self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME), timeout=timeout)
            raise

        # delete the instance
        delete = self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME), timeout=timeout)
        ret_str = '                    shutting-down'

        self.assertDestroyInstance()

    def test_instance_rename(self):
        '''
        Tests creating and renaming an instance on EC2 (classic)
        '''
        # create the instance
        rename = INSTANCE_NAME + '-rename'
        instance = self.run_cloud('-p ec2-test {0} --no-deploy'.format(INSTANCE_NAME), timeout=TIMEOUT)
        ret_str = '{0}:'.format(INSTANCE_NAME)

        # check if instance returned
        try:
            self.assertIn(ret_str, instance)
        except AssertionError:
            self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME), timeout=TIMEOUT)
            raise

        change_name = self.run_cloud('-a rename {0} newname={1} --assume-yes'.format(INSTANCE_NAME, rename), timeout=TIMEOUT)

        check_rename = self.run_cloud('-a show_instance {0} --assume-yes'.format(rename), [rename])
        exp_results = ['        {0}:'.format(rename), '            size:',
                       '            architecture:']
        try:
            for result in exp_results:
                self.assertIn(result, check_rename[0])
        except AssertionError:
            self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME), timeout=TIMEOUT)
            raise

        self.assertDestroyInstance()

    def test_instance(self):
        '''
        Tests creating and deleting an instance on EC2 (classic)
        '''
        self._test_instance('ec2-test')

    def test_win2012r2_psexec(self):
        '''
        Tests creating and deleting a Windows 2012r2instance on EC2 using
        psexec (classic)
        '''
        # TODO: psexec calls hang and the test fails by timing out. The same
        # same calls succeed when run outside of the test environment.
        self.override_profile_config(
            'ec2-win2012r2-test',
            {
                'use_winrm': False,
                'userdata_file': self.copy_file('windows-firewall-winexe.ps1'),
                'win_installer': self.copy_file(self.installer),
            },
        )
        self._test_instance('ec2-win2012r2-test', debug=True, timeout=TIMEOUT)

    @skipIf(not HAS_WINRM, 'Skip when winrm dependencies are missing')
    def test_win2012r2_winrm(self):
        '''
        Tests creating and deleting a Windows 2012r2 instance on EC2 using
        winrm (classic)
        '''
        self.override_profile_config(
            'ec2-win2012r2-test',
            {
                'userdata_file': self.copy_file('windows-firewall.ps1'),
                'win_installer': self.copy_file(self.installer),
                'winrm_ssl_verify': False,
                'use_winrm': True,
            }

        )
        self._test_instance('ec2-win2012r2-test', debug=True, timeout=TIMEOUT)

    def test_win2016_psexec(self):
        '''
        Tests creating and deleting a Windows 2016 instance on EC2 using winrm
        (classic)
        '''
        # TODO: winexe calls hang and the test fails by timing out. The same
        # same calls succeed when run outside of the test environment.
        self.override_profile_config(
            'ec2-win2016-test',
            {
                'use_winrm': False,
                'userdata_file': self.copy_file('windows-firewall-winexe.ps1'),
                'win_installer': self.copy_file(self.installer),
            },
        )
        self._test_instance('ec2-win2016-test', debug=True, timeout=TIMEOUT)

    @skipIf(not HAS_WINRM, 'Skip when winrm dependencies are missing')
    def test_win2016_winrm(self):
        '''
        Tests creating and deleting a Windows 2016 instance on EC2 using winrm
        (classic)
        '''
        self.override_profile_config(
            'ec2-win2016-test',
            {
                'userdata_file': self.copy_file('windows-firewall.ps1'),
                'win_installer': self.copy_file(self.installer),
                'winrm_ssl_verify': False,
                'use_winrm': True,
            }

        )
        self._test_instance('ec2-win2016-test', debug=True, timeout=TIMEOUT)

    def tearDown(self):
        '''
        Clean up after tests
        '''
        query = self.run_cloud('--query')
        ret_str = '        {0}:'.format(INSTANCE_NAME)

        # if test instance is still present, delete it
        if ret_str in query:
            self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME), timeout=TIMEOUT)
