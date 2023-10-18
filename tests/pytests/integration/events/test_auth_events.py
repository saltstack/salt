import time

from saltfactories.utils import random_string


def test_auth_events_autosign_grains_pend_enabled(salt_master_factory, event_listener):
    """
    Test auth events when auth_events_autosign_grains contains 'pend',
    and the minion sends autosign grains.
    """
    master_id = random_string("auth_event_master-")
    minion_id = random_string("auth_event_minion-")
    start_time = time.time()
    autosign_grain = random_string("grain-")
    events = []

    def handler(data):
        events.append(data)

    event_listener.register_auth_event_handler(master_id, handler)
    master = salt_master_factory.salt_master_daemon(
        master_id,
        overrides={
            "log_level": "info",
            "auth_events_autosign_grains": ["pend"],
        },
    )
    minion = master.salt_minion_daemon(
        minion_id,
        overrides={
            "log_level": "info",
            "grains": {
                "autosign_key": {
                    # Add some extra nesting just for the fun of it
                    "a": {
                        "b": autosign_grain,
                    }
                }
            },
            "autosign_grains": ["autosign_key"],
        },
    )

    with master.started(), minion.started():
        events = event_listener.get_events(
            [(master.id, "salt/auth")],
            after_time=start_time,
        )

        for event in events:
            assert event.data["act"] != "error"

            if event.data["act"] == "pend":
                grain = event.data["autosign_grains"]
                assert grain["autosign_key"]["a"]["b"] == autosign_grain
            else:
                assert "autosign_grains" not in event.data

    event_listener.unregister_auth_event_handler(master_id)


def test_auth_events_autosign_grains_pend_enabled_without_grains(
    salt_master_factory, event_listener
):
    """
    Test auth events when auth_events_autosign_grains contains 'pend',
    and the minion does not send autosign grains.
    """
    master_id = random_string("auth_event_master-")
    minion_id = random_string("auth_event_minion-")
    start_time = time.time()
    events = []

    def handler(data):
        events.append(data)

    event_listener.register_auth_event_handler(master_id, handler)
    master = salt_master_factory.salt_master_daemon(
        master_id,
        overrides={
            "log_level": "info",
            "auth_events_autosign_grains": ["pend"],
        },
    )
    minion = master.salt_minion_daemon(
        minion_id,
        overrides={
            "log_level": "info",
        },
    )

    with master.started(), minion.started():
        events = event_listener.get_events(
            [(master.id, "salt/auth")],
            after_time=start_time,
        )

        for event in events:
            assert event.data["act"] != "error"
            assert "autosign_grains" not in event.data

    event_listener.unregister_auth_event_handler(master_id)


def test_auth_events_autosign_grains_pend_disabled(salt_master_factory, event_listener):
    """
    Test auth events when auth_events_autosign_grains does not contain
    'pend', and the minion sends autosign grains.
    """
    master_id = random_string("auth_event_master-")
    minion_id = random_string("auth_event_minion-")
    start_time = time.time()
    autosign_grain = random_string("grain-")
    events = []

    def handler(data):
        events.append(data)

    event_listener.register_auth_event_handler(master_id, handler)
    master = salt_master_factory.salt_master_daemon(
        master_id,
        overrides={
            "log_level": "info",
            "auth_events_autosign_grains": ["reject"],
        },
    )
    minion = master.salt_minion_daemon(
        minion_id,
        overrides={
            "log_level": "info",
            "grains": {
                "autosign_key": autosign_grain,
            },
            "autosign_grains": ["autosign_key"],
        },
    )

    with master.started(), minion.started():
        events = event_listener.get_events(
            [(master.id, "salt/auth")],
            after_time=start_time,
        )

        for event in events:
            assert event.data["act"] != "error"
            assert "autosign_grains" not in event.data

    event_listener.unregister_auth_event_handler(master_id)


def test_auth_events_autosign_grains_not_set(salt_master_factory, event_listener):
    """
    Test auth events when auth_events_autosign_grains is not set at all,
    and the minion sends autosign grains.
    """
    master_id = random_string("auth_event_master-")
    minion_id = random_string("auth_event_minion-")
    start_time = time.time()
    autosign_grain = random_string("grain-")
    events = []

    def handler(data):
        events.append(data)

    event_listener.register_auth_event_handler(master_id, handler)
    master = salt_master_factory.salt_master_daemon(
        master_id,
        overrides={
            "log_level": "info",
        },
    )
    minion = master.salt_minion_daemon(
        minion_id,
        overrides={
            "log_level": "info",
            "grains": {
                "autosign_key": autosign_grain,
            },
            "autosign_grains": ["autosign_key"],
        },
    )

    with master.started(), minion.started():
        events = event_listener.get_events(
            [(master.id, "salt/auth")],
            after_time=start_time,
        )

        for event in events:
            assert event.data["act"] != "error"
            assert "autosign_grains" not in event.data

    event_listener.unregister_auth_event_handler(master_id)
