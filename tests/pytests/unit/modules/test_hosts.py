"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    TestCase for salt.modules.hosts
"""

import pytest

import salt.modules.hosts as hosts
import salt.utils.data
import salt.utils.platform
from tests.support.mock import MagicMock, mock_open, patch


@pytest.fixture
def configure_loader_modules():
    return {hosts: {}}


# 'list_hosts' function tests: 1


def test_list_hosts():
    """
    Tests return the hosts found in the hosts file
    """
    with patch(
        "salt.modules.hosts._list_hosts",
        MagicMock(return_value={"10.10.10.10": {"aliases": ["Salt1", "Salt2"]}}),
    ):
        assert {"10.10.10.10": {"aliases": ["Salt1", "Salt2"]}} == hosts.list_hosts()


# 'get_ip' function tests: 3


def test_get_ip():
    """
    Tests return ip associated with the named host
    """
    with patch(
        "salt.modules.hosts._list_hosts",
        MagicMock(return_value={"10.10.10.10": {"aliases": ["Salt1", "Salt2"]}}),
    ):
        assert "10.10.10.10" == hosts.get_ip("Salt1")

        assert "" == hosts.get_ip("Salt3")


def test_get_ip_none():
    """
    Tests return ip associated with the named host
    """
    with patch("salt.modules.hosts._list_hosts", MagicMock(return_value="")):
        assert "" == hosts.get_ip("Salt1")


# 'get_alias' function tests: 2


def test_get_alias():
    """
    Tests return the list of aliases associated with an ip
    """
    with patch(
        "salt.modules.hosts._list_hosts",
        MagicMock(return_value={"10.10.10.10": {"aliases": ["Salt1", "Salt2"]}}),
    ):
        assert ["Salt1", "Salt2"] == hosts.get_alias("10.10.10.10")


def test_get_alias_none():
    """
    Tests return the list of aliases associated with an ip
    """
    with patch(
        "salt.modules.hosts._list_hosts",
        MagicMock(return_value={"10.10.10.10": {"aliases": ["Salt1", "Salt2"]}}),
    ):
        assert [] == hosts.get_alias("10.10.10.11")


# 'has_pair' function tests: 1


def test_has_pair():
    """
    Tests return True / False if the alias is set
    """
    with patch(
        "salt.modules.hosts._list_hosts",
        MagicMock(return_value={"10.10.10.10": {"aliases": ["Salt1", "Salt2"]}}),
    ):
        assert hosts.has_pair("10.10.10.10", "Salt1")

        assert not hosts.has_pair("10.10.10.10", "Salt3")


# 'set_host' function tests: 3


def test_set_host():
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
        assert not hosts.set_host("10.10.10.10", "Salt1")


def test_set_host_true():
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
            assert hosts.set_host("10.10.10.10", "Salt1")


def test_set_host_true_remove():
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

        mock_opt = MagicMock(return_value=None)
        with patch.dict(hosts.__salt__, {"config.option": mock_opt}):
            assert hosts.set_host("1.1.1.1", " ")


# 'rm_host' function tests: 2


def test_rm_host():
    """
    Tests if specified host entry gets removed from the hosts file
    """
    hosts_content = (
        b"# one line comment\n10.10.10.10    Salt1\n9.9.9.9    Salt2   # comment\n"
    )
    with patch("salt.utils.files.fopen", mock_open(hosts_content)), patch(
        "salt.modules.hosts.__get_hosts_filename",
        MagicMock(return_value="/etc/hosts"),
    ), patch("salt.modules.hosts.has_pair", MagicMock(return_value=True)), patch(
        "os.path.isfile", MagicMock(return_value=True)
    ):
        mock_opt = MagicMock(return_value=None)
        with patch.dict(hosts.__salt__, {"config.option": mock_opt}):
            assert hosts.rm_host("10.10.10.10", "Salt1")


def test_rm_host_false():
    """
    Tests if specified host entry gets removed from the hosts file
    """
    with patch("salt.modules.hosts.has_pair", MagicMock(return_value=False)):
        assert hosts.rm_host("10.10.10.10", "Salt1")


# 'add_host' function tests: 3


def test_add_host():
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
            assert hosts.add_host("10.10.10.10", "Salt1")


def test_add_host_no_file():
    """
    Tests if specified host entry gets added from the hosts file
    """
    with patch("salt.utils.files.fopen", mock_open()), patch(
        "os.path.isfile", MagicMock(return_value=False)
    ):
        mock_opt = MagicMock(return_value=None)
        with patch.dict(hosts.__salt__, {"config.option": mock_opt}):
            assert not hosts.add_host("10.10.10.10", "Salt1")


def test_add_host_create_entry():
    """
    Tests if specified host entry gets added from the hosts file
    """
    with patch("salt.utils.files.fopen", mock_open()), patch(
        "os.path.isfile", MagicMock(return_value=True)
    ):
        mock_opt = MagicMock(return_value=None)
        with patch.dict(hosts.__salt__, {"config.option": mock_opt}):
            assert hosts.add_host("10.10.10.10", "Salt1")


def test_set_comment():
    """
    Tests return True / False when setting a comment
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
            with patch(
                "salt.modules.hosts._list_hosts",
                MagicMock(
                    return_value={"10.10.10.10": {"aliases": ["Salt1", "Salt2"]}}
                ),
            ):
                assert hosts.set_comment("10.10.10.10", "A comment")

                assert not hosts.set_comment("10.10.10.11", "A comment")
