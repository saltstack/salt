# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.hosts as hosts
import salt.utils.data
import salt.utils.platform
import salt.utils.stringutils
from salt.ext import six
from salt.ext.six.moves import StringIO

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, mock_open, patch
from tests.support.unit import TestCase


class HostsTestCase(TestCase, LoaderModuleMockMixin):
    """
    TestCase for salt.modules.hosts
    """

    def setup_loader_modules(self):
        return {hosts: {}}

    # 'list_hosts' function tests: 1

    def test_list_hosts(self):
        """
        Tests return the hosts found in the hosts file
        """
        with patch(
            "salt.modules.hosts._list_hosts",
            MagicMock(return_value={"10.10.10.10": ["Salt1", "Salt2"]}),
        ):
            self.assertDictEqual(
                {"10.10.10.10": ["Salt1", "Salt2"]}, hosts.list_hosts()
            )

    # 'get_ip' function tests: 3

    def test_get_ip(self):
        """
        Tests return ip associated with the named host
        """
        with patch(
            "salt.modules.hosts._list_hosts",
            MagicMock(return_value={"10.10.10.10": ["Salt1", "Salt2"]}),
        ):
            self.assertEqual("10.10.10.10", hosts.get_ip("Salt1"))

            self.assertEqual("", hosts.get_ip("Salt3"))

    def test_get_ip_none(self):
        """
        Tests return ip associated with the named host
        """
        with patch("salt.modules.hosts._list_hosts", MagicMock(return_value="")):
            self.assertEqual("", hosts.get_ip("Salt1"))

    # 'get_alias' function tests: 2

    def test_get_alias(self):
        """
        Tests return the list of aliases associated with an ip
        """
        with patch(
            "salt.modules.hosts._list_hosts",
            MagicMock(return_value={"10.10.10.10": ["Salt1", "Salt2"]}),
        ):
            self.assertListEqual(["Salt1", "Salt2"], hosts.get_alias("10.10.10.10"))

    def test_get_alias_none(self):
        """
        Tests return the list of aliases associated with an ip
        """
        with patch(
            "salt.modules.hosts._list_hosts",
            MagicMock(return_value={"10.10.10.10": ["Salt1", "Salt2"]}),
        ):
            self.assertListEqual([], hosts.get_alias("10.10.10.11"))

    # 'has_pair' function tests: 1

    def test_has_pair(self):
        """
        Tests return True / False if the alias is set
        """
        with patch(
            "salt.modules.hosts._list_hosts",
            MagicMock(return_value={"10.10.10.10": ["Salt1", "Salt2"]}),
        ):
            self.assertTrue(hosts.has_pair("10.10.10.10", "Salt1"))

            self.assertFalse(hosts.has_pair("10.10.10.10", "Salt3"))

    # 'set_host' function tests: 3

    def test_set_host(self):
        """
        Tests true if the alias is set
        """
        hosts_file = "/etc/hosts"
        if salt.utils.platform.is_windows():
            hosts_file = r"C:\Windows\System32\Drivers\etc\hosts"

        with patch(
            "salt.modules.hosts.__get_hosts_filename",
            MagicMock(return_value=hosts_file),
        ), patch("os.path.isfile", MagicMock(return_value=False)), patch.dict(
            hosts.__salt__, {"config.option": MagicMock(return_value=None)}
        ):
            self.assertFalse(hosts.set_host("10.10.10.10", "Salt1"))

    def test_set_host_true(self):
        """
        Tests true if the alias is set
        """
        with patch(
            "salt.modules.hosts.__get_hosts_filename",
            MagicMock(return_value="/etc/hosts"),
        ), patch("os.path.isfile", MagicMock(return_value=True)), patch(
            "salt.utils.files.fopen", mock_open(b"")
        ):
            mock_opt = MagicMock(return_value=None)
            with patch.dict(hosts.__salt__, {"config.option": mock_opt}):
                self.assertTrue(hosts.set_host("10.10.10.10", "Salt1"))

    def test_set_host_true_remove(self):
        """
        Test if an empty hosts value removes existing entries
        """
        with patch(
            "salt.modules.hosts.__get_hosts_filename",
            MagicMock(return_value="/etc/hosts"),
        ), patch("os.path.isfile", MagicMock(return_value=True)):
            data = [
                "\n".join(
                    (
                        "1.1.1.1 foo.foofoo foo",
                        "2.2.2.2 bar.barbar bar",
                        "3.3.3.3 asdf.asdfadsf asdf",
                        "1.1.1.1 foofoo.foofoo foofoo",
                    )
                )
            ]

            class TmpStringIO(StringIO, object):
                def __init__(self, fn, mode="r"):
                    self.mode = mode
                    initial_value = data[0]
                    if "w" in self.mode:
                        initial_value = ""
                    super(TmpStringIO, self).__init__(initial_value)

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc_value, traceback):
                    self.close()

                def close(self):
                    # Don't save unless there's something there. In Windows
                    # the class gets initialized the first time with mode = w
                    # which sets the initial value to ''. When the class closes
                    # it clears out data and causes the test to fail.
                    # I don't know why it get's initialized with a mode of 'w'
                    # For the purposes of this test data shouldn't be empty
                    # This is a problem with this class and not with the hosts
                    # module
                    if self.getvalue():
                        data[0] = self.getvalue()
                    StringIO.close(self)

                def read(self, *args):
                    ret = super(TmpStringIO, self).read(*args)
                    if six.PY3 and "b" in self.mode:
                        return salt.utils.stringutils.to_bytes(ret)
                    else:
                        return ret

                def write(self, s, *args):
                    if six.PY3:
                        if "b" in self.mode:
                            if not isinstance(s, bytes):
                                # Make this act like a binary filehandle
                                raise TypeError(
                                    "a bytes-like object is required, not 'str'"
                                )
                            # The StringIO wants a str type, it won't take
                            # bytes. Convert before writing to it.
                            return super(TmpStringIO, self).write(
                                salt.utils.stringutils.to_str(s), *args
                            )
                        else:
                            if not isinstance(s, str):
                                # Make this act like a non-binary filehandle
                                raise TypeError(
                                    "write() argument must be str, not bytes"
                                )
                    return super(TmpStringIO, self).write(s, *args)

                def readlines(self):
                    ret = super(TmpStringIO, self).readlines()
                    if six.PY3 and "b" in self.mode:
                        return salt.utils.data.encode(ret)
                    else:
                        return ret

                def writelines(self, lines):
                    for line in lines:
                        self.write(line)

            expected = (
                "\n".join(("2.2.2.2 bar.barbar bar", "3.3.3.3 asdf.asdfadsf asdf",))
                + "\n"
            )

            with patch("salt.utils.files.fopen", TmpStringIO):
                mock_opt = MagicMock(return_value=None)
                with patch.dict(hosts.__salt__, {"config.option": mock_opt}):
                    self.assertTrue(hosts.set_host("1.1.1.1", " "))

            self.assertEqual(data[0], expected)

    # 'rm_host' function tests: 2

    def test_rm_host(self):
        """
        Tests if specified host entry gets removed from the hosts file
        """
        with patch("salt.utils.files.fopen", mock_open(b"")), patch(
            "salt.modules.hosts.__get_hosts_filename",
            MagicMock(return_value="/etc/hosts"),
        ), patch("salt.modules.hosts.has_pair", MagicMock(return_value=True)), patch(
            "os.path.isfile", MagicMock(return_value=True)
        ):
            mock_opt = MagicMock(return_value=None)
            with patch.dict(hosts.__salt__, {"config.option": mock_opt}):
                self.assertTrue(hosts.rm_host("10.10.10.10", "Salt1"))

    def test_rm_host_false(self):
        """
        Tests if specified host entry gets removed from the hosts file
        """
        with patch("salt.modules.hosts.has_pair", MagicMock(return_value=False)):
            self.assertTrue(hosts.rm_host("10.10.10.10", "Salt1"))

    # 'add_host' function tests: 3

    def test_add_host(self):
        """
        Tests if specified host entry gets added from the hosts file
        """
        hosts_file = "/etc/hosts"
        if salt.utils.platform.is_windows():
            hosts_file = r"C:\Windows\System32\Drivers\etc\hosts"

        with patch("salt.utils.files.fopen", mock_open()), patch(
            "salt.modules.hosts.__get_hosts_filename",
            MagicMock(return_value=hosts_file),
        ):
            mock_opt = MagicMock(return_value=None)
            with patch.dict(hosts.__salt__, {"config.option": mock_opt}):
                self.assertTrue(hosts.add_host("10.10.10.10", "Salt1"))

    def test_add_host_no_file(self):
        """
        Tests if specified host entry gets added from the hosts file
        """
        with patch("salt.utils.files.fopen", mock_open()), patch(
            "os.path.isfile", MagicMock(return_value=False)
        ):
            mock_opt = MagicMock(return_value=None)
            with patch.dict(hosts.__salt__, {"config.option": mock_opt}):
                self.assertFalse(hosts.add_host("10.10.10.10", "Salt1"))

    def test_add_host_create_entry(self):
        """
        Tests if specified host entry gets added from the hosts file
        """
        with patch("salt.utils.files.fopen", mock_open()), patch(
            "os.path.isfile", MagicMock(return_value=True)
        ):
            mock_opt = MagicMock(return_value=None)
            with patch.dict(hosts.__salt__, {"config.option": mock_opt}):
                self.assertTrue(hosts.add_host("10.10.10.10", "Salt1"))
