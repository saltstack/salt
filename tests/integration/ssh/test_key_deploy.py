# -*- coding: utf-8 -*-
'''
:codeauthor: :email:`Daniel Wallace (daniel@saltstack.com)`


====================================
Test Case for --no-key-deploy
====================================
'''
from __future__ import unicode_literals, absolute_import

# Import Python Libs
import os
import json

# Import Tests Libs
from tests.support.case import SSHCase
from tests.support.runtests import RUNTIME_VARS


class SSHKeyDeployQuestionCase(SSHCase):

    def _run_ssh(self, arg_str, with_retcode=False, timeout=25, catch_stderr=False):

        arg_str = '-ldebug -c {0} -i --roster-file {1} --out=json localhost {2}'.format(
            self.get_config_dir(),
            os.path.join(RUNTIME_VARS.TMP_CONF_DIR, '_ssh', 'roster'),
            arg_str,
        )
        return self.run_script('salt-ssh',
                               arg_str,
                               with_retcode=with_retcode,
                               catch_stderr=catch_stderr,
                               timeout=timeout,
                               raw=True)

    def test_no_key_deploy(self):
        exp = {
            'localhost': {
                'stdout': '',
                'stderr': "Permission denied (publickey).\r\n",
                'retcode': 255,
            },
        }
        assert json.loads(self._run_ssh('--no-key-deploy localhost test.ping')) == exp

    def test_key_deploy(self):
        exp = ['Process took more than 5 seconds to complete. Process Killed!']
        assert self._run_ssh('localhost test.ping', timeout=5) == exp
