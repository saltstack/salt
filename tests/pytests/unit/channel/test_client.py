import asyncio
import warnings

import pytest

import salt.channel.client
import salt.crypt
import salt.exceptions
import salt.payload
from tests.support.mock import AsyncMock, MagicMock, patch


def test_async_methods():
    "Validate all defined async_methods and close_methods are present"
    async_classes = [
        salt.channel.client.AsyncReqChannel,
        salt.channel.client.AsyncPubChannel,
    ]
    method_attrs = [
        "async_methods",
        "close_methods",
    ]
    for cls in async_classes:
        for attr in method_attrs:
            assert hasattr(cls, attr)
            assert isinstance(getattr(cls, attr), list)
            for name in getattr(cls, attr):
                assert hasattr(cls, name)


async def test_async_pub_channel_key_overwritten_by_bad_data(minion_opts, tmp_path):
    """
    Ensure AsyncPubChannel raises a SaltClientError when it encounters a bad key.

    This bug is a bit nuanced because of how the auth module uses singletons.
    We're validating an error from salt.crypt.AsyncAuth.gen_token because of
    bad key data results in a SaltClientError. This error is handled by
    Minion._connect_minion resulting error message explaining the minion
    connection failed due to bad key data.

    https://github.com/saltstack/salt/issues/68190
    """
    minion_opts["pki_dir"] = str(tmp_path)
    minion_opts["id"] = "minion"
    minion_opts["master_ip"] = "127.0.0.1"

    # This will initialize the singleton with a valid key.
    with patch("salt.transport.publish_client"):
        channel = salt.channel.client.AsyncPubChannel.factory(minion_opts, crypt="aes")
        channel.close()

    # Now we need to overwrite the bad key with the new one. When gen_token
    # gets called a SaltClientError will ge traised
    key_path = tmp_path / "minion.pem"
    key_path.chmod(0o660)
    key_path.write_text(
        "asdfiosjaoiasdfjooaisjdfo902j0ianosdifn091091jw0edw09jcr89eq79vr"
    )
    with pytest.raises(salt.exceptions.SaltClientError):
        salt.channel.client.AsyncPubChannel.factory(minion_opts, crypt="aes")


async def test_async_pub_channel_decode_payload_drops_undecrypted_payload():
    """
    When a payload cannot be decrypted even after re-authenticating the master it
    should be discarded instead of surfacing bytes to the minion handler.
    """

    class DummyCrypticle:
        def loads(self, payload):  # pylint: disable=unused-argument
            raise salt.crypt.AuthenticationError()

    class DummyAuth:
        def __init__(self):
            self.crypticle = DummyCrypticle()
            self.authenticated = True

        async def authenticate(self):
            raise salt.crypt.AuthenticationError()

    channel = object.__new__(salt.channel.client.AsyncPubChannel)
    channel.opts = {"master_ip": "127.0.0.1"}
    channel.auth = DummyAuth()

    payload = {"enc": "aes", "load": b"ciphertext"}

    assert await channel._decode_payload(payload) is None


class _StubTransport:
    """Minimal transport stub whose ``send`` returns pre-canned encrypted replies."""

    ttype = "zeromq"

    def __init__(self, replies):
        # ``replies`` is a list of bytes payloads returned in order.
        self._replies = list(replies)
        self.sent = []

    async def send(self, payload, timeout=None):  # pylint: disable=unused-argument
        self.sent.append(payload)
        return self._replies.pop(0)


class _StubAuth:
    """Auth stub that owns a ``session_crypticle`` we can rotate mid-test."""

    def __init__(self, opts, session_crypticle):
        self.opts = opts
        self.session_crypticle = session_crypticle
        self.authenticated = True
        self.mpub = "master.pub"

    def gen_token(self, clear_tok):  # pragma: no cover - unused
        return b""

    async def authenticate(self):  # pragma: no cover - unused
        return None


def _make_channel(minion_opts, tmp_path, transport, auth):
    minion_opts["pki_dir"] = str(tmp_path)
    minion_opts["id"] = "minion"
    minion_opts["master_uri"] = "tcp://127.0.0.1:4506"
    minion_opts.setdefault("minion_sign_messages", False)
    return salt.channel.client.AsyncReqChannel(
        minion_opts, transport, auth, timeout=1, tries=1
    )


