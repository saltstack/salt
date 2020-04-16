# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import os
import textwrap

# Import Salt libs
import salt.utils.files
import salt.utils.platform

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import skipIf


@skipIf(not salt.utils.platform.is_windows(), "windows test only")
class WinPKGTest(ModuleCase):
    """
    Tests for salt.modules.win_pkg. There are already
    some pkg execution module tests in the the test
    integration.modules.test_pkg but this will be for
    specific windows software respository tests while
    using the win_pkg module.
    """

    @classmethod
    def setUpClass(cls):
        cls.repo_dir = os.path.join(
            RUNTIME_VARS.FILES, "file", "base", "win", "repo-ng"
        )
        cls.curl_sls_path = os.path.join(cls.repo_dir, "curl.sls")

    def tearDown(self):
        if os.path.isfile(self.curl_sls_path):
            os.remove(self.curl_sls_path)

    @destructiveTest
    def test_adding_removing_pkg_sls(self):
        """
        Test add and removing a new pkg sls
        in the windows software repository
        """

        def _check_pkg(pkgs, check_refresh, exists=True):
            refresh = self.run_function("pkg.refresh_db")
            self.assertEqual(
                check_refresh,
                refresh["total"],
                msg="total returned {0}. Expected return {1}".format(
                    refresh["total"], check_refresh
                ),
            )
            repo_data = self.run_function("pkg.get_repo_data")
            repo_cache = os.path.join(
                RUNTIME_VARS.TMP, "rootdir", "cache", "files", "base", "win", "repo-ng"
            )
            for pkg in pkgs:
                if exists:
                    assert pkg in str(repo_data), str(repo_data)
                else:
                    assert pkg not in str(repo_data), str(repo_data)

                for root, dirs, files in os.walk(repo_cache):
                    if exists:
                        assert pkg + ".sls" in files
                    else:
                        assert pkg + ".sls" not in files

        pkgs = ["putty", "7zip"]
        # check putty and 7zip are in cache and repo query
        _check_pkg(pkgs, 2)

        # now add new sls
        with salt.utils.files.fopen(self.curl_sls_path, "w") as fp_:
            fp_.write(
                textwrap.dedent(
                    """
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
                """
                )
            )
        # now check if curl is also in cache and repo query
        pkgs.append("curl")
        for pkg in pkgs:
            self.assertIn(pkg + ".sls", os.listdir(self.repo_dir))
        _check_pkg(pkgs, 3)

        # remove curl sls and check its not in cache and repo query
        os.remove(self.curl_sls_path)
        _check_pkg(["curl"], 2, exists=False)
