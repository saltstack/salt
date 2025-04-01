"""
    Test cases for salt.modules.dig
"""

import pytest

import salt.modules.dig as dig
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {dig: {}}


class SpfValues:
    def __call__(self, key, python_shell=False):
        _spf_values = {
            "dig +short xmission.com TXT": {
                "pid": 27282,
                "retcode": 0,
                "stderr": "",
                "stdout": '"v=spf1 a mx include:_spf.xmission.com ?all"',
            },
            "dig +short _spf.xmission.com TXT": {
                "pid": 27282,
                "retcode": 0,
                "stderr": "",
                "stdout": '"v=spf1 a mx ip4:198.60.22.0/24 ip4:166.70.13.0/24 ~all"',
            },
            "dig +short xmission-redirect.com TXT": {
                "pid": 27282,
                "retcode": 0,
                "stderr": "",
                "stdout": "v=spf1 redirect=_spf.xmission.com",
            },
            "dig +short foo.com TXT": {
                "pid": 27282,
                "retcode": 0,
                "stderr": "",
                "stdout": "v=spf1 ip4:216.73.93.70/31 ip4:216.73.93.72/31 ~all",
            },
        }
        return _spf_values.get(
            " ".join(key), {"pid": 27310, "retcode": 0, "stderr": "", "stdout": ""}
        )


def test_dig_cname_found():
    dig_mock = MagicMock(
        return_value={
            "pid": 2018,
            "retcode": 0,
            "stderr": "",
            "stdout": "bellanotte1986.github.io.",
        }
    )
    with patch.dict(dig.__salt__, {"cmd.run_all": dig_mock}):
        assert dig.CNAME("www.eitr.tech") == "bellanotte1986.github.io."


def test_dig_cname_none_found():
    dig_mock = MagicMock(
        return_value={
            "pid": 2022,
            "retcode": 0,
            "stderr": "",
            "stdout": "",
        }
    )
    with patch.dict(dig.__salt__, {"cmd.run_all": dig_mock}):
        assert dig.CNAME("www.google.com") == ""


def test_check_ip():
    assert dig.check_ip("127.0.0.1")


def test_check_ip_ipv6():
    assert dig.check_ip("1111:2222:3333:4444:5555:6666:7777:8888")


def test_check_ip_ipv6_valid():
    assert dig.check_ip("2607:fa18:0:3::4")


def test_check_ip_neg():
    assert not dig.check_ip("-127.0.0.1")


def test_check_ip_empty():
    assert not dig.check_ip("")


def test_a():
    dig_mock = MagicMock(
        return_value={
            "pid": 3656,
            "retcode": 0,
            "stderr": "",
            "stdout": (
                "74.125.193.104\n"
                "74.125.193.105\n"
                "74.125.193.99\n"
                "74.125.193.106\n"
                "74.125.193.103\n"
                "74.125.193.147"
            ),
        }
    )
    with patch.dict(dig.__salt__, {"cmd.run_all": dig_mock}):
        assert dig.A("www.google.com") == [
            "74.125.193.104",
            "74.125.193.105",
            "74.125.193.99",
            "74.125.193.106",
            "74.125.193.103",
            "74.125.193.147",
        ]


def test_ptr():
    dig_mock = MagicMock(
        return_value={
            "pid": 3657,
            "retcode": 0,
            "stderr": "",
            "stdout": ("dns.google."),
        }
    )
    with patch.dict(dig.__salt__, {"cmd.run_all": dig_mock}):
        assert dig.ptr("8.8.8.8") == [
            "dns.google.",
        ]


def test_aaaa():
    dig_mock = MagicMock(
        return_value={
            "pid": 25451,
            "retcode": 0,
            "stderr": "",
            "stdout": "2607:f8b0:400f:801::1014",
        }
    )
    with patch.dict(dig.__salt__, {"cmd.run_all": dig_mock}):
        assert dig.AAAA("www.google.com") == ["2607:f8b0:400f:801::1014"]


def test_ns():
    with patch("salt.modules.dig.A", MagicMock(return_value=["ns4.google.com."])):
        dig_mock = MagicMock(
            return_value={
                "pid": 26136,
                "retcode": 0,
                "stderr": "",
                "stdout": "ns4.google.com.",
            }
        )
        with patch.dict(dig.__salt__, {"cmd.run_all": dig_mock}):
            assert dig.NS("google.com") == ["ns4.google.com."]


def test_spf():
    dig_mock = MagicMock(side_effect=SpfValues())
    with patch.dict(dig.__salt__, {"cmd.run_all": dig_mock}):
        assert dig.SPF("foo.com") == ["216.73.93.70/31", "216.73.93.72/31"]


def test_spf_redir():
    """
    Test for SPF records which use the 'redirect' SPF mechanism
    https://en.wikipedia.org/wiki/Sender_Policy_Framework#Mechanisms
    """
    dig_mock = MagicMock(side_effect=SpfValues())
    with patch.dict(dig.__salt__, {"cmd.run_all": dig_mock}):
        assert dig.SPF("xmission-redirect.com") == ["198.60.22.0/24", "166.70.13.0/24"]


def test_spf_include():
    """
    Test for SPF records which use the 'include' SPF mechanism
    https://en.wikipedia.org/wiki/Sender_Policy_Framework#Mechanisms
    """
    dig_mock = MagicMock(side_effect=SpfValues())
    with patch.dict(dig.__salt__, {"cmd.run_all": dig_mock}):
        assert dig.SPF("xmission.com") == ["198.60.22.0/24", "166.70.13.0/24"]


def test_mx():
    dig_mock = MagicMock(
        return_value={
            "pid": 27780,
            "retcode": 0,
            "stderr": "",
            "stdout": (
                "10 aspmx.l.google.com.\n"
                "20 alt1.aspmx.l.google.com.\n"
                "40 alt3.aspmx.l.google.com.\n"
                "50 alt4.aspmx.l.google.com.\n"
                "30 alt2.aspmx.l.google.com."
            ),
        }
    )
    with patch.dict(dig.__salt__, {"cmd.run_all": dig_mock}):
        assert dig.MX("google.com") == [
            ["10", "aspmx.l.google.com."],
            ["20", "alt1.aspmx.l.google.com."],
            ["40", "alt3.aspmx.l.google.com."],
            ["50", "alt4.aspmx.l.google.com."],
            ["30", "alt2.aspmx.l.google.com."],
        ]
