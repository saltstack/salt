import logging

import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
]

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def data_module(modules):
    return modules.data


def test_clear(data_module):
    """
    data.clear
    """
    ret = data_module.update("foo", "bar")
    assert ret

    ret = data_module.clear()
    assert ret

    ret = data_module.items()
    assert ret == {}


def test_dump(data_module):
    """
    data.dump
    """
    ret = data_module.update("foo", "bar")
    assert ret

    ret = data_module.items()
    assert ret == {"foo": "bar"}

    ret = data_module.dump("{'bar': 'baz'}")
    assert ret

    ret = data_module.items()
    assert ret == {"bar": "baz"}


def test_cas(data_module):
    """
    data.cas
    """
    ret = data_module.update("foo", "bar")
    assert ret

    ret = data_module.items()
    assert ret == {"foo": "bar"}

    ret = data_module.cas("foo", "baz", "bar")
    assert ret

    ret = data_module.items()
    assert ret == {"foo": "baz"}


def test_pop(data_module):
    """
    data.pop
    """
    ret = data_module.update("foo", "bar")
    assert ret

    ret = data_module.update("bar", "baz")
    assert ret

    ret = data_module.items()
    assert ret == {"foo": "bar", "bar": "baz"}

    ret = data_module.pop("bar")
    assert ret == "baz"

    ret = data_module.items()
    assert ret == {"foo": "bar"}


def test_get(data_module):
    """
    data.get
    """
    ret = data_module.update("foo", "bar")
    assert ret

    ret = data_module.update("bar", "baz")
    assert ret

    ret = data_module.get("foo")
    assert ret == "bar"

    ret = data_module.get(["foo", "bar"])
    assert ret == ["bar", "baz"]


def test_items(data_module):
    """
    data.items
    """
    ret = data_module.update("foo", "bar")
    assert ret

    ret = data_module.items()
    assert ret == {"foo": "bar"}


def test_values(data_module):
    """
    data.values
    """
    ret = data_module.update("foo", "bar")
    assert ret

    ret = data_module.values()
    assert ret == ["bar"]


def test_keys(data_module):
    """
    data.keys
    """
    ret = data_module.update("foo", "bar")
    assert ret

    ret = data_module.keys()
    assert ret == ["foo"]


def test_has_key(data_module):
    """
    data.has_key
    """
    ret = data_module.update("foo", "bar")
    assert ret

    ret = data_module.has_key("foo")
    assert ret

    ret = data_module.has_key("bar")

    assert not ret
