# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Daniel Mizyrycki (mzdaniel@glidelink.net)`


    tests.integration.cli.test_custom_module
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test salt-ssh sls with a custom module work.

    $ cat srv/custom_module.sls
    custom-module:
      module.run:
        - name: test.recho
        - text: hello


    $ cat srv/_modules/override_test.py
    __virtualname__ = 'test'

    def __virtual__():
        return __virtualname__

    def recho(text):
        return text[::-1]


    $ salt-ssh localhost state.sls custom_module
    localhost:
        olleh


    This test can be run in a small test suite with:

    $ python tests/runtests.py -C --ssh
'''
# Import Python libs
from __future__ import absolute_import

# Import 3rd-party libs
import pytest


class TestSSHCustomModule(object):
    '''
    Test sls with custom module functionality using ssh
    '''

    def test_ssh_regular_module(self, session_salt_ssh):
        '''
        Test regular module work using SSHCase environment
        '''
        expected = 'hello'
        cmd = session_salt_ssh.run_sync('test.echo', 'hello')
        assert expected == cmd

    def test_ssh_custom_module(self, session_salt_ssh):
        '''
        Test custom module work using SSHCase environment
        '''
        expected = 'hello'[::-1]
        cmd = session_salt_ssh.run_sync('test.recho', 'hello')
        assert expected == cmd

    def test_ssh_sls_with_custom_module(self, session_salt_ssh):
        '''
        Test sls with custom module work using SSHCase environment
        '''
        expected = {
            "module_|-regular-module_|-test.echo_|-run": 'hello',
            "module_|-custom-module_|-test.recho_|-run": 'olleh'}
        cmd = session_salt_ssh.run_sync('state.sls', 'custom_module')
        assert cmd.json is not None, '{0} is not a proper state return'.format(cmd.stdout)
        for key in cmd.json:
            if not isinstance(cmd.json[key], dict):
                pytest.fail('{0} is not a proper state return'.format(cmd))
            elif not cmd.json[key]['result']:
                pytest.fail(cmd[key]['comment'])
            cmd_ret = cmd.json[key]['changes'].get('ret', None)
            assert cmd_ret == expected[key]
