"""
Verify AsyncAuth.authenticate publishes salt/auth/creds synchronously when
auth_events=True. This guards against the macOS regression where the event was
fired via fire_event_async on the calling subprocess io_loop and got lost
before the parent minion's handle_event consumer could update creds_map.
"""

import os

import pytest

import salt.crypt as crypt
from tests.support.mock import MagicMock, patch


@pytest.fixture
def minion_root(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "etc").mkdir()
    (root / "etc" / "salt").mkdir()
    (root / "etc" / "salt" / "pki").mkdir()
    yield root


async def test_authenticate_fires_creds_event_synchronously(minion_root, io_loop):
    """
    With auth_events=True, the salt/auth/creds event MUST be published via the
    synchronous event.fire_event() (not fire_event_async with io_loop=...) so
    that the publish completes before the `with` block tears down the IPC
    session, regardless of which io_loop the caller is on.
    """
    pki_dir = minion_root / "etc" / "salt" / "pki"
    os.makedirs(str(pki_dir), exist_ok=True)
    opts = {
        "id": "minion",
        "__role": "minion",
        "auth_events": True,
        "pki_dir": str(pki_dir),
        "master_uri": "tcp://127.0.0.1:4505",
        "keysize": 4096,
        "acceptance_wait_time": 60,
        "keys.cache_driver": "localfs_key",
        "acceptance_wait_time_max": 60,
    }
    priv, pub = crypt.gen_keys(opts["keysize"])
    keypath = pki_dir / "minion"
    keypath.with_suffix(".pem").write_text(priv)
    keypath.with_suffix(".pub").write_text(pub)

    aes = crypt.Crypticle.generate_key_string()
    session = crypt.Crypticle.generate_key_string()

    auth = crypt.AsyncAuth(opts, io_loop)

    async def mock_sign_in(*args, **kwargs):
        return mock_sign_in.response

    mock_sign_in.response = {"enc": "pub", "aes": aes, "session": session}
    auth.sign_in = mock_sign_in

    # Capture how the event bus is used by AsyncAuth.authenticate()
    fake_event = MagicMock()
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=fake_event)
    cm.__exit__ = MagicMock(return_value=False)
    get_event_mock = MagicMock(return_value=cm)

    with patch("salt.utils.event.get_event", get_event_mock):
        await auth.authenticate()

    # The IPC session must be opened with the role's bus and NO io_loop, so
    # the publish runs synchronously on the active loop and completes before
    # the context manager exits (the bug was passing io_loop=self.io_loop
    # which scheduled the publish on a coro that may never get awaited from
    # a short-lived subprocess).
    get_event_mock.assert_called_once()
    call_kwargs = get_event_mock.call_args.kwargs
    assert "io_loop" not in call_kwargs, (
        "get_event must NOT be passed io_loop; the event must fire on the "
        "role's own bus, synchronously"
    )
    assert call_kwargs.get("listen") is False

    # Must be the SYNC fire_event(...), NOT fire_event_async(...).
    fake_event.fire_event.assert_called_once()
    assert not fake_event.fire_event_async.called, (
        "auth/creds must be fired synchronously via event.fire_event, not "
        "fire_event_async"
    )

    # Sanity-check the event payload/tag.
    args, _ = fake_event.fire_event.call_args
    payload, tag = args
    assert tag == "salt/auth/creds"
    assert payload["creds"]["aes"] == aes
    assert payload["creds"]["session"] == session
