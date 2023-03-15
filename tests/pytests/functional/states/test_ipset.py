import logging

import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
]

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("ipset", check_all=False),
]


@pytest.fixture()
def setup_set(modules):
    set_name = "test_name"
    kwargs = {"range": "192.168.0.0/16", "comment": "Hello18"}
    modules.ipset.new_set(name=set_name, set_type="bitmap:ip", family="ipv4", **kwargs)
    yield set_name
    modules.ipset.delete_set(set_name)


def test_ipset_present(states, setup_set):
    """
    test ipset.present
    """
    # add set first
    entry = "192.168.0.3"
    comment = "Hello"
    ret = states.ipset.present(
        name="setname_entries", set_name=setup_set, entry=entry, comment=comment
    )
    assert ret.result
    assert (
        ret.comment
        == f"entry {entry} comment {comment} added to set {setup_set} for family ipv4\n"
    )
