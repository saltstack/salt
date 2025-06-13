import pytest

import salt.daemons.masterapi


@pytest.mark.parametrize(
    "tag, valid",
    [
        ("salt/job/20160829225914848058/publish", False),
        ("salt/key", False),
        ("salt/cluster/fobar", False),
        ("salt/job/20160829225914848058/return", False),
        ("salt/job/20160829225914848058/new", False),
        ("salt/wheel/20160829225914848058/new", False),
        ("salt/run/20160829225914848058/new", False),
        ("salt/run/20160829225914848058/ret", False),
        ("salt/run/20160829225914848058/args", False),
        ("salt/cloud/20160829225914848058/new", False),
        ("salt/cloud/20160829225914848058/ret", False),
    ],
)
def test_valid_minion_tag(tag, valid):
    assert salt.daemons.masterapi.valid_minion_tag(tag) is valid
