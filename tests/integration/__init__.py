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

# Import salt cloud libs
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

    def run_cloud(self, arg_str):
        '''
        Execute salt-cloud
        '''
        cloud_conf = os.path.join(
            INTEGRATION_TEST_DIR, 'files', 'conf', 'cloud'
        )
        arg_str = '-C {0} {1}'.format(cloud_conf, arg_str)
        return self.run_script('salt-cloud', arg_str)
