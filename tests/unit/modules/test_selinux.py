# -*- coding: utf-8 -*-

# Import Salt Testing Libs
from __future__ import absolute_import

import salt.modules.selinux as selinux

# Import Salt libs
from salt.exceptions import SaltInvocationError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class SelinuxModuleTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.selinux
    """

    def setup_loader_modules(self):
        return {selinux: {}}

    def test_fcontext_get_policy_parsing(self):
        """
        Test to verify that the parsing of the semanage output into fields is
        correct. Added with #45784.
        """
        cases = [
            {
                "semanage_out": "/var/www(/.*)?     all files          system_u:object_r:httpd_sys_content_t:s0",
                "name": "/var/www(/.*)?",
                "filetype": "all files",
                "sel_user": "system_u",
                "sel_role": "object_r",
                "sel_type": "httpd_sys_content_t",
                "sel_level": "s0",
            },
            {
                "semanage_out": "/var/www(/.*)? all files          system_u:object_r:httpd_sys_content_t:s0",
                "name": "/var/www(/.*)?",
                "filetype": "all files",
                "sel_user": "system_u",
                "sel_role": "object_r",
                "sel_type": "httpd_sys_content_t",
                "sel_level": "s0",
            },
            {
                "semanage_out": "/var/lib/dhcp3?                                    directory          system_u:object_r:dhcp_state_t:s0",
                "name": "/var/lib/dhcp3?",
                "filetype": "directory",
                "sel_user": "system_u",
                "sel_role": "object_r",
                "sel_type": "dhcp_state_t",
                "sel_level": "s0",
            },
            {
                "semanage_out": "/var/lib/dhcp3?  directory          system_u:object_r:dhcp_state_t:s0",
                "name": "/var/lib/dhcp3?",
                "filetype": "directory",
                "sel_user": "system_u",
                "sel_role": "object_r",
                "sel_type": "dhcp_state_t",
                "sel_level": "s0",
            },
            {
                "semanage_out": "/var/lib/dhcp3? directory          system_u:object_r:dhcp_state_t:s0",
                "name": "/var/lib/dhcp3?",
                "filetype": "directory",
                "sel_user": "system_u",
                "sel_role": "object_r",
                "sel_type": "dhcp_state_t",
                "sel_level": "s0",
            },
        ]

        for case in cases:
            with patch.dict(
                selinux.__salt__,
                {"cmd.shell": MagicMock(return_value=case["semanage_out"])},
            ):
                ret = selinux.fcontext_get_policy(case["name"])
                self.assertEqual(ret["filespec"], case["name"])
                self.assertEqual(ret["filetype"], case["filetype"])
                self.assertEqual(ret["sel_user"], case["sel_user"])
                self.assertEqual(ret["sel_role"], case["sel_role"])
                self.assertEqual(ret["sel_type"], case["sel_type"])
                self.assertEqual(ret["sel_level"], case["sel_level"])

    def test_parse_protocol_port_positive(self):
        """
        Test to verify positive parsing name, protocol and port combinations
        """
        cases = [
            {
                "name": "tcp/80",
                "protocol": None,
                "port": None,
                "expected": ("tcp", "80"),
            },
            {
                "name": "udp/53",
                "protocol": None,
                "port": None,
                "expected": ("udp", "53"),
            },
            {
                "name": "tcp_test_dns",
                "protocol": "tcp",
                "port": "53",
                "expected": ("tcp", "53"),
            },
            {
                "name": "udp_test/dns",
                "protocol": "udp",
                "port": "53",
                "expected": ("udp", "53"),
            },
        ]

        for case in cases:
            ret = selinux._parse_protocol_port(
                case["name"], case["protocol"], case["port"]
            )
            self.assertTupleEqual(ret, case["expected"])

    def test_parse_protocol_port_negative(self):
        """
        Test to verify negative parsing of name, protocol and port combinations
        """
        cases = [
            {"name": "invalid_name_no_args", "protocol": None, "port": None},
            {"name": "invalid_proto/80", "protocol": "nottcp", "port": "80"},
            {"name": "invalid_port", "protocol": "tcp", "port": "notaport"},
            {"name": "missing_proto", "protocol": None, "port": "80"},
            {"name": "missing_port", "protocol": "udp", "port": None},
        ]

        for case in cases:
            self.assertRaises(
                SaltInvocationError,
                selinux._parse_protocol_port,
                case["name"],
                case["protocol"],
                case["port"],
            )

    def test_port_get_policy_parsing(self):
        """
        Test to verify that the parsing of the semanage port output into fields is correct.
        """
        cases = [
            {
                "semanage_out": "cma_port_t                     tcp      1050",
                "name": "tcp/1050",
                "expected": {
                    "sel_type": "cma_port_t",
                    "protocol": "tcp",
                    "port": "1050",
                },
            },
            {
                "semanage_out": "cluster_port_t                 tcp      5149, 40040, 50006-50008",
                "name": "tcp/40040",
                "expected": {
                    "sel_type": "cluster_port_t",
                    "protocol": "tcp",
                    "port": "5149, 40040, 50006-50008",
                },
            },
            {
                "semanage_out": "http_port_t                    tcp      9008, 8010, 9002-9003, 80, 81, 443, 488, 8008, 8009, 8443, 9000",
                "name": "tcp/9000",
                "expected": {
                    "sel_type": "http_port_t",
                    "protocol": "tcp",
                    "port": "9008, 8010, 9002-9003, 80, 81, 443, 488, 8008, 8009, 8443, 9000",
                },
            },
            {
                "semanage_out": "vnc_port_t                     tcp      5985-5999, 5900-5983",
                "name": "tcp/5985-5999",
                "expected": {
                    "sel_type": "vnc_port_t",
                    "protocol": "tcp",
                    "port": "5985-5999, 5900-5983",
                },
            },
            {
                "semanage_out": "zebra_port_t                   tcp      2606, 2608-2609, 2600-2604",
                "name": "tcp/2608-2609",
                "expected": {
                    "sel_type": "zebra_port_t",
                    "protocol": "tcp",
                    "port": "2606, 2608-2609, 2600-2604",
                },
            },
            {
                "semanage_out": "radius_port_t                  udp      1645, 1812, 18120-18121",
                "name": "tcp/18120-18121",
                "expected": {
                    "sel_type": "radius_port_t",
                    "protocol": "udp",
                    "port": "1645, 1812, 18120-18121",
                },
            },
        ]

        for case in cases:
            with patch.dict(
                selinux.__salt__,
                {"cmd.shell": MagicMock(return_value=case["semanage_out"])},
            ):
                ret = selinux.port_get_policy(case["name"])
                self.assertDictEqual(ret, case["expected"])
