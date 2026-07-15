"""
    :codeauthor: `Gareth J. Greenaway <gareth@saltstack.com>`

    tests.unit.cloud.clouds.digitalocean_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

import logging

import pytest

from salt.cloud.clouds import digitalocean
from salt.exceptions import SaltCloudSystemExit
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


def test_reboot_no_call():
    """
    Tests that a SaltCloudSystemExit is raised when
    kwargs that are provided do not include an action.
    """
    with pytest.raises(SaltCloudSystemExit) as excinfo:
        digitalocean.reboot(name="fake_name")

    assert "The reboot action must be called with -a or --action." == str(excinfo.value)


def test_destroy_dns_records_pagination_55143():
    """
    destroy_dns_records must walk every page of DNS records, not just the
    first, so a matching record that lives past page 1 is still deleted.

    Regression test for https://github.com/saltstack/salt/issues/55143: the
    DigitalOcean API paginates records (20 per page by default), and the driver
    only ever requested the first page, so records past it were never matched
    or deleted. destroy() calls destroy_dns_records(name) with the minion name,
    which splits into domain="example.com" / hostname="www" here.
    """
    # Page 1: 20 non-matching records plus a "next" link so the loop pages on.
    page1 = {
        "domain_records": [{"id": i, "name": "other"} for i in range(1, 21)],
        "links": {
            "pages": {
                "next": "https://api.digitalocean.com/v2/domains/example.com/records?page=2",
                "last": "https://api.digitalocean.com/v2/domains/example.com/records?page=2",
            }
        },
        "meta": {"total": 21},
    }
    # Page 2: the matching record, with no further links so the loop stops.
    page2 = {
        "domain_records": [{"id": 42, "name": "www"}],
        "meta": {"total": 21},
    }

    def fake_query(
        method=None, droplet_id=None, command=None, http_method="get", args=None
    ):
        # command == "records" is the unpaginated call the buggy driver made.
        if command == "records" or command.startswith("records?page=1"):
            return page1
        if command.startswith("records?page=2"):
            return page2
        if command.startswith("records/") and http_method == "delete":
            return True
        raise AssertionError(f"unexpected query command={command!r}")

    query_mock = MagicMock(side_effect=fake_query)
    with patch.object(digitalocean, "query", query_mock):
        digitalocean.destroy_dns_records("www.example.com")

    commands = [call.kwargs.get("command") for call in query_mock.call_args_list]
    # The loop must have paged past page 1.
    assert any(c and c.startswith("records?page=2") for c in commands)
    # The page-2 record was matched and deleted.
    query_mock.assert_any_call(
        method="domains",
        droplet_id="example.com",
        command="records/42",
        http_method="delete",
    )
    # Non-matching page-1 records must never be deleted.
    for i in range(1, 21):
        assert f"records/{i}" not in commands, f"non-matching record {i} was deleted"


def test_destroy_dns_records_no_matching_records_55143():
    """
    Inverse of the pagination fix: a domain whose record set is empty must
    result in zero deletions. This passes with and without the fix -- an empty
    record set yields no deletions regardless of how many pages are walked --
    so it guards against the paginated fix ever over-deleting.
    """
    empty_page = {"domain_records": [], "meta": {"total": 0}}

    def fake_query(
        method=None, droplet_id=None, command=None, http_method="get", args=None
    ):
        if command.startswith("records/"):
            raise AssertionError("no record should be deleted")
        return empty_page

    query_mock = MagicMock(side_effect=fake_query)
    with patch.object(digitalocean, "query", query_mock):
        digitalocean.destroy_dns_records("www.example.com")

    delete_calls = [
        call
        for call in query_mock.call_args_list
        if call.kwargs.get("http_method") == "delete"
    ]
    assert delete_calls == []


def test_destroy_dns_records_domain_lookup_failure_55143():
    """
    Peripheral coverage of the touched function: when the record lookup raises
    SaltCloudSystemExit (e.g. the domain is not managed by DigitalOcean),
    destroy_dns_records returns False and attempts no deletions.
    """
    query_mock = MagicMock(side_effect=SaltCloudSystemExit("boom"))
    with patch.object(digitalocean, "query", query_mock):
        result = digitalocean.destroy_dns_records("www.example.com")

    assert result is False
    for call in query_mock.call_args_list:
        assert call.kwargs.get("http_method", "get") != "delete"
