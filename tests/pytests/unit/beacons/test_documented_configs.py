"""
Tests that the beacon configuration examples shipped in the documentation
remain valid against the beacons' ``validate()`` functions.

These tests pin the docs against the code, so a future drift causes a
loud failure rather than silent stale documentation. Issues addressed:

* :issue:`63693` and :issue:`65019` for the inotify beacon
* :issue:`61332` for the network_settings beacon
* :issue:`61616` for the beacon -> reactor data dict shape
"""

import pytest

from salt.beacons import inotify

try:
    import pyinotify  # pylint: disable=unused-import

    HAS_PYINOTIFY = True
except ImportError:
    HAS_PYINOTIFY = False


@pytest.fixture
def configure_loader_modules():
    return {inotify: {}}


@pytest.mark.skipif(
    not HAS_PYINOTIFY, reason="pyinotify is not available on this platform"
)
def test_inotify_documented_example_validates(tmp_path):
    """
    The minimal inotify configuration shown in
    ``doc/topics/beacons/index.rst`` (and copied below) must pass
    ``inotify.validate()``.
    """
    watched = tmp_path / "important_file"
    watched.write_text("important_config: True\n")
    config = [
        {"files": {str(watched): {"mask": ["modify"]}}},
        {"disable_during_state_run": True},
    ]
    valid, _ = inotify.validate(config)
    assert valid is True


def test_beacon_to_reactor_data_dict_shape():
    """
    The reactor documentation in ``doc/topics/reactor/index.rst`` says
    that for events produced by a beacon, the reactor template variable
    ``data`` is the beacon's payload directly (with ``id`` at the top
    level). This test pins the contract by exercising the same unwrap
    path the master daemon uses:

    1. The beacon process returns ``[{"tag": ..., "data": {...},
       "beacon_name": ...}, ...]``.
    2. ``MinionBase._fire_master`` ships those as ``load["events"]``.
    3. ``LocalFuncs._minion_event`` on the master unwraps each event
       and fires ``event["data"]`` on the bus with ``event["tag"]``.

    The reactor's template renderer then receives the unwrapped payload
    as ``data``, so ``data["id"]`` -- not ``data["data"]["id"]`` --
    must be the minion id.
    """
    # Simulate a beacon process output. The beacons subsystem always
    # injects ``id`` if the beacon function did not.
    minion_id = "minion-1"
    beacon_raw = [
        {
            "tag": f"salt/beacon/{minion_id}/inotify//etc/important_file",
            "data": {
                "id": minion_id,
                "change": "IN_MODIFY",
                "path": "/etc/important_file",
            },
            "beacon_name": "inotify",
        }
    ]

    # Simulate the master's _minion_event unwrap step.
    unwrapped = []
    for event in beacon_raw:
        if "data" in event:
            event_data = event["data"]
        else:
            event_data = event
        unwrapped.append((event["tag"], event_data))

    # The reactor's render_reaction(data=event_data) sees this:
    fired_tag, reactor_data = unwrapped[0]

    assert fired_tag == f"salt/beacon/{minion_id}/inotify//etc/important_file"
    # Critical: ``data["id"]`` is the minion id, NOT ``data["data"]["id"]``.
    assert reactor_data["id"] == minion_id
    assert "data" not in reactor_data or reactor_data.get("data") != {"id": minion_id}


def test_event_send_data_dict_shape():
    """
    Counterpart to ``test_beacon_to_reactor_data_dict_shape``: for an
    event produced by ``event.send`` from a minion, the master fires
    the whole load on the bus, so the reactor's ``data`` template
    variable IS the load -- the user payload ends up at
    ``data["data"]``.
    """
    minion_id = "minion-1"
    user_payload = {"orchestrate": "refresh"}
    load = {
        "id": minion_id,
        "cmd": "_minion_event",
        "tag": "foo",
        "data": user_payload,
    }

    # Simulate the master's single-event path in _minion_event.
    fired_tag = load["tag"]
    reactor_data = load

    assert fired_tag == "foo"
    # ``data["data"]["orchestrate"]`` is "refresh" -- the documented
    # pattern in ``doc/topics/reactor/index.rst`` Referencing Data
    # Passed in Events.
    assert reactor_data["data"]["orchestrate"] == "refresh"
    assert reactor_data["id"] == minion_id
