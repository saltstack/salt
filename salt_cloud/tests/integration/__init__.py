# -*- coding: utf-8 -*-
'''
    integration
    ~~~~~~~~~~~

    Integration testing

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import python libs
import os
import sys
import shutil
import tempfile

# Import external libs
import yaml

INTEGRATION_TEST_DIR = os.path.dirname(
    os.path.normpath(os.path.abspath(__file__))
)
CODE_DIR = os.path.dirname(os.path.dirname(INTEGRATION_TEST_DIR))
SALTCLOUD_LIBS = os.path.dirname(CODE_DIR)
SCRIPT_DIR = os.path.join(CODE_DIR, 'scripts')
PYEXEC = 'python{0}.{1}'.format(sys.version_info[0], sys.version_info[1])

# Update sys.path
for dir_ in [CODE_DIR, SALTCLOUD_LIBS]:
    if not dir_ in sys.path:
        sys.path.insert(0, dir_)

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.case import ShellTestCase
from salttesting.mixins import CheckShellBinaryNameAndVersionMixIn
from salttesting.parser import run_testcase

# Import salt libs
import salt.config

# Import salt cloud libs
import saltcloud.config
import saltcloud.version


class ShellCaseCommonTestsMixIn(CheckShellBinaryNameAndVersionMixIn):

    _call_binary_expected_version_ = saltcloud.version.__version__


class ShellCase(ShellTestCase, CheckShellBinaryNameAndVersionMixIn):
    '''
    Execute a test for a shell command
    '''

    _code_dir_ = CODE_DIR
    _script_dir_ = SCRIPT_DIR
    _python_executable_ = PYEXEC
    _temp_cloud_config_dir_ = None
    _temp_cloud_config_file_ = None

    @classmethod
    def setUpClass(cls):
        '''
        Setup temporary configuration
        '''
        cls._temp_cloud_config_dir_ = tempfile.mkdtemp()
        root_dir = os.path.join(cls._temp_cloud_config_dir_, 'root-dir')
        os.makedirs(root_dir)

        # Let's create a temporary master configuration
        master_config_file = os.path.join(
            cls._temp_cloud_config_dir_, 'master'
        )
        master_config = salt.config.DEFAULT_MASTER_OPTS.copy()
        # Let's update it with some working settings
        master_config['root_dir'] = root_dir
        master_config['sock_dir'] = 'socks'
        master_config['pki_dir'] = 'pki/master'
        master_config['cache_dir'] = 'cache'
        master_config['conf_file'] = master_config_file
        master_config['log_file'] = 'logs/master'
        master_config['pidfile'] = 'run/salt-master.pid'
        master_config['key_logfile'] = 'logs/key'
        open(master_config_file, 'w').write(yaml.dump(master_config))

        # Let's create a temporary cloud configuration
        cls._temp_cloud_config_file_ = cloud_config_file = os.path.join(
            cls._temp_cloud_config_dir_, 'cloud'
        )
        cloud_config = saltcloud.config.CLOUD_CONFIG_DEFAULTS.copy()
        # Let's update it with some working settings
        cloud_config['log_file'] = 'logs/cloud'
        cloud_config['conf_file'] = cloud_config
        cloud_config['master_config'] = master_config_file
        open(cloud_config_file, 'w').write(yaml.dump(cloud_config))

    @classmethod
    def tearDownClass(cls):
        if os.path.isdir(cls._temp_cloud_config_dir_):
            shutil.rmtree(cls._temp_cloud_config_dir_)

    def run_cloud(self, arg_str, catch_stderr=False, timeout=None):
        '''
        Execute salt-cloud
        '''
        arg_str = '-C {0} {1}'.format(self._temp_cloud_config_file_, arg_str)
        return self.run_script('salt-cloud', arg_str, catch_stderr, timeout)
