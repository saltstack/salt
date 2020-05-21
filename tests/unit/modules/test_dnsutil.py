# -*- coding: utf-8 -*-
"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import Salt Libs
import salt.modules.dnsutil as dnsutil
import salt.utils.stringutils
from tests.support.mock import MagicMock, mock_open, patch

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf

log = logging.getLogger(__name__)

mock_hosts_file = salt.utils.stringutils.to_str(
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

mock_hosts_file_rtn = {
    "::1": ["localhost"],
    "255.255.255.255": ["broadcasthost"],
    "127.0.0.1": ["localhost"],
    "fe80::1%lo0": ["localhost"],
}

mock_soa_zone = salt.utils.stringutils.to_str(
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

mock_writes_list = salt.utils.data.decode(
    [
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
    ],
    to_str=True,
)


class DNSUtilTestCase(TestCase):
    def test_parse_hosts(self):
        with patch("salt.utils.files.fopen", mock_open(read_data=mock_hosts_file)):
            self.assertEqual(
                dnsutil.parse_hosts(),
                {
                    "::1": ["localhost"],
                    "255.255.255.255": ["broadcasthost"],
                    "127.0.0.1": ["localhost"],
                    "fe80::1%lo0": ["localhost"],
                },
            )

    def test_hosts_append(self):
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
            expected = salt.utils.stringutils.to_str(
                "\n127.0.0.1 ad1.yuk.co ad2.yuk.co"
            )
            assert writes[0] == expected, writes[0]

    def test_hosts_remove(self):
        to_remove = "ad1.yuk.co"
        new_mock_file = mock_hosts_file + "\n127.0.0.1 " + to_remove + "\n"
        with patch(
            "salt.utils.files.fopen", mock_open(read_data=new_mock_file)
        ) as m_open:
            dnsutil.hosts_remove("/etc/hosts", to_remove)
            writes = m_open.write_calls()
            assert writes == mock_writes_list, writes

    @skipIf(True, "Waiting on bug report fixes")
    def test_parse_zone(self):
        with patch("salt.utils.files.fopen", mock_open(read_data=mock_soa_zone)):
            log.debug(mock_soa_zone)
            log.debug(dnsutil.parse_zone("/var/lib/named/example.com.zone"))

    def test_to_seconds_hour(self):
        self.assertEqual(
            dnsutil._to_seconds("4H"),
            14400,
            msg="Did not detect valid hours as invalid",
        )

    def test_to_seconds_day(self):
        self.assertEqual(
            dnsutil._to_seconds("1D"), 86400, msg="Did not detect valid day as invalid"
        )

    def test_to_seconds_week(self):
        self.assertEqual(
            dnsutil._to_seconds("2W"),
            604800,
            msg="Did not set time greater than one week to one week",
        )

    def test_to_seconds_empty(self):
        self.assertEqual(
            dnsutil._to_seconds(""), 604800, msg="Did not set empty time to one week"
        )

    def test_to_seconds_large(self):
        self.assertEqual(
            dnsutil._to_seconds("604801"),
            604800,
            msg="Did not set time greater than one week to one week",
        )
