import pytest
from pytestshellutils.utils.processes import terminate_process

import salt.utils.event
import salt.utils.stringutils


@pytest.mark.slow_test
def test_event_return(master_opts):
    evt = None
    try:
        evt = salt.utils.event.EventReturn(master_opts)
        evt.start()
    except TypeError as exc:
        if "object" in str(exc):
            pytest.fail(f"'{exc}' TypeError should have not been raised")
    finally:
        if evt is not None:
            terminate_process(evt.pid, kill_children=True)


def test_filter_cluster_peer():
    assert (
        salt.utils.event.EventReturn._filter(
            {"__peer_id": "foo", "tag": "salt/test", "data": {"foo": "bar"}},
        )
        is False
    )


def test_filter_no_allow_or_deny():
    assert (
        salt.utils.event.EventReturn._filter(
            {"tag": "salt/test", "data": {"foo": "bar"}},
        )
        is True
    )


def test_filter_not_allowed():
    assert (
        salt.utils.event.EventReturn._filter(
            {"tag": "salt/test", "data": {"foo": "bar"}},
            allow=["foo/*"],
        )
        is False
    )


def test_filter_not_denied():
    assert (
        salt.utils.event.EventReturn._filter(
            {"tag": "salt/test", "data": {"foo": "bar"}},
            deny=["foo/*"],
        )
        is True
    )


def test_filter_allowed():
    assert (
        salt.utils.event.EventReturn._filter(
            {"tag": "salt/test", "data": {"foo": "bar"}},
            allow=["salt/*"],
        )
        is True
    )


def test_filter_denied():
    assert (
        salt.utils.event.EventReturn._filter(
            {"tag": "salt/test", "data": {"foo": "bar"}},
            deny=["salt/*"],
        )
        is False
    )


def test_filter_allowed_but_denied():
    assert (
        salt.utils.event.EventReturn._filter(
            {"tag": "salt/test", "data": {"foo": "bar"}},
            allow=["salt/*"],
            deny=["salt/test"],
        )
        is False
    )
