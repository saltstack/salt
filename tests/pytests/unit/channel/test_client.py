import pytest
import tornado.concurrent
import tornado.gen
import tornado.ioloop

import salt.channel.client
import salt.crypt
import salt.exceptions
import salt.payload


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


def test_async_pub_channel_key_overwritten_by_bad_data(minion_opts, tmp_path):
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
    salt.channel.client.AsyncPubChannel.factory(minion_opts, crypt="aes")

    # Now we need to overwrite the bad key with the new one. When gen_token
    # gets called a SaltClientError will ge traised
    key_path = tmp_path / "minion.pem"
    key_path.chmod(0o660)
    key_path.write_text(
        "asdfiosjaoiasdfjooaisjdfo902j0ianosdifn091091jw0edw09jcr89eq79vr"
    )
    with pytest.raises(salt.exceptions.SaltClientError):
        salt.channel.client.AsyncPubChannel.factory(minion_opts, crypt="aes")


@pytest.mark.asyncio
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

    @tornado.gen.coroutine
    def send(self, payload, timeout=None):  # pylint: disable=unused-argument
        self.sent.append(payload)
        raise tornado.gen.Return(self._replies.pop(0))


class _StubAuth:
    """Auth stub that owns a ``session_crypticle`` we can rotate mid-test."""

    def __init__(self, opts, session_crypticle):
        self.opts = opts
        self.session_crypticle = session_crypticle
        self.authenticated = True
        self.mpub = "master.pub"

    def gen_token(self, clear_tok):  # pragma: no cover - unused
        return b""

    @tornado.gen.coroutine
    def authenticate(self):  # pragma: no cover - unused
        raise tornado.gen.Return(None)


def _make_channel(minion_opts, tmp_path, transport, auth):
    minion_opts["pki_dir"] = str(tmp_path)
    minion_opts["id"] = "minion"
    minion_opts["master_uri"] = "tcp://127.0.0.1:4506"
    minion_opts.setdefault("minion_sign_messages", False)
    return salt.channel.client.AsyncReqChannel(
        minion_opts, transport, auth, timeout=1, tries=1
    )


def test_do_transfer_reauth_mid_flight_uses_same_crypticle(minion_opts, tmp_path):
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
        @tornado.gen.coroutine
        def send(self, payload, timeout=None):
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
            raise tornado.gen.Return(reply)

    minion_old = salt.crypt.Crypticle(minion_opts, old_key)
    minion_new = salt.crypt.Crypticle(minion_opts, new_key)
    auth = _StubAuth(minion_opts, minion_old)
    transport = _CapturingTransport([])

    channel = _make_channel(minion_opts, tmp_path, transport, auth)

    io_loop = tornado.ioloop.IOLoop()

    @tornado.gen.coroutine
    def _drive():
        # Simulate a concurrent re-auth: swap in a *new* session_crypticle
        # after the send path pinned the reference but before the reply
        # is decrypted.  With the fix, _do_transfer must use the pinned
        # (old) crypticle for both dumps and loads; without it, loads
        # would use the new one and raise AuthenticationError (HMAC).
        original_transport_send = transport.send

        @tornado.gen.coroutine
        def _rotate_and_send(payload, timeout=None):
            reply = yield original_transport_send(payload, timeout=timeout)
            # Rotate the auth mid-flight.
            auth.session_crypticle = minion_new
            raise tornado.gen.Return(reply)

        transport.send = _rotate_and_send
        result = yield channel._crypted_transfer({"cmd": "test"}, timeout=1)
        raise tornado.gen.Return(result)

    try:
        result = io_loop.run_sync(_drive)
    finally:
        io_loop.close(all_fds=True)

    assert result == {"result": "ok"}
    assert nonce_holder["nonce"]  # sanity: request had a nonce


def test_do_transfer_serialized_by_lock(minion_opts, tmp_path):
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
    # ``gate`` must be created inside the running io_loop; modern tornado's
    # ``Future`` binds to the currently-running asyncio event loop, which
    # only exists once ``run_sync`` has installed one.
    gate_holder = {}

    class _OrderingTransport(_StubTransport):
        def __init__(self):
            super().__init__([])
            self.call = 0

        @tornado.gen.coroutine
        def send(self, payload, timeout=None):
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
                # Suspend the first send until the second send starts
                # (would-be race) -- with the lock, the second send
                # cannot begin, so this future is completed by the test
                # driver after a small delay via io_loop.call_later.
                yield gate_holder["gate"]
            events.append(f"send-end-{self.call}")
            raise tornado.gen.Return(reply)

    auth = _StubAuth(minion_opts, minion)
    transport = _OrderingTransport()
    channel = _make_channel(minion_opts, tmp_path, transport, auth)

    io_loop = tornado.ioloop.IOLoop()

    @tornado.gen.coroutine
    def _drive():
        # Fire both transfers "concurrently".  Under the lock, transfer2
        # must wait for transfer1 to fully finish (including decrypt)
        # before its send even begins.
        gate_holder["gate"] = tornado.concurrent.Future()
        fut1 = channel._crypted_transfer({"cmd": "one"}, timeout=5)
        fut2 = channel._crypted_transfer({"cmd": "two"}, timeout=5)

        def _release():
            gate = gate_holder["gate"]
            if not gate.done():
                gate.set_result(None)

        io_loop.call_later(0.05, _release)
        r1 = yield fut1
        r2 = yield fut2
        raise tornado.gen.Return((r1, r2))

    try:
        r1, r2 = io_loop.run_sync(_drive)
    finally:
        io_loop.close(all_fds=True)

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
