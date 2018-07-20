# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
import os
import textwrap

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf
from tests.support.helpers import destructiveTest
from tests.support.runtests import RUNTIME_VARS

# Import Salt libs
import salt.utils

CURL = os.path.join(RUNTIME_VARS.FILES, 'file', 'base', 'win', 'repo-ng', 'curl.sls')


@skipIf(not salt.utils.is_windows(), 'windows test only')
class WinPKGTest(ModuleCase):
    '''
    Tests for salt.modules.win_pkg. There are already
    some pkg execution module tests in the the test
    integration.modules.test_pkg but this will be for
    specific windows software respository tests while
    using the win_pkg module.
    '''
    @destructiveTest
    def test_adding_removing_pkg_sls(self):
        '''
        Test add and removing a new pkg sls
        in the windows software repository
        '''
        def _check_pkg(pkgs, exists=True):
            self.run_function('pkg.refresh_db')
            repo_data = self.run_function('pkg.get_repo_data')
            repo_cache = os.path.join(RUNTIME_VARS.TMP, 'rootdir', 'cache', 'files', 'base', 'win', 'repo-ng')
            for pkg in pkgs:
                if exists:
                    assert pkg in str(repo_data)
                else:
                    assert pkg not in str(repo_data)

                for root, dirs, files in os.walk(repo_cache):
                    if exists:
                        assert pkg + '.sls' in files
                    else:
                        assert pkg + '.sls' not in files

        pkgs = ['putty', '7zip']
        # check putty and 7zip are in cache and repo query
        _check_pkg(pkgs)

        # now add new sls
        with salt.utils.fopen(CURL, 'w') as fp_:
            fp_.write(textwrap.dedent('''
                curl:
                  '7.46.0':
                    full_name: 'cURL'
                    {% if grains['cpuarch'] == 'AMD64' %}
                    installer: 'salt://win/repo-ng/curl/curl-7.46.0-win64.msi'
                    uninstaller: 'salt://win/repo-ng/curl/curl-7.46.0-win64.msi'
                    {% else %}
                    installer: 'salt://win/repo-ng/curl/curl-7.46.0-win32.msi'
                    uninstaller: 'salt://win/repo-ng/curl/curl-7.46.0-win32.msi'
                    {% endif %}
                    install_flags: '/qn /norestart'
                    uninstall_flags: '/qn /norestart'
                    msiexec: True
                    locale: en_US
                    reboot: False
                '''))
        # now check if curl is also in cache and repo query
        pkgs.append('curl')
        _check_pkg(pkgs)

        # remove curl sls and check its not in cache and repo query
        os.remove(CURL)
        _check_pkg(['curl'], exists=False)

    def tearDown(self):
        if os.path.isfile(CURL):
            os.remove(CURL)
