# -*- coding: utf-8 -*-
"""
    :codeauthor: Daniel Mizyrycki (mzdaniel@glidelink.net)


    tests.integration.cli.grains
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test salt-ssh grains id work for localhost. (gh #16129)

    $ salt-ssh localhost grains.get id
    localhost:
        localhost
"""
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os

import pytest
import salt.utils.files
from tests.support.case import ShellCase, SSHCase
from tests.support.helpers import flaky, requires_system_grains, slowTest

log = logging.getLogger(__name__)


@pytest.mark.windows_whitelisted
@pytest.mark.usefixtures("salt_sub_minion")
class GrainsTargetingTest(ShellCase):
    """
    Integration tests for targeting with grains.
    """

    @slowTest
    @requires_system_grains
    def test_grains_targeting_os_running(self, grains):
        """
        Tests running "salt -G 'os:<system-os>' test.ping and minions both return True
        """
        test_ret = ["sub_minion:", "    True", "minion:", "    True"]
        ret = self.run_salt('-G "os:{0}" test.ping'.format(grains["os"]))
        self.assertEqual(sorted(ret), sorted(test_ret))

    @slowTest
    def test_grains_targeting_minion_id_running(self):
        """
        Tests return of each running test minion targeting with minion id grain
        """
        minion = self.run_salt('-G "id:minion" test.ping')
        self.assertEqual(sorted(minion), sorted(["minion:", "    True"]))

        sub_minion = self.run_salt('-G "id:sub_minion" test.ping')
        self.assertEqual(sorted(sub_minion), sorted(["sub_minion:", "    True"]))

    @flaky
    @slowTest
    def test_grains_targeting_disconnected(self):
        """
        Tests return of minion using grains targeting on a disconnected minion.
        """
        test_ret = "Minion did not return. [No response]"

        # Create a minion key, but do not start the "fake" minion. This mimics a
        # disconnected minion.
        key_file = os.path.join(self.master_opts["pki_dir"], "minions", "disconnected")
        with salt.utils.files.fopen(key_file, "a"):
            pass

        # ping disconnected minion and ensure it times out and returns with correct message
        try:
            ret = ""
            for item in self.run_salt(
                '-t 1 -G "id:disconnected" test.ping', timeout=40
            ):
                if item != "disconnected:":
                    ret = item.strip()
                    break
            assert ret == test_ret
        finally:
            os.unlink(key_file)


@pytest.mark.windows_whitelisted
class SSHGrainsTest(SSHCase):
    """
    Test salt-ssh grains functionality
    Depend on proper environment set by SSHCase class
    """

    @slowTest
    def test_grains_id(self):
        """
        Test salt-ssh grains id work for localhost.
        """
        cmd = self.run_function("grains.get", ["id"])
        self.assertEqual(cmd, "localhost")