async def test_do_transfer_reauth_mid_flight_uses_same_crypticle(minion_opts, tmp_path):
    """
    Regression for issue #69753: if ``self.auth.session_crypticle`` is
    swapped between the ``dumps`` on the send path and the ``loads`` on the
    receive path of ``_do_transfer``, the fixed code must still decrypt
    with the crypticle that produced the outbound nonce.
    """
    old_key = salt.crypt.Crypticle.generate_key_string()
    new_key = salt.crypt.Crypticle.generate_key_string()

    # Master encrypts its reply with the *old* crypticle (the one that
    # was in place when the request went out).
    master_old = salt.crypt.Crypticle(minion_opts, old_key)
    # This is the reply the master would send, keyed to the request's
    # nonce (fake, but we can intercept it below).
    nonce_holder = {}

    class _CapturingTransport(_StubTransport):
        async def send(self, payload, timeout=None):
            self.sent.append(payload)
            # Extract the actual nonce the channel used by decrypting the
            # outbound load with the *old* key (which must have been used
            # to encrypt it).
            outer = (
                salt.payload.loads(payload) if isinstance(payload, bytes) else payload
            )
            enc_load = outer["load"]
            decrypted = master_old.loads(enc_load)
            nonce_holder["nonce"] = decrypted["nonce"]
            reply = master_old.dumps({"result": "ok"}, nonce=decrypted["nonce"])
            return reply

    minion_old = salt.crypt.Crypticle(minion_opts, old_key)
    minion_new = salt.crypt.Crypticle(minion_opts, new_key)
    auth = _StubAuth(minion_opts, minion_old)
    transport = _CapturingTransport([])

    channel = _make_channel(minion_opts, tmp_path, transport, auth)

    original_transport_send = transport.send

    async def _rotate_and_send(payload, timeout=None):
        reply = await original_transport_send(payload, timeout=timeout)
        auth.session_crypticle = minion_new
        return reply

    transport.send = _rotate_and_send
    result = await channel._crypted_transfer({"cmd": "test"}, timeout=1)

    assert result == {"result": "ok"}
    assert nonce_holder["nonce"]  # sanity: request had a nonce


async def test_do_transfer_serialized_by_lock(minion_opts, tmp_path):
    """
    Regression for issue #69753: two concurrent ``_crypted_transfer``
    calls on the same channel must not overlap.  We assert the second
    call's send does not begin until the first call's reply has been
    decrypted.
    """
    key = salt.crypt.Crypticle.generate_key_string()
    master = salt.crypt.Crypticle(minion_opts, key)
    minion = salt.crypt.Crypticle(minion_opts, key)

    events = []
    gate = asyncio.Event()
    started = asyncio.Event()

    class _OrderingTransport(_StubTransport):
        def __init__(self):
            super().__init__([])
            self.call = 0

        async def send(self, payload, timeout=None):
            self.call += 1
            events.append(f"send-start-{self.call}")
            outer = (
                salt.payload.loads(payload) if isinstance(payload, bytes) else payload
            )
            enc_load = outer["load"]
            decrypted = master.loads(enc_load)
            nonce = decrypted["nonce"]
            reply = master.dumps({"n": self.call}, nonce=nonce)
            if self.call == 1:
                started.set()
                await gate.wait()
            events.append(f"send-end-{self.call}")
            return reply

    auth = _StubAuth(minion_opts, minion)
    transport = _OrderingTransport()
    channel = _make_channel(minion_opts, tmp_path, transport, auth)

    first = asyncio.create_task(channel._crypted_transfer({"cmd": "one"}, timeout=5))
    await started.wait()
    second = asyncio.create_task(channel._crypted_transfer({"cmd": "two"}, timeout=5))
    await asyncio.sleep(0)
    assert events == ["send-start-1"]
    gate.set()
    r1, r2 = await asyncio.gather(first, second)

    # With the lock, ordering must be: send-start-1, send-end-1,
    # send-start-2, send-end-2.  If the lock is missing, we'd see
    # send-start-1, send-start-2, send-end-1, send-end-2.
    assert events == [
        "send-start-1",
        "send-end-1",
        "send-start-2",
        "send-end-2",
    ], events
    assert r1 == {"n": 1}
    assert r2 == {"n": 2}


@pytest.mark.parametrize("crypt", ["clear", "aes"])
async def test_request_factory_uses_callers_loop(minion_opts, crypt):
    loop = asyncio.get_running_loop()
    with patch("salt.crypt.AsyncAuth") as auth, patch(
        "salt.transport.request_client"
    ) as transport:
        channel = salt.channel.client.AsyncReqChannel.factory(minion_opts, crypt=crypt)
        transport.assert_called_once_with(minion_opts, io_loop=loop)
        if crypt == "aes":
            auth.assert_called_once_with(minion_opts, io_loop=loop)
        else:
            auth.assert_not_called()
        channel.close()
    assert not loop.is_closed()


