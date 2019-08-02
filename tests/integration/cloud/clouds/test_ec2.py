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
from tests.support.paths import FILES
from tests.support.helpers import expensiveTest, generate_random_name
from tests.support.unit import skipIf
from tests.support import win_installer


# Create the cloud instance name to be used throughout the tests
INSTANCE_NAME = generate_random_name('CLOUD-TEST-')
PROVIDER_NAME = 'ec2'
HAS_WINRM = salt.utils.cloud.HAS_WINRM and salt.utils.cloud.HAS_SMB
TIMEOUT = 1200


class EC2Test(ShellCase):
    '''
    Integration tests for the EC2 cloud provider in Salt-Cloud
    '''

    def _installer_name(self):
        '''
        Determine the downloaded installer name by searching the files
        directory for the firt file that loosk like an installer.
        '''
        for path, dirs, files in os.walk(FILES):
            for file in files:
                if file.startswith(win_installer.PREFIX):
                    return file
            break
        return

    def _fetch_latest_installer(self):
        '''
        Download the latest Windows installer executable
        '''
        name = win_installer.latest_installer_name()
        path = os.path.join(FILES, name)
        with salt.utils.files.fopen(path, 'wb') as fp:
            win_installer.download_and_verify(fp, name)
        return name

    def _ensure_installer(self):
        '''
        Make sure the testing environment has a Windows installer executbale.
        '''
        name = self._installer_name()
        if name:
            return name
        return self._fetch_latest_installer()

    @skipIf(True, 'WAR ROOM 8/1/2019, flaky cloud test')
    @expensiveTest
    def setUp(self):
        '''
        Sets up the test requirements
        '''
        super(EC2Test, self).setUp()

        # check if appropriate cloud provider and profile files are present
        profile_str = 'ec2-config'
        providers = self.run_cloud('--list-providers')

        if profile_str + ':' not in providers:
            self.skipTest(
                'Configuration file for {0} was not found. Check {0}.conf files '
                'in tests/integration/files/conf/cloud.*.d/ to run these tests.'
                .format(PROVIDER_NAME)
            )

        # check if id, key, keyname, securitygroup, private_key, location,
        # and provider are present
        config = cloud_providers_config(
            os.path.join(
                FILES,
                'conf',
                'cloud.providers.d',
                PROVIDER_NAME + '.conf'
            )
        )

        id_ = config[profile_str][PROVIDER_NAME]['id']
        key = config[profile_str][PROVIDER_NAME]['key']
        key_name = config[profile_str][PROVIDER_NAME]['keyname']
        private_key = config[profile_str][PROVIDER_NAME]['private_key']
        location = config[profile_str][PROVIDER_NAME]['location']
        group_or_subnet = config[profile_str][PROVIDER_NAME].get('securitygroup', '')
        if not group_or_subnet:
            group_or_subnet = config[profile_str][PROVIDER_NAME].get('subnetid', '')

        conf_items = [id_, key, key_name, private_key, location, group_or_subnet]
        missing_conf_item = []

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
        src = os.path.join(FILES, name)
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

        # check if deletion was performed appropriately
        try:
            self.assertIn(ret_str, delete)
        except AssertionError:
            raise

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

        # delete the instance
        delete = self.run_cloud('-d {0} --assume-yes'.format(rename), timeout=TIMEOUT)
        ret_str = '                    shutting-down'

        # check if deletion was performed appropriately
        self.assertIn(ret_str, delete)

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
                'win_installer': self.copy_file(self.INSTALLER),
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
                'win_installer': self.copy_file(self.INSTALLER),
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
                'win_installer': self.copy_file(self.INSTALLER),
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
                'win_installer': self.copy_file(self.INSTALLER),
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
