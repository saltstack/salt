import logging

import pytest

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("ipset", check_all=False),
]


log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def ipset(modules):
    return modules.ipset


@pytest.fixture()
def setup_set(ipset):
    set_name = "test_name"
    kwargs = {"range": "192.168.0.0/16", "comment": "Hello18"}
    ipset.new_set(name=set_name, set_type="bitmap:ip", family="ipv4", **kwargs)
    yield set_name
    ipset.delete_set(set_name)


def test_ipset_add(ipset, setup_set):
    """
    test ipset.add
    """
    # add set first
    ret = ipset.add(name=setup_set, entry="192.168.0.3 comment Hello18")
    assert ret == "Success"
    check_set = ipset.list_sets()
    assert any([x for x in check_set if x["Name"] == setup_set])


def test_ipset_add_comment_kwarg(ipset, setup_set):
    """
    test ipset.add when comment is set in kwarg
    """
    # add set first
    kwargs = {"comment": "Hello19"}
    entry = "192.168.0.3"
    ret = ipset.add(name=setup_set, entry="192.168.0.3", **kwargs)
    assert ret == "Success"
    check_set = ipset.list_sets()
    assert any([x for x in check_set if x["Name"] == setup_set])


def test_ipset_new_set_with_family(ipset):
    """
    test ipset.new_set with set_type that uses family (eg. hash:ip)
    """
    set_name = "test_name_haship"
    ret = ipset.new_set(name=set_name, set_type="hash:ip")
    assert ret is True
    check_set = ipset.list_sets()
    try:
        assert any([x for x in check_set if x["Name"] == set_name])
    finally:
        ipset.delete_set(set_name)
