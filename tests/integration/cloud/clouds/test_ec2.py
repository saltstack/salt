# -*- coding: utf-8 -*-
'''
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import yaml

# Import Salt Libs
import salt.utils.cloud
import salt.utils.files
import salt.utils.yaml

# Import Salt Testing Libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.helpers import expensiveTest
from tests.support.unit import skipIf
from tests.support import win_installer

# Create the cloud instance name to be used throughout the tests
from tests.integration.cloud.helpers.cloud_test_base import CloudTest

HAS_WINRM = salt.utils.cloud.HAS_WINRM and salt.utils.cloud.HAS_SMB
# THis test needs a longer timeout than other cloud tests
TIMEOUT = 1200


class EC2Test(CloudTest):
    '''
    Integration tests for the EC2 cloud provider in Salt-Cloud
    '''
    PROVIDER = 'ec2'
    REQUIRED_PROVIDER_CONFIG_ITEMS = ('id', 'key', 'keyname', 'private_key', 'location')

    @staticmethod
    def __fetch_installer():
        # Determine the downloaded installer name by searching the files
        # directory for the first file that looks like an installer.
        for path, dirs, files in os.walk(RUNTIME_VARS.FILES):
            for file in files:
                if file.startswith(win_installer.PREFIX):
                    return file

        # If the installer wasn't found in the previous steps, download the latest Windows installer executable
        name = win_installer.latest_installer_name()
        path = os.path.join(RUNTIME_VARS.FILES, name)
        with salt.utils.files.fopen(path, 'wb') as fp:
            win_installer.download_and_verify(fp, name)
        return name

    @property
    def installer(self):
        '''
        Make sure the testing environment has a Windows installer executable.
        '''
        if not hasattr(self, '_installer'):
            self._installer = self.__fetch_installer()
        return self._installer

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

        super(EC2Test, self).setUp()

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

    def _test_instance(self, profile, debug):
        '''
        Tests creating and deleting an instance on EC2 (classic)
        '''

        # create the instance
        cmd = ['-p', profile]
        if debug:
            cmd.extend(['-l', 'debug'])
        cmd.append(self.instance_name)
        ret_val = self.run_cloud(' '.join(cmd), timeout=TIMEOUT)

        # check if instance returned with salt installed
        self.assertInstanceExists(ret_val)

        self.assertDestroyInstance()

    def test_instance_rename(self):
        '''
        Tests creating and renaming an instance on EC2 (classic)
        '''
        # create the instance
        ret_val = self.run_cloud('-p ec2-test {0} --no-deploy'.format(self.instance_name), timeout=TIMEOUT)
        # check if instance returned
        self.assertInstanceExists(ret_val)

        changed_name = self.instance_name + '-changed'

        rename_result = self.run_cloud(
            '-a rename {0} newname={1} --assume-yes'.format(self.instance_name, changed_name), timeout=TIMEOUT)
        self.assertFalse(self._instance_exists(), 'Instance wasn\'t renamed: |\n{}'.format(rename_result))
        self.assertInstanceExists(instance_name=changed_name)

        self.assertDestroyInstance(changed_name)

    def test_instance(self):
        '''
        Tests creating and deleting an instance on EC2 (classic)
        '''
        self._test_instance('ec2-test', debug=False)

    def test_win2012r2_psexec(self):
        '''
        Tests creating and deleting a Windows 2012r2instance on EC2 using
        psexec (classic)
        '''
        # TODO: psexec calls hang and the test fails by timing out. The same
        # same calls succeed when run outside of the test environment.
        # FIXME? Does this override need to be undone at the end of the test?
        self.override_profile_config(
            'ec2-win2012r2-test',
            {
                'use_winrm': False,
                'userdata_file': self.copy_file('windows-firewall-winexe.ps1'),
                'win_installer': self.copy_file(self.installer),
            },
        )
        self._test_instance('ec2-win2012r2-test', debug=True)

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
        self._test_instance('ec2-win2012r2-test', debug=True)

    def test_win2016_psexec(self):
        '''
        Tests creating and deleting a Windows 2016 instance on EC2 using winrm
        (classic)
        '''
        # TODO: winexe calls hang and the test fails by timing out. The
        # same calls succeed when run outside of the test environment.
        self.override_profile_config(
            'ec2-win2016-test',
            {
                'use_winrm': False,
                'userdata_file': self.copy_file('windows-firewall-winexe.ps1'),
                'win_installer': self.copy_file(self.installer),
            },
        )
        self._test_instance('ec2-win2016-test', debug=True)

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
        self._test_instance('ec2-win2016-test', debug=True)
