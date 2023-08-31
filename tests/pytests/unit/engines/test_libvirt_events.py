"""
unit tests for the libvirt_events engine
"""
import pytest

import salt.engines.libvirt_events as libvirt_events
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {libvirt_events: {}}


@pytest.fixture
def mock_libvirt():
    with patch("salt.engines.libvirt_events.libvirt") as mock_libvirt:
        mock_libvirt.getVersion.return_value = 2000000
        mock_libvirt.virEventRunDefaultImpl.return_value = -1  # Don't loop for ever
        mock_libvirt.VIR_DOMAIN_EVENT_ID_LIFECYCLE = 0
        mock_libvirt.VIR_DOMAIN_EVENT_ID_REBOOT = 1
        mock_libvirt.VIR_STORAGE_POOL_EVENT_ID_LIFECYCLE = 0
        mock_libvirt.VIR_STORAGE_POOL_EVENT_ID_REFRESH = 1
        mock_libvirt.VIR_NODE_DEVICE_EVENT_ID_LIFECYCLE = 0
        mock_libvirt.VIR_NODE_DEVICE_EVENT_ID_UPDATE = 1
        yield mock_libvirt


def test_get_libvirt_enum_string_subprefix(mock_libvirt):
    """
    Make sure the libvirt enum value to string works reliably with
    elements with a sub prefix, eg VIR_PREFIX_SUB_* in this case.
    """
    # Test case with a sub prefix
    mock_libvirt.VIR_PREFIX_NONE = 0
    mock_libvirt.VIR_PREFIX_ONE = 1
    mock_libvirt.VIR_PREFIX_TWO = 2
    mock_libvirt.VIR_PREFIX_SUB_FOO = 0
    mock_libvirt.VIR_PREFIX_SUB_BAR = 1
    mock_libvirt.VIR_PREFIX_SUB_FOOBAR = 2

    assert libvirt_events._get_libvirt_enum_string("VIR_PREFIX_", 2) == "two"


def test_get_libvirt_enum_string_underscores(mock_libvirt):
    """
    Make sure the libvirt enum value to string works reliably and items
    with an underscore aren't confused with sub prefixes.
    """
    mock_libvirt.VIR_PREFIX_FOO = 0
    mock_libvirt.VIR_PREFIX_BAR_FOO = 1

    assert libvirt_events._get_libvirt_enum_string("VIR_PREFIX_", 1) == "bar foo"


def test_get_domain_event_detail(mock_libvirt):
    """
    Test get_domain_event_detail function
    """
    mock_libvirt.VIR_DOMAIN_EVENT_CRASHED_PANICKED = 0
    mock_libvirt.VIR_DOMAIN_EVENT_DEFINED = 0
    mock_libvirt.VIR_DOMAIN_EVENT_UNDEFINED = 1
    mock_libvirt.VIR_DOMAIN_EVENT_CRASHED = 2
    mock_libvirt.VIR_DOMAIN_EVENT_DEFINED_ADDED = 0
    mock_libvirt.VIR_DOMAIN_EVENT_DEFINED_UPDATED = 1

    assert libvirt_events._get_domain_event_detail(1, 2) == ("undefined", "unknown")
    assert libvirt_events._get_domain_event_detail(0, 1) == ("defined", "updated")
    assert libvirt_events._get_domain_event_detail(4, 2) == ("unknown", "unknown")


