"""
    :codeauthor: Anthony Shaw <anthonyshaw@apache.org>
"""

import pytest

import salt.states.libcloud_dns as libcloud_dns
from salt.modules.libcloud_dns import _simple_record, _simple_zone


class DNSTestZone:
    def __init__(self, id, domain):
        self.id = id
        self.type = "master"
        self.ttl = 4400
        self.domain = domain
        self.extra = {}


class DNSTestRecord:
    def __init__(self, id, name, record_type, data):
        self.id = id
        self.name = name
        self.type = record_type
        self.ttl = 4400
        self.data = data
        self.zone = DNSTestZone("test", "domain")
        self.extra = {}


@pytest.fixture
def configure_loader_modules():
    def list_records(zone_id, profile):
        test_records = {
            "zone1": [_simple_record(DNSTestRecord(0, "www", "A", "127.0.0.1"))]
        }
        return test_records[zone_id]

    def list_zones(profile):
        return [_simple_zone(DNSTestZone("zone1", "test.com"))]

    def _record(*args):
        return True

    return {
        libcloud_dns: {
            "__salt__": {
                "libcloud_dns.list_zones": list_zones,
                "libcloud_dns.list_records": list_records,
                "libcloud_dns.create_record": _record,
                "libcloud_dns.delete_record": _record,
                "libcloud_dns.create_zone": _record,
                "libcloud_dns.delete_zone": _record,
            }
        }
    }


def test_present_record_exists():
    """
    Try and create a record that already exists
    """
    result = libcloud_dns.record_present("www", "test.com", "A", "127.0.0.1", "test")
    assert result


def test_present_record_does_not_exist():
    """
    Try and create a record that already exists
    """
    result = libcloud_dns.record_present("mail", "test.com", "A", "127.0.0.1", "test")
    assert result


def test_absent_record_exists():
    """
    Try and deny a record that already exists
    """
    result = libcloud_dns.record_absent("www", "test.com", "A", "127.0.0.1", "test")
    assert result


def test_absent_record_does_not_exist():
    """
    Try and deny a record that already exists
    """
    result = libcloud_dns.record_absent("mail", "test.com", "A", "127.0.0.1", "test")
    assert result


def test_present_zone_not_found():
    """
    Assert that when you try and ensure present state for a record to a zone that doesn't exist
    it fails gracefully
    """
    result = libcloud_dns.record_present(
        "mail", "notatest.com", "A", "127.0.0.1", "test"
    )
    assert not result["result"]


def test_absent_zone_not_found():
    """
    Assert that when you try and ensure absent state for a record to a zone that doesn't exist
    it fails gracefully
    """
    result = libcloud_dns.record_absent(
        "mail", "notatest.com", "A", "127.0.0.1", "test"
    )
    assert not result["result"]


def test_zone_present():
    """
    Assert that a zone is present (that did not exist)
    """
    result = libcloud_dns.zone_present("testing.com", "master", "test1")
    assert result


def test_zone_already_present():
    """
    Assert that a zone is present (that did exist)
    """
    result = libcloud_dns.zone_present("test.com", "master", "test1")
    assert result


def test_zone_absent():
    """
    Assert that a zone that did exist is absent
    """
    result = libcloud_dns.zone_absent("test.com", "test1")
    assert result


def test_zone_already_absent():
    """
    Assert that a zone that did not exist is absent
    """
    result = libcloud_dns.zone_absent("testing.com", "test1")
    assert result
