from collections import defaultdict

import salt.netapi.rest_tornado.saltnado as saltnado_app
from salt.ext.tornado.concurrent import Future
from tests.support.mock import MagicMock


def _make_event_listener():
    """
    Build an EventListener without touching the real master event bus.
    """
    event_listener = saltnado_app.EventListener.__new__(saltnado_app.EventListener)
    event_listener.tag_map = defaultdict(list)
    event_listener.request_map = defaultdict(list)
    event_listener.timeout_map = {}
    event_listener.event = MagicMock()
    return event_listener


def test_handle_event_socket_recv_delivers_to_all_waiters():
    """
    A single matching event must resolve every future waiting on that tag.

    Regression test for #35798: the delivery loop used to remove futures from
    the very list it was iterating, skipping every other waiter so that only
    some websocket clients received the event.
    """
    event_listener = _make_event_listener()
    matcher = saltnado_app.EventListener.exact_matcher
    key = ("evt1", matcher)

    futures = [Future() for _ in range(4)]
    for future in futures:
        event_listener.tag_map[key].append(future)

    # event.unpack(raw) -> (mtag, data)
    event_listener.event.unpack.return_value = ("evt1", {"data": "foo"})

    event_listener._handle_event_socket_recv("raw")

    for future in futures:
        assert future.done()
        assert future.result() == {"data": {"data": "foo"}, "tag": "evt1"}

    # every delivered future should be removed from the tag_map list
    assert event_listener.tag_map[key] == []