async def test_publish_factory_uses_callers_loop(minion_opts):
    loop = asyncio.get_running_loop()
    with patch("salt.crypt.AsyncAuth"), patch(
        "salt.transport.publish_client"
    ) as transport, patch("salt.utils.event.get_event"):
        channel = salt.channel.client.AsyncPubChannel.factory(minion_opts)
        assert channel.io_loop is loop
        assert transport.call_args.args[1] is loop
        channel.close()
    assert not loop.is_closed()


@pytest.mark.parametrize(
    "factory",
    [
        salt.channel.client.AsyncReqChannel.factory,
        salt.channel.client.AsyncPubChannel.factory,
    ],
)
@pytest.mark.parametrize("legacy", [False, True])
async def test_channel_factory_warns_only_for_tornado_loop(
    minion_opts, io_loop, factory, legacy
):
    loop = asyncio.get_running_loop()
    with patch("salt.crypt.AsyncAuth"), patch(
        "salt.transport.request_client"
    ) as request_client, patch(
        "salt.transport.publish_client"
    ) as publish_client, patch(
        "salt.utils.event.get_event"
    ):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", DeprecationWarning)
            channel = factory(
                minion_opts, io_loop=io_loop if legacy else loop, crypt="clear"
            )
        try:
            assert len(caught) == int(legacy)
            if legacy:
                assert "Passing a Tornado IOLoop" in str(caught[0].message)
                assert "removed in Salt 3009.2" in str(caught[0].message)
                assert caught[0].filename == __file__
            if request_client.called:
                assert request_client.call_args.kwargs["io_loop"] is loop
            else:
                assert publish_client.call_args.args[1] is loop
                assert channel.io_loop is loop
        finally:
            channel.close()
    assert not loop.is_closed()


async def test_publish_constructor_defaults_to_current_loop(minion_opts):
    with patch("salt.utils.event.get_event"):
        channel = salt.channel.client.AsyncPubChannel(
            minion_opts, MagicMock(), MagicMock()
        )
        try:
            assert channel.io_loop is asyncio.get_running_loop()
        finally:
            channel.close()


def test_sync_request_factory_supplies_native_loop(minion_opts):
    with patch("salt.transport.request_client") as transport:
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            channel = salt.channel.client.ReqChannel.factory(minion_opts, crypt="clear")
        try:
            assert transport.call_args.kwargs["io_loop"] is channel.asyncio_loop
        finally:
            channel.close()


async def test_cancelled_transfer_releases_channel(minion_opts, tmp_path):
    """Cancelling the active request must allow the next encrypted request to run."""
    key = salt.crypt.Crypticle.generate_key_string()
    crypticle = salt.crypt.Crypticle(minion_opts, key)
    started = asyncio.Event()
    calls = []

    async def send(payload, timeout=None):
        calls.append(payload)
        if len(calls) == 1:
            started.set()
            await asyncio.Event().wait()
        load = crypticle.loads(payload["load"])
        return crypticle.dumps({"result": "ok"}, nonce=load["nonce"])

    transport = MagicMock(send=send)
    channel = _make_channel(
        minion_opts, tmp_path, transport, _StubAuth(minion_opts, crypticle)
    )
    first = asyncio.create_task(channel._crypted_transfer({"cmd": "one"}, timeout=5))
    await started.wait()
    second = asyncio.create_task(channel._crypted_transfer({"cmd": "two"}, timeout=5))
    await asyncio.sleep(0)
    assert len(calls) == 1
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    assert await asyncio.wait_for(second, 1) == {"result": "ok"}
    assert len(calls) == 2


async def test_publish_async_context_closes_resources(minion_opts):
    with patch("salt.crypt.AsyncAuth"), patch(
        "salt.transport.publish_client"
    ) as transport, patch("salt.utils.event.get_event") as event:
        async with salt.channel.client.AsyncPubChannel.factory(minion_opts):
            transport.return_value.close.assert_not_called()
        transport.return_value.close.assert_called_once_with()
        event.return_value.destroy.assert_called_once_with()


async def test_publish_factory_failure_closes_transport(minion_opts):
    with patch("salt.crypt.AsyncAuth") as auth, patch(
        "salt.transport.publish_client"
    ) as transport:
        auth.return_value.gen_token.side_effect = salt.exceptions.InvalidKeyError(
            "bad key"
        )
        with pytest.raises(salt.exceptions.SaltClientError, match="bad key"):
            salt.channel.client.AsyncPubChannel.factory(minion_opts)
        transport.return_value.close.assert_called_once_with()


