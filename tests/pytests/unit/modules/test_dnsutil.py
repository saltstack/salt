"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>

     TestCase for salt.modules.dnsutil
"""

import pytest

import salt.modules.dnsutil as dnsutil
import salt.utils.stringutils
from tests.support.mock import MagicMock, mock_open, patch


@pytest.fixture
def mock_hosts_file():
    return (
        "##\n"
        "# Host Database\n"
        "#\n"
        "# localhost is used to configure the loopback interface\n"
        "# when the system is booting.  Do not change this entry.\n"
        "##\n"
        "127.0.0.1	localhost\n"
        "255.255.255.255	broadcasthost\n"
        "::1             localhost\n"
        "fe80::1%lo0	localhost"
    )


@pytest.fixture
def mock_hosts_file_rtn():
    return {
        "::1": ["localhost"],
        "255.255.255.255": ["broadcasthost"],
        "127.0.0.1": ["localhost"],
        "fe80::1%lo0": ["localhost"],
    }


@pytest.fixture
def mock_soa_zone():
    return (
        "$TTL 3D\n"
        "@               IN      SOA     land-5.com. root.land-5.com. (\n"
        "199609203       ; Serial\n"
        "28800   ; Refresh\n"
        "7200    ; Retry\n"
        "604800  ; Expire\n"
        "86400)  ; Minimum TTL\n"
        "NS      land-5.com.\n\n"
        "1                       PTR     localhost."
    )


@pytest.fixture
def mock_writes_list():
    return [
        "##\n",
        "# Host Database\n",
        "#\n",
        "# localhost is used to configure the loopback interface\n",
        "# when the system is booting.  Do not change this entry.\n",
        "##\n",
        "127.0.0.1 localhost",
        "\n",
        "255.255.255.255 broadcasthost",
        "\n",
        "::1 localhost",
        "\n",
        "fe80::1%lo0 localhost",
        "\n",
    ]


@pytest.fixture
def configure_loader_modules():
    return {dnsutil: {}}


def test_parse_hosts(mock_hosts_file):
    with patch("salt.utils.files.fopen", mock_open(read_data=mock_hosts_file)):
        assert dnsutil.parse_hosts() == {
            "::1": ["localhost"],
            "255.255.255.255": ["broadcasthost"],
            "127.0.0.1": ["localhost"],
            "fe80::1%lo0": ["localhost"],
        }


def test_hosts_append(mock_hosts_file, mock_hosts_file_rtn):
    with patch(
        "salt.utils.files.fopen", mock_open(read_data=mock_hosts_file)
    ) as m_open, patch(
        "salt.modules.dnsutil.parse_hosts",
        MagicMock(return_value=mock_hosts_file_rtn),
    ):
        dnsutil.hosts_append("/etc/hosts", "127.0.0.1", "ad1.yuk.co,ad2.yuk.co")
        writes = m_open.write_calls()
        # We should have called .write() only once, with the expected
        # content
        num_writes = len(writes)
        assert num_writes == 1, num_writes
        expected = salt.utils.stringutils.to_str("\n127.0.0.1 ad1.yuk.co ad2.yuk.co")
        assert writes[0] == expected, writes[0]


def test_hosts_remove(mock_hosts_file, mock_writes_list):
    to_remove = "ad1.yuk.co"
    new_mock_file = mock_hosts_file + "\n127.0.0.1 " + to_remove + "\n"
    with patch("salt.utils.files.fopen", mock_open(read_data=new_mock_file)) as m_open:
        dnsutil.hosts_remove("/etc/hosts", to_remove)
        writes = m_open.write_calls()
        assert writes == mock_writes_list, writes


def test_to_seconds_hour():
    assert dnsutil._to_seconds("4H") == 14400, "Did not detect valid hours as invalid"


def test_to_seconds_day():
    assert dnsutil._to_seconds("1D") == 86400, "Did not detect valid day as invalid"


def test_to_seconds_week():
    assert (
        dnsutil._to_seconds("2W") == 604800
    ), "Did not set time greater than one week to one week"


def test_to_seconds_empty():
    assert dnsutil._to_seconds("") == 604800, "Did not set empty time to one week"


def test_to_seconds_large():
    assert (
        dnsutil._to_seconds("604801") == 604800
    ), "Did not set time greater than one week to one week"
