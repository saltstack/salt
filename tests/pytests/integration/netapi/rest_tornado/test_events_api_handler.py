import asyncio
from functools import partial

import pytest

from salt.netapi.rest_tornado import saltnado

# TODO: run all the same tests from the root handler, but for now since they are
# the same code, we'll just sanity check


@pytest.fixture
def app_urls():
    return [
        (r"/events", saltnado.EventsSaltAPIHandler),
    ]


@pytest.mark.slow_test
async def test_get(http_client, io_loop, app):
    events_fired = []

    def on_event(events_fired, event):
        if len(events_fired) < 6:
            event = event.decode("utf-8")
            app.event_listener.event.fire_event(
                {"foo": "bar", "baz": "qux"}, "salt/netapi/test"
            )
            events_fired.append(1)
            event = event.strip()
            # if we got a retry, just continue
            if event != "retry: 400":
                tag, data = event.splitlines()
                assert tag.startswith("tag: ")
                assert data.startswith("data: ")

    # We spawn the call here because otherwise the fetch method would
    # continue reading indefinitely and there would be no wait to
    # properly run the assertions or stop the request.
    io_loop.spawn_callback(
        http_client.fetch,
        "/events",
        streaming_callback=partial(on_event, events_fired),
        request_timeout=30,
    )

    while len(events_fired) < 5:
        await asyncio.sleep(1)

    assert len(events_fired) >= 5
