# -*- coding: utf-8 -*-
"""
Test the hosts module
"""
# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os
import shutil

# Import Salt libs
import salt.utils.files
import salt.utils.stringutils
from tests.support.case import ModuleCase

# Import Salt Testing libs
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)


class HostsModuleTest(ModuleCase):
    """
    Test the hosts module
    """

    maxDiff = None

    @classmethod
    def setUpClass(cls):
        cls.hosts_file = os.path.join(RUNTIME_VARS.TMP, "hosts")

    def __clear_hosts(self):
        """
        Delete the tmp hosts file
        """
        if os.path.isfile(self.hosts_file):
            os.remove(self.hosts_file)

    def setUp(self):
        shutil.copyfile(os.path.join(RUNTIME_VARS.FILES, "hosts"), self.hosts_file)
        self.addCleanup(self.__clear_hosts)

    def test_list_hosts(self):
        """
        hosts.list_hosts
        """
        hosts = self.run_function("hosts.list_hosts")
        self.assertEqual(len(hosts), 10)
        self.assertEqual(hosts["::1"], ["ip6-localhost", "ip6-loopback"])
        self.assertEqual(hosts["127.0.0.1"], ["localhost", "myname"])

    def test_list_hosts_nofile(self):
        """
        hosts.list_hosts
        without a hosts file
        """
        if os.path.isfile(self.hosts_file):
            os.remove(self.hosts_file)
        hosts = self.run_function("hosts.list_hosts")
        self.assertEqual(hosts, {})

    def test_get_ip(self):
        """
        hosts.get_ip
        """
        self.assertEqual(self.run_function("hosts.get_ip", ["myname"]), "127.0.0.1")
        self.assertEqual(self.run_function("hosts.get_ip", ["othername"]), "")
        self.__clear_hosts()
        self.assertEqual(self.run_function("hosts.get_ip", ["othername"]), "")

    def test_get_alias(self):
        """
        hosts.get_alias
        """
        self.assertEqual(
            self.run_function("hosts.get_alias", ["127.0.0.1"]), ["localhost", "myname"]
        )
        self.assertEqual(self.run_function("hosts.get_alias", ["127.0.0.2"]), [])
        self.__clear_hosts()
        self.assertEqual(self.run_function("hosts.get_alias", ["127.0.0.1"]), [])

    def test_has_pair(self):
        """
        hosts.has_pair
        """
        self.assertTrue(self.run_function("hosts.has_pair", ["127.0.0.1", "myname"]))
        self.assertFalse(
            self.run_function("hosts.has_pair", ["127.0.0.1", "othername"])
        )

    def test_set_host(self):
        """
        hosts.set_hosts
        """
        self.assertTrue(self.run_function("hosts.set_host", ["192.168.1.123", "newip"]))
        self.assertTrue(self.run_function("hosts.has_pair", ["192.168.1.123", "newip"]))
        self.assertTrue(self.run_function("hosts.set_host", ["127.0.0.1", "localhost"]))
        self.assertEqual(len(self.run_function("hosts.list_hosts")), 11)
        self.assertFalse(
            self.run_function("hosts.has_pair", ["127.0.0.1", "myname"]),
            "should remove second entry",
        )

    def test_add_host(self):
        """
        hosts.add_host
        """
        self.assertTrue(self.run_function("hosts.add_host", ["192.168.1.123", "newip"]))
        self.assertTrue(self.run_function("hosts.has_pair", ["192.168.1.123", "newip"]))
        self.assertEqual(len(self.run_function("hosts.list_hosts")), 11)
        self.assertTrue(
            self.run_function("hosts.add_host", ["127.0.0.1", "othernameip"])
        )
        self.assertEqual(len(self.run_function("hosts.list_hosts")), 11)

    def test_rm_host(self):
        self.assertTrue(self.run_function("hosts.has_pair", ["127.0.0.1", "myname"]))
        self.assertTrue(self.run_function("hosts.rm_host", ["127.0.0.1", "myname"]))
        self.assertFalse(self.run_function("hosts.has_pair", ["127.0.0.1", "myname"]))
        self.assertTrue(self.run_function("hosts.rm_host", ["127.0.0.1", "unknown"]))

    def test_add_host_formatting(self):
        """
        Ensure that hosts.add_host isn't adding duplicates and that
        it's formatting the output correctly
        """
        # instead of using the 'clean' hosts file we're going to
        # use an empty one so we can prove the syntax of the entries
        # being added by the hosts module
        self.__clear_hosts()
        with salt.utils.files.fopen(self.hosts_file, "w"):
            pass

        self.assertTrue(
            self.run_function("hosts.add_host", ["192.168.1.3", "host3.fqdn.com"])
        )
        self.assertTrue(
            self.run_function("hosts.add_host", ["192.168.1.1", "host1.fqdn.com"])
        )
        self.assertTrue(self.run_function("hosts.add_host", ["192.168.1.1", "host1"]))
        self.assertTrue(
            self.run_function("hosts.add_host", ["192.168.1.2", "host2.fqdn.com"])
        )
        self.assertTrue(self.run_function("hosts.add_host", ["192.168.1.2", "host2"]))
        self.assertTrue(
            self.run_function("hosts.add_host", ["192.168.1.2", "oldhost2"])
        )
        self.assertTrue(
            self.run_function("hosts.add_host", ["192.168.1.2", "host2-reorder"])
        )
        self.assertTrue(
            self.run_function("hosts.add_host", ["192.168.1.1", "host1-reorder"])
        )

        # now read the lines and ensure they're formatted correctly
        with salt.utils.files.fopen(self.hosts_file, "r") as fp_:
            lines = salt.utils.stringutils.to_unicode(fp_.read()).splitlines()
        self.assertEqual(
            lines,
            [
                "192.168.1.3\t\thost3.fqdn.com",
                "192.168.1.1\t\thost1.fqdn.com host1 host1-reorder",
                "192.168.1.2\t\thost2.fqdn.com host2 oldhost2 host2-reorder",
            ],
        )
