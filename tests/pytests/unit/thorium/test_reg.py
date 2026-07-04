"""
    tests.pytests.unit.thorium.test_reg
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Unit tests for the thorium reg module
"""

import pytest

import salt.thorium.reg as reg


@pytest.fixture
def setup_reg_dunders():
    # The thorium loader injects ``__reg__`` and ``__events__`` as module
    # globals.  Set them directly since they are not standard salt dunders
    # handled by the loader mock fixture.
    reg.__dict__["__reg__"] = {}
    reg.__dict__["__events__"] = [
        {
            "tag": "phil/was/here",
            "data": {"data": {42: "the answer"}, "_stamp": "2017-09-06"},
        }
    ]
    try:
        yield
    finally:
        reg.__dict__.pop("__reg__", None)
        reg.__dict__.pop("__events__", None)


def test_list_integer_add(setup_reg_dunders):
    """
    An integer ``add`` value must not raise AttributeError (no .split on int)
    and the integer key should be looked up in the event data.
    """
    ret = reg.list_("myregister", add=42, match="phil/was/here")
    assert ret["result"] is True
    assert reg.__dict__["__reg__"]["myregister"]["val"] == [{42: "the answer"}]


def test_list_string_add_still_splits(setup_reg_dunders):
    """
    A comma separated string ``add`` value must still be split into keys.
    """
    reg.__dict__["__events__"][0]["data"]["data"] = {"a": 1, "b": 2}
    ret = reg.list_("myregister", add="a,b", match="phil/was/here")
    assert ret["result"] is True
    assert reg.__dict__["__reg__"]["myregister"]["val"] == [{"a": 1, "b": 2}]
