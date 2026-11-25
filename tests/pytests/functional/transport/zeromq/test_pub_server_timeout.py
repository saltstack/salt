"""
Functional regression tests for the zeromq transport's publish-timeout
behavior.  Companion to the ws-side tests at
``tests/pytests/functional/transport/ws/test_pub_server_timeout.py``.

Design note (scope of this file):

On 3008.x, ``salt.transport.zeromq.PublishServer.publish`` accepts
``**kwargs`` (so ``timeout=`` is silently dropped) and
``PublishServer.publish_payload`` does NOT accept ``timeout=`` at all
(positional / keyword signature is ``(payload, topic_list=None,
raw_payload=None)``).  The zeromq wire transport relies on libzmq's
own HWM/backpressure semantics rather than an asyncio ``wait_for``
wrap around the drain, so the ws-style ``timeout=`` kwarg is neither
needed nor implemented here.  The user-level invariant -- "one slow
subscriber must not block fan-out to other subscribers" -- is
delivered by libzmq's PUB socket semantics: the PUB socket drops
messages for slow SUB peers past HWM instead of blocking the
publisher.

Since the PR under review (#70939) is the ws companion to #70461, and
the zeromq transport is deliberately out of scope for the timeout
kwarg, this file only exercises the SIGNATURE and COMPAT invariants
that matter for callers that call ``publish(timeout=N)`` on a zeromq
``PublishServer`` (e.g. a shared event-bus caller that is unaware of
the wire transport type):

1. ``PublishServer.publish(payload, timeout=N)`` on zeromq must NOT
   raise ``TypeError`` -- the ``**kwargs`` accepts-and-drops contract
   is the shared public shape across transports.
2. ``PublishServer.publish_payload`` on zeromq does NOT accept
   ``timeout=`` (positive assertion that future code must not pass
   one without first widening the signature) -- this is the pin for
   the current zeromq contract on 3008.x.

Without-fix verification: the zeromq transport is NOT changed by this
PR, so there is no pre/post comparison to run.  These tests pin the
current contract so an accidental signature change on zeromq surfaces
as a test failure.
"""

import pytest

import salt.transport.zeromq

pytestmark = [
    pytest.mark.slow_test,
]


async def test_publish_accepts_timeout_kwarg_silently():
    """``PublishServer.publish(payload, timeout=N)`` on the zeromq
    transport accepts the kwarg via ``**kwargs``.  The kwarg is
    dropped (libzmq backpressure is the actual publisher-side
    semantic) but the call must not raise ``TypeError`` so a
    transport-agnostic caller (event bus, master reactor) can pass
    the same signature as the ws/tcp transports."""
    server = object.__new__(salt.transport.zeromq.PublishServer)
    sent = []

    class _StubSock:
        async def send(self, payload):
            sent.append(payload)

    server.sock = _StubSock()
    server.ctx = None
    # Must not raise TypeError for the `timeout=` kwarg.
    await server.publish(b"payload", timeout=3)
    assert sent == [b"payload"]


def test_publish_payload_signature_does_not_accept_timeout():
    """Pin the current zeromq ``PublishServer.publish_payload``
    signature: it accepts ``(payload, topic_list=None,
    raw_payload=None)`` and does NOT accept ``timeout=``.  If this
    changes (e.g. a future PR widens the signature to match ws/tcp),
    the assertion fails and the companion ws/tcp tests should be
    revisited to keep the three transports aligned.

    See the module docstring for the rationale on why zeromq is
    deliberately left without a ``timeout=`` kwarg on 3008.x."""
    import inspect

    sig = inspect.signature(salt.transport.zeromq.PublishServer.publish_payload)
    params = list(sig.parameters)
    assert "timeout" not in params, (
        f"zeromq PublishServer.publish_payload signature changed to "
        f"include `timeout`: {sig}.  Revisit the ws/tcp transport "
        f"tests and the companion #70461/#70938 pattern."
    )
    # The current pinned signature:
    assert params == ["self", "payload", "topic_list", "raw_payload"]
