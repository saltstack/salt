import asyncio
import logging

import pytest

import salt.utils.event
from salt.netapi.rest_tornado import saltnado
from tests.support.events import eventpublisher_process

log = logging.getLogger(__name__)


def _check_skip(grains):
    if grains["os"] == "MacOS":
        return True
    return False


pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_initial_gh_actions_failure(skip=_check_skip),
]


class Request:
    __slots__ = ("_finished",)

    def __init__(self):
        self._finished = True


@pytest.fixture
def sock_dir(tmp_path):
    yield str(tmp_path)


async def test_simple(sock_dir):
    """
    Test getting a few events
    """
    with eventpublisher_process(sock_dir):
        with salt.utils.event.MasterEvent(sock_dir) as me:
            request = Request()
            event_listener = saltnado.EventListener(
                {},  # we don't use mod_opts, don't save?
                {"sock_dir": sock_dir, "transport": "zeromq"},
            )
            await asyncio.sleep(1)
            event_future = event_listener.get_event(
                request, "evt1"
            )  # get an event future
            me.fire_event({"data": "foo2"}, "evt2")  # fire an event we don't want
            me.fire_event({"data": "foo1"}, "evt1")  # fire an event we do want

            await event_future  # wait for the future

            # check that we got the event we wanted
            assert event_future.done()
            assert event_future.result()["tag"] == "evt1"
            assert event_future.result()["data"]["data"] == "foo1"


async def test_set_event_handler(sock_dir):
    """
    Test subscribing events using set_event_handler
    """
    with eventpublisher_process(sock_dir):
        with salt.utils.event.MasterEvent(sock_dir) as me:
            request = Request()
            event_listener = saltnado.EventListener(
                {},  # we don't use mod_opts, don't save?
                {"sock_dir": sock_dir, "transport": "zeromq"},
            )
            await asyncio.sleep(1)
            event_future = event_listener.get_event(
                request,
                tag="evt",
                timeout=1,
            )  # get an event future
            me.fire_event({"data": "foo"}, "evt")  # fire an event we do want

            await event_future  # wait for the future

            # check that we subscribed the event we wanted
            assert len(event_listener.timeout_map) == 0


async def test_timeout(sock_dir):
    """
    Make sure timeouts work correctly
    """
    with eventpublisher_process(sock_dir):
        request = Request()
        event_listener = saltnado.EventListener(
            {},  # we don't use mod_opts, don't save?
            {"sock_dir": sock_dir, "transport": "zeromq"},
        )
        await asyncio.sleep(1)
        event_future = event_listener.get_event(
            request,
            tag="evt1",
            timeout=1,
        )  # get an event future

        with pytest.raises(saltnado.TimeoutException):
            await event_future  # wait for the future

        assert event_future.done()


async def test_clean_by_request(sock_dir, io_loop):
    """
    Make sure the method clean_by_request clean up every related data in EventListener
    request_future_1 : will be timeout-ed by clean_by_request(request1)
    request_future_2 : will be finished by me.fire_event and awaiting for it ...
    request_future_3 : will be finished by me.fire_event and awaiting for it ...
    request_future_4 : will be timeout-ed by clean-by_request(request2)
    """

    with eventpublisher_process(sock_dir):
        log.info("After event pubserver start")
        with salt.utils.event.MasterEvent(sock_dir) as me:
            log.info("After master event start %r", me)
            request1 = Request()
            request2 = Request()
            event_listener = saltnado.EventListener(
                {},  # we don't use mod_opts, don't save?
                {"sock_dir": sock_dir, "transport": "zeromq"},
            )
            await asyncio.sleep(1)

            assert 0 == len(event_listener.tag_map)
            assert 0 == len(event_listener.request_map)

            request_future_1 = event_listener.get_event(request1, tag="evt1")
            request_future_2 = event_listener.get_event(request1, tag="evt2")
            dummy_request_future_1 = event_listener.get_event(request2, tag="evt3")
            dummy_request_future_2 = event_listener.get_event(
                request2, timeout=10, tag="evt4"
            )

            assert 4 == len(event_listener.tag_map)
            assert 2 == len(event_listener.request_map)

            me.fire_event({"data": "foo2"}, "evt2")
            me.fire_event({"data": "foo3"}, "evt3")

            await request_future_2
            await dummy_request_future_1

            event_listener.clean_by_request(request1)
            me.fire_event({"data": "foo1"}, "evt1")

            assert request_future_1.done()
            with pytest.raises(saltnado.TimeoutException):
                request_future_1.result()

            assert request_future_2.done()
            assert request_future_2.result()["tag"] == "evt2"
            assert request_future_2.result()["data"]["data"] == "foo2"

            assert dummy_request_future_1.done()
            assert dummy_request_future_1.result()["tag"] == "evt3"
            assert dummy_request_future_1.result()["data"]["data"] == "foo3"

            assert not dummy_request_future_2.done()

            assert 2 == len(event_listener.tag_map)
            assert 1 == len(event_listener.request_map)

            event_listener.clean_by_request(request2)

            with pytest.raises(saltnado.TimeoutException):
                dummy_request_future_2.result()

            assert 0 == len(event_listener.tag_map)
            assert 0 == len(event_listener.request_map)