async def test_publish_factory_cleanup_does_not_mask_initialization_error(minion_opts):
    with patch("salt.crypt.AsyncAuth") as auth, patch(
        "salt.transport.publish_client"
    ) as transport:
        auth.return_value.gen_token.side_effect = salt.exceptions.InvalidKeyError(
            "original key failure"
        )
        transport.return_value.close.side_effect = OSError("cleanup failure")
        with pytest.raises(
            salt.exceptions.SaltClientError, match="original key failure"
        ):
            salt.channel.client.AsyncPubChannel.factory(minion_opts)
        transport.return_value.close.assert_called_once_with()


@pytest.mark.parametrize("reconnected", [False, True])
@pytest.mark.parametrize("failed", [False, True])
async def test_connected_event_does_not_gate_connection_callback(
    minion_opts, reconnected, failed
):
    release = asyncio.Event()
    started = asyncio.Event()
    publications = []

    async def publish():
        started.set()
        await release.wait()
        if failed:
            raise OSError("event publication failed")

    def fire_event(*args):
        publications.append(asyncio.create_task(publish()))
        return True

    with patch("salt.crypt.AsyncAuth"), patch("salt.transport.publish_client"), patch(
        "salt.utils.event.get_event"
    ) as event:
        channel = salt.channel.client.AsyncPubChannel.factory(minion_opts)
    channel.send_id = AsyncMock()
    channel._reconnected = reconnected
    event.return_value.fire_event.side_effect = fire_event
    event.return_value.fire_event_async = AsyncMock(side_effect=publish)
    request = MagicMock(send=AsyncMock())
    request.__aenter__ = AsyncMock(return_value=request)
    request.__aexit__ = AsyncMock(return_value=None)
    try:
        with patch("salt.channel.client.AsyncReqChannel.factory", return_value=request):
            await asyncio.wait_for(channel.connect_callback(True), 1)
        await asyncio.wait_for(started.wait(), 1)
        assert channel.connected
        assert channel._reconnected
        assert len(publications) == 1
        assert not publications[0].done()
        event.return_value.fire_event_async.assert_not_awaited()
        assert request.send.await_count == int(reconnected)
        release.set()
        results = await asyncio.gather(*publications, return_exceptions=True)
        if failed:
            assert isinstance(results[0], OSError)
        assert channel.connected
        assert channel._reconnected
    finally:
        release.set()
        await asyncio.gather(*publications, return_exceptions=True)
        channel.close()


@pytest.mark.parametrize("queued_cancel", [False, True])
async def test_request_lock_recovers_after_failure_or_queued_cancellation(
    minion_opts, tmp_path, queued_cancel
):
    key = salt.crypt.Crypticle.generate_key_string()
    crypticle = salt.crypt.Crypticle(minion_opts, key)
    entered = asyncio.Event()
    release = asyncio.Event()
    calls = []

    async def send(payload, timeout=None):
        calls.append(payload)
        if len(calls) == 1:
            entered.set()
            await release.wait()
            raise OSError("first request failed")
        load = crypticle.loads(payload["load"])
        return crypticle.dumps({"result": "ok"}, nonce=load["nonce"])

    channel = _make_channel(
        minion_opts, tmp_path, MagicMock(send=send), _StubAuth(minion_opts, crypticle)
    )
    first = asyncio.create_task(channel._crypted_transfer({"cmd": "one"}, timeout=1))
    second = None
    try:
        await asyncio.wait_for(entered.wait(), 1)
        second = asyncio.create_task(
            channel._crypted_transfer({"cmd": "two"}, timeout=1)
        )
        await asyncio.sleep(0)
        assert len(calls) == 1
        if queued_cancel:
            second.cancel()
            with pytest.raises(asyncio.CancelledError):
                await second
        release.set()
        with pytest.raises(OSError, match="first request failed"):
            await first
        if not queued_cancel:
            assert await asyncio.wait_for(second, 1) == {"result": "ok"}
        assert await asyncio.wait_for(
            channel._crypted_transfer({"cmd": "last"}, timeout=1), 1
        ) == {"result": "ok"}
    finally:
        release.set()
        for task in (first, second):
            if task is not None:
                task.cancel()
        await asyncio.gather(
            *(task for task in (first, second) if task is not None),
            return_exceptions=True,
        )
        channel.close()
