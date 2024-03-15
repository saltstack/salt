import pytest

import salt.config
import salt.daemons.masterapi as masterapi
import salt.utils.platform
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.slow_test,
]


class FakeCache:
    def __init__(self):
        self.data = {}

    def store(self, bank, key, value):
        self.data[bank, key] = value

    def fetch(self, bank, key):
        return self.data[bank, key]


@pytest.fixture
def funcs(temp_salt_master):
    opts = temp_salt_master.config.copy()
    salt.cache.MemCache.data.clear()
    funcs = masterapi.RemoteFuncs(opts)
    funcs.cache = FakeCache()
    return funcs


def test_mine_get(funcs, tgt_type_key="tgt_type"):
    """
    Asserts that ``mine_get`` gives the expected results.

    Actually this only tests that:

    - the correct check minions method is called
    - the correct cache key is subsequently used
    """
    funcs.cache.store("minions/webserver", "mine", dict(ip_addr="2001:db8::1:3"))
    with patch(
        "salt.utils.minions.CkMinions._check_compound_minions",
        MagicMock(return_value=dict(minions=["webserver"], missing=[])),
    ):
        ret = funcs._mine_get(
            {
                "id": "requester_minion",
                "tgt": "G@roles:web",
                "fun": "ip_addr",
                tgt_type_key: "compound",
            }
        )
    assert ret == dict(webserver="2001:db8::1:3")


def test_mine_get_pre_nitrogen_compat(funcs):
    """
    Asserts that pre-Nitrogen API key ``expr_form`` is still accepted.

    This is what minions before Nitrogen would issue.
    """
    test_mine_get(funcs, tgt_type_key="expr_form")


def test_mine_get_dict_str(funcs, tgt_type_key="tgt_type"):
    """
    Asserts that ``mine_get`` gives the expected results when request
    is a comma-separated list.

    Actually this only tests that:

    - the correct check minions method is called
    - the correct cache key is subsequently used
    """
    funcs.cache.store(
        "minions/webserver",
        "mine",
        dict(ip_addr="2001:db8::1:3", ip4_addr="127.0.0.1"),
    )
    with patch(
        "salt.utils.minions.CkMinions._check_compound_minions",
        MagicMock(return_value=dict(minions=["webserver"], missing=[])),
    ):
        ret = funcs._mine_get(
            {
                "id": "requester_minion",
                "tgt": "G@roles:web",
                "fun": "ip_addr,ip4_addr",
                tgt_type_key: "compound",
            }
        )
    assert ret == dict(
        ip_addr=dict(webserver="2001:db8::1:3"),
        ip4_addr=dict(webserver="127.0.0.1"),
    )


def test_mine_get_dict_list(funcs, tgt_type_key="tgt_type"):
    """
    Asserts that ``mine_get`` gives the expected results when request
    is a list.

    Actually this only tests that:

    - the correct check minions method is called
    - the correct cache key is subsequently used
    """
    funcs.cache.store(
        "minions/webserver",
        "mine",
        dict(ip_addr="2001:db8::1:3", ip4_addr="127.0.0.1"),
    )
    with patch(
        "salt.utils.minions.CkMinions._check_compound_minions",
        MagicMock(return_value=dict(minions=["webserver"], missing=[])),
    ):
        ret = funcs._mine_get(
            {
                "id": "requester_minion",
                "tgt": "G@roles:web",
                "fun": ["ip_addr", "ip4_addr"],
                tgt_type_key: "compound",
            }
        )
    assert ret == dict(
        ip_addr=dict(webserver="2001:db8::1:3"),
        ip4_addr=dict(webserver="127.0.0.1"),
    )


def test_mine_get_acl_allowed(funcs):
    """
    Asserts that ``mine_get`` gives the expected results when this is allowed
    in the client-side ACL that was stored in the mine data.
    """
    funcs.cache.store(
        "minions/webserver",
        "mine",
        {
            "ip_addr": {
                salt.utils.mine.MINE_ITEM_ACL_DATA: "2001:db8::1:4",
                salt.utils.mine.MINE_ITEM_ACL_ID: salt.utils.mine.MINE_ITEM_ACL_VERSION,
                "allow_tgt": "requester_minion",
                "allow_tgt_type": "glob",
            },
        },
    )
    # The glob check is for the resolution of the allow_tgt
    # The compound check is for the resolution of the tgt in the mine_get request.
    with patch(
        "salt.utils.minions.CkMinions._check_glob_minions",
        MagicMock(return_value={"minions": ["requester_minion"], "missing": []}),
    ), patch(
        "salt.utils.minions.CkMinions._check_compound_minions",
        MagicMock(return_value={"minions": ["webserver"], "missing": []}),
    ):
        ret = funcs._mine_get(
            {
                "id": "requester_minion",
                "tgt": "anything",
                "tgt_type": "compound",
                "fun": ["ip_addr"],
            }
        )
    assert ret == {"ip_addr": {"webserver": "2001:db8::1:4"}}


def test_mine_get_acl_rejected(funcs):
    """
    Asserts that ``mine_get`` gives the expected results when this is rejected
    in the client-side ACL that was stored in the mine data. This results in
    no data being sent back (just as if the entry wouldn't exist).
    """
    funcs.cache.store(
        "minions/webserver",
        "mine",
        {
            "ip_addr": {
                salt.utils.mine.MINE_ITEM_ACL_DATA: "2001:db8::1:4",
                salt.utils.mine.MINE_ITEM_ACL_ID: salt.utils.mine.MINE_ITEM_ACL_VERSION,
                "allow_tgt": "not_requester_minion",
                "allow_tgt_type": "glob",
            }
        },
    )
    # The glob check is for the resolution of the allow_tgt
    # The compound check is for the resolution of the tgt in the mine_get request.
    with patch(
        "salt.utils.minions.CkMinions._check_glob_minions",
        MagicMock(return_value={"minions": ["not_requester_minion"], "missing": []}),
    ), patch(
        "salt.utils.minions.CkMinions._check_compound_minions",
        MagicMock(return_value={"minions": ["webserver"], "missing": []}),
    ):
        ret = funcs._mine_get(
            {
                "id": "requester_minion",
                "tgt": "anything",
                "tgt_type": "compound",
                "fun": ["ip_addr"],
            }
        )
    assert ret == {}