def test_event_register(mock_libvirt):
    """
    Test that the libvirt_events engine actually registers events catch them and cleans
    before leaving the place.
    """
    mock_libvirt.VIR_NETWORK_EVENT_ID_LIFECYCLE = 1000

    mock_cnx = MagicMock()
    mock_libvirt.openReadOnly.return_value = mock_cnx

    # Don't loop for ever
    mock_libvirt.virEventRunDefaultImpl.return_value = -1

    mock_cnx.networkEventRegisterAny.return_value = 10000

    libvirt_events.start("test:///", "test/prefix")

    # Check that the connection has been opened
    mock_libvirt.openReadOnly.assert_called_once_with("test:///")

    # Check that the connection has been closed
    mock_cnx.close.assert_called_once()

    # Check events registration and deregistration
    mock_cnx.domainEventRegisterAny.assert_any_call(
        None,
        mock_libvirt.VIR_DOMAIN_EVENT_ID_LIFECYCLE,
        libvirt_events._domain_event_lifecycle_cb,
        {"prefix": "test/prefix", "object": "domain", "event": "lifecycle"},
    )
    mock_cnx.networkEventRegisterAny.assert_any_call(
        None,
        mock_libvirt.VIR_NETWORK_EVENT_ID_LIFECYCLE,
        libvirt_events._network_event_lifecycle_cb,
        {"prefix": "test/prefix", "object": "network", "event": "lifecycle"},
    )
    mock_cnx.storagePoolEventRegisterAny.assert_any_call(
        None,
        mock_libvirt.VIR_STORAGE_POOL_EVENT_ID_LIFECYCLE,
        libvirt_events._pool_event_lifecycle_cb,
        {"prefix": "test/prefix", "object": "pool", "event": "lifecycle"},
    )
    mock_cnx.storagePoolEventRegisterAny.assert_any_call(
        None,
        mock_libvirt.VIR_STORAGE_POOL_EVENT_ID_REFRESH,
        libvirt_events._pool_event_refresh_cb,
        {"prefix": "test/prefix", "object": "pool", "event": "refresh"},
    )
    mock_cnx.nodeDeviceEventRegisterAny.assert_any_call(
        None,
        mock_libvirt.VIR_NODE_DEVICE_EVENT_ID_LIFECYCLE,
        libvirt_events._nodedev_event_lifecycle_cb,
        {"prefix": "test/prefix", "object": "nodedev", "event": "lifecycle"},
    )
    mock_cnx.nodeDeviceEventRegisterAny.assert_any_call(
        None,
        mock_libvirt.VIR_NODE_DEVICE_EVENT_ID_UPDATE,
        libvirt_events._nodedev_event_update_cb,
        {"prefix": "test/prefix", "object": "nodedev", "event": "update"},
    )

    # Check that the deregister events are called with the result of register
    mock_cnx.networkEventDeregisterAny.assert_called_with(
        mock_cnx.networkEventRegisterAny.return_value
    )

    # Check that the default 'all' filter actually worked
    counts = {
        obj: len(callback_def)
        for obj, callback_def in libvirt_events.CALLBACK_DEFS.items()
    }
    for obj, count in counts.items():
        register = libvirt_events.REGISTER_FUNCTIONS[obj]
        assert getattr(mock_cnx, register).call_count == count


def test_event_skipped(mock_libvirt):
    """
    Test that events are skipped if their ID isn't defined in the libvirt
    module (older libvirt)
    """
    mock_libvirt.mock_add_spec(
        [
            "openReadOnly",
            "virEventRegisterDefaultImpl",
            "virEventRunDefaultImpl",
            "VIR_DOMAIN_EVENT_ID_LIFECYCLE",
        ],
        spec_set=True,
    )

    libvirt_events.start("test:///", "test/prefix")

    # Check events registration and deregistration
    mock_cnx = mock_libvirt.openReadOnly.return_value

    mock_cnx.domainEventRegisterAny.assert_any_call(
        None,
        mock_libvirt.VIR_DOMAIN_EVENT_ID_LIFECYCLE,
        libvirt_events._domain_event_lifecycle_cb,
        {"prefix": "test/prefix", "object": "domain", "event": "lifecycle"},
    )

    # Network events should have been skipped
    mock_cnx.networkEventRegisterAny.assert_not_called()


def test_event_filtered(mock_libvirt):
    """
    Test that events are skipped if their ID isn't defined in the libvirt
    module (older libvirt)
    """
    libvirt_events.start("test", "test/prefix", "domain/lifecycle")

    # Check events registration and deregistration
    mock_cnx = mock_libvirt.openReadOnly.return_value

    mock_cnx.domainEventRegisterAny.assert_any_call(
        None,
        0,
        libvirt_events._domain_event_lifecycle_cb,
        {"prefix": "test/prefix", "object": "domain", "event": "lifecycle"},
    )

    # Network events should have been filtered out
    mock_cnx.networkEventRegisterAny.assert_not_called()
