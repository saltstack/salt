import time

from saltfactories.utils import random_string

from tests.conftest import FIPS_TESTRUN

_MASTER_FIPS_OVERRIDES = {
    "fips_mode": FIPS_TESTRUN,
    "publish_signing_algorithm": (
        "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
    ),
}

_MINION_FIPS_OVERRIDES = {
    "fips_mode": FIPS_TESTRUN,
    "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
    "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
}


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
            **_MASTER_FIPS_OVERRIDES,
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
            **_MINION_FIPS_OVERRIDES,
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
            **_MASTER_FIPS_OVERRIDES,
        },
    )
    minion = master.salt_minion_daemon(
        minion_id,
        overrides={
            "log_level": "info",
            **_MINION_FIPS_OVERRIDES,
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
            **_MASTER_FIPS_OVERRIDES,
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
            **_MINION_FIPS_OVERRIDES,
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
            **_MASTER_FIPS_OVERRIDES,
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
            **_MINION_FIPS_OVERRIDES,
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
