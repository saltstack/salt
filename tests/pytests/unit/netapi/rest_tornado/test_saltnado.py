import pytest

import salt.ext.tornado
import salt.ext.tornado.gen
import salt.netapi.rest_tornado.saltnado as saltnado
from tests.support.mock import patch

# The legacy suite ran under tornado's gen_test decorator, which enforced a
# per-test deadline; io_loop.run_sync has none by default, and the harness
# fallback timeout is not applied on Windows. Keep every coroutine bounded.
RUN_SYNC_TIMEOUT = 30


# ----- TestJobNotRunning ------------------------------------------------------------------------------------------->
@pytest.fixture
def job_not_running_handler(salt_api_handler):
    handler = salt_api_handler
    handler._write_buffer = []
    handler._transforms = []
    handler.lowstate = []
    handler.content_type = "text/plain"
    handler.dumper = lambda x: x
    f = salt.ext.tornado.gen.Future()
    f.set_result({"jid": f, "minions": []})
    handler.saltclients.update({"local": lambda *args, **kwargs: f})
    return handler


def test_when_disbatch_has_already_finished_then_writing_return_should_not_fail(
    io_loop, job_not_running_handler
):
    handler = job_not_running_handler
    handler.finish()
    buffered = list(handler._write_buffer)
    io_loop.run_sync(handler.disbatch, timeout=RUN_SYNC_TIMEOUT)
    # disbatch on a finished handler must not raise, and must not write
    # anything more into the response buffer.
    assert handler._write_buffer == buffered


def test_when_disbatch_has_already_finished_then_finishing_should_not_fail(
    io_loop, job_not_running_handler
):
    handler = job_not_running_handler
    handler.finish()
    io_loop.run_sync(handler.disbatch, timeout=RUN_SYNC_TIMEOUT)
    # No assertion necessary, because we just want no failure here.
    # Asserting that it doesn't raise anything is... the default behavior
    # for a test.


def test_when_event_times_out_and_minion_is_not_running_result_should_be_True(
    io_loop, job_not_running_handler
):
    handler = job_not_running_handler
    fut = salt.ext.tornado.gen.Future()
    fut.set_exception(saltnado.TimeoutException())
    handler.application.event_listener.get_event.return_value = fut
    wrong_future = salt.ext.tornado.gen.Future()

    result = io_loop.run_sync(
        lambda: handler.job_not_running(
            jid=42, tgt="*", tgt_type="glob", minions=[], is_finished=wrong_future
        ),
        timeout=RUN_SYNC_TIMEOUT,
    )

    assert result


def test_when_event_times_out_and_minion_is_not_running_minion_data_should_not_be_set(
    io_loop, job_not_running_handler
):
    handler = job_not_running_handler
    fut = salt.ext.tornado.gen.Future()
    fut.set_exception(saltnado.TimeoutException())
    handler.application.event_listener.get_event.return_value = fut
    wrong_future = salt.ext.tornado.gen.Future()
    minions = {}

    io_loop.run_sync(
        lambda: handler.job_not_running(
            jid=42, tgt="*", tgt_type="glob", minions=minions, is_finished=wrong_future
        ),
        timeout=RUN_SYNC_TIMEOUT,
    )

    assert not minions


def test_when_event_finally_finishes_and_returned_minion_not_in_minions_it_should_be_set_to_False(
    io_loop, job_not_running_handler
):
    handler = job_not_running_handler
    expected_id = 42
    no_data_event = salt.ext.tornado.gen.Future()
    no_data_event.set_result({"data": {}})
    empty_return_event = salt.ext.tornado.gen.Future()
    empty_return_event.set_result({"data": {"return": {}}})
    actual_return_event = salt.ext.tornado.gen.Future()
    actual_return_event.set_result(
        {"data": {"return": {"something happened here": "OK?"}, "id": expected_id}}
    )
    timed_out_event = salt.ext.tornado.gen.Future()
    timed_out_event.set_exception(saltnado.TimeoutException())
    handler.application.event_listener.get_event.side_effect = [
        no_data_event,
        empty_return_event,
        actual_return_event,
        timed_out_event,
        timed_out_event,
    ]
    minions = {}

    io_loop.run_sync(
        lambda: handler.job_not_running(
            jid=99,
            tgt="*",
            tgt_type="fnord",
            minions=minions,
            is_finished=salt.ext.tornado.gen.Future(),
        ),
        timeout=RUN_SYNC_TIMEOUT,
    )

    assert not minions[expected_id]


def test_when_event_finally_finishes_and_returned_minion_already_in_minions_it_should_not_be_changed(
    io_loop, job_not_running_handler
):
    handler = job_not_running_handler
    expected_id = 42
    expected_value = object()
    minions = {expected_id: expected_value}
    no_data_event = salt.ext.tornado.gen.Future()
    no_data_event.set_result({"data": {}})
    empty_return_event = salt.ext.tornado.gen.Future()
    empty_return_event.set_result({"data": {"return": {}}})
    actual_return_event = salt.ext.tornado.gen.Future()
    actual_return_event.set_result(
        {"data": {"return": {"something happened here": "OK?"}, "id": expected_id}}
    )
    timed_out_event = salt.ext.tornado.gen.Future()
    timed_out_event.set_exception(saltnado.TimeoutException())
    handler.application.event_listener.get_event.side_effect = [
        no_data_event,
        empty_return_event,
        actual_return_event,
        timed_out_event,
        timed_out_event,
    ]

    io_loop.run_sync(
        lambda: handler.job_not_running(
            jid=99,
            tgt="*",
            tgt_type="fnord",
            minions=minions,
            is_finished=salt.ext.tornado.gen.Future(),
        ),
        timeout=RUN_SYNC_TIMEOUT,
    )

    assert minions[expected_id] is expected_value


def test_when_event_returns_early_and_finally_times_out_result_should_be_True(
    io_loop, job_not_running_handler
):
    handler = job_not_running_handler
    no_data_event = salt.ext.tornado.gen.Future()
    no_data_event.set_result({"data": {}})
    empty_return_event = salt.ext.tornado.gen.Future()
    empty_return_event.set_result({"data": {"return": {}}})
    actual_return_event = salt.ext.tornado.gen.Future()
    actual_return_event.set_result(
        {"data": {"return": {"something happened here": "OK?"}, "id": "fnord"}}
    )
    timed_out_event = salt.ext.tornado.gen.Future()
    timed_out_event.set_exception(saltnado.TimeoutException())
    handler.application.event_listener.get_event.side_effect = [
        no_data_event,
        empty_return_event,
        actual_return_event,
        timed_out_event,
        timed_out_event,
    ]

    result = io_loop.run_sync(
        lambda: handler.job_not_running(
            jid=99,
            tgt="*",
            tgt_type="fnord",
            minions={},
            is_finished=salt.ext.tornado.gen.Future(),
        ),
        timeout=RUN_SYNC_TIMEOUT,
    )
    assert result


def test_when_event_finishes_but_is_finished_is_done_then_result_should_be_True(
    io_loop, job_not_running_handler
):
    handler = job_not_running_handler
    expected_minion_id = "fnord"
    expected_minion_value = object()
    no_data_event = salt.ext.tornado.gen.Future()
    no_data_event.set_result({"data": {}})
    empty_return_event = salt.ext.tornado.gen.Future()
    empty_return_event.set_result({"data": {"return": {}}})
    actual_return_event = salt.ext.tornado.gen.Future()
    actual_return_event.set_result(
        {
            "data": {
                "return": {"something happened here": "OK?"},
                "id": expected_minion_id,
            }
        }
    )
    is_finished = salt.ext.tornado.gen.Future()

    def abort(*args, **kwargs):
        yield actual_return_event
        f = salt.ext.tornado.gen.Future()
        f.set_exception(saltnado.TimeoutException())
        is_finished.set_result("This is done")
        yield f
        assert False, "Never should make it here"

    minions = {expected_minion_id: expected_minion_value}

    handler.application.event_listener.get_event.side_effect = (x for x in abort())

    result = io_loop.run_sync(
        lambda: handler.job_not_running(
            jid=99,
            tgt="*",
            tgt_type="fnord",
            minions=minions,
            is_finished=is_finished,
        ),
        timeout=RUN_SYNC_TIMEOUT,
    )
    assert result

    # These are failsafes to ensure nothing super sideways happened
    assert len(minions) == 1, str(minions)
    assert minions[expected_minion_id] is expected_minion_value


def test_when_is_finished_times_out_before_event_finishes_result_should_be_True(
    io_loop, job_not_running_handler
):
    handler = job_not_running_handler
    # Other test times out with event - this one should time out for is_finished
    finished = salt.ext.tornado.gen.Future()
    finished.set_exception(saltnado.TimeoutException())
    wrong_future = salt.ext.tornado.gen.Future()
    handler.application.event_listener.get_event.return_value = wrong_future

    result = io_loop.run_sync(
        lambda: handler.job_not_running(
            jid=42, tgt="*", tgt_type="glob", minions=[], is_finished=finished
        ),
        timeout=RUN_SYNC_TIMEOUT,
    )

    assert result


def test_when_is_finished_times_out_before_event_finishes_event_should_have_result_set_to_None(
    io_loop, job_not_running_handler
):
    handler = job_not_running_handler
    finished = salt.ext.tornado.gen.Future()
    finished.set_exception(saltnado.TimeoutException())
    wrong_future = salt.ext.tornado.gen.Future()
    handler.application.event_listener.get_event.return_value = wrong_future

    io_loop.run_sync(
        lambda: handler.job_not_running(
            jid=42, tgt="*", tgt_type="glob", minions=[], is_finished=finished
        ),
        timeout=RUN_SYNC_TIMEOUT,
    )

    assert wrong_future.result() is None


# <----- TestJobNotRunning -------------------------------------------------------------------------------------------


# ----- TestGetMinionReturns ---------------------------------------------------------------------------------------->
def test_if_finished_before_any_events_return_then_result_should_be_empty_dictionary(
    io_loop, salt_api_handler
):
    handler = salt_api_handler
    expected_result = {}
    xxx = salt.ext.tornado.gen.Future()
    xxx.set_result(None)
    is_finished = salt.ext.tornado.gen.Future()
    is_finished.set_result(None)
    actual_result = io_loop.run_sync(
        lambda: handler.get_minion_returns(
            events=[],
            is_finished=is_finished,
            is_timed_out=salt.ext.tornado.gen.Future(),
            min_wait_time=xxx,
            minions={},
        ),
        timeout=RUN_SYNC_TIMEOUT,
    )
    assert actual_result == expected_result


# TODO: Copy above - test with timed out -W. Werner, 2020-11-05


def test_if_is_finished_after_events_return_then_result_should_contain_event_result_data(
    io_loop, salt_api_handler
):
    handler = salt_api_handler
    expected_result = {
        "minion1": {"fnord": "this is some fnordish data"},
        "minion2": {"fnord": "this is some other fnordish data"},
    }
    xxx = salt.ext.tornado.gen.Future()
    xxx.set_result(None)
    is_finished = salt.ext.tornado.gen.Future()
    # XXX what do I do here?
    events = [
        salt.ext.tornado.gen.Future(),
        salt.ext.tornado.gen.Future(),
        salt.ext.tornado.gen.Future(),
        salt.ext.tornado.gen.Future(),
    ]
    events[0].set_result(
        {
            "tag": "fnord",
            "data": {"id": "minion1", "return": expected_result["minion1"]},
        }
    )
    events[1].set_result(
        {
            "tag": "fnord",
            "data": {"id": "minion2", "return": expected_result["minion2"]},
        }
    )
    io_loop.call_later(0.2, lambda: is_finished.set_result(None))

    actual_result = io_loop.run_sync(
        lambda: handler.get_minion_returns(
            events=events,
            is_finished=is_finished,
            is_timed_out=salt.ext.tornado.gen.Future(),
            min_wait_time=xxx,
            minions={
                "minion1": False,
                "minion2": False,
                "never returning minion": False,
            },
        ),
        timeout=RUN_SYNC_TIMEOUT,
    )

    assert actual_result == expected_result


def test_if_timed_out_after_events_return_then_result_should_contain_event_result_data(
    io_loop, salt_api_handler
):
    handler = salt_api_handler
    expected_result = {
        "minion1": {"fnord": "this is some fnordish data"},
        "minion2": {"fnord": "this is some other fnordish data"},
    }
    xxx = salt.ext.tornado.gen.Future()
    xxx.set_result(None)
    is_timed_out = salt.ext.tornado.gen.Future()
    # XXX what do I do here?
    events = [
        salt.ext.tornado.gen.Future(),
        salt.ext.tornado.gen.Future(),
        salt.ext.tornado.gen.Future(),
        salt.ext.tornado.gen.Future(),
    ]
    events[0].set_result(
        {
            "tag": "fnord",
            "data": {"id": "minion1", "return": expected_result["minion1"]},
        }
    )
    events[1].set_result(
        {
            "tag": "fnord",
            "data": {"id": "minion2", "return": expected_result["minion2"]},
        }
    )
    io_loop.call_later(0.2, lambda: is_timed_out.set_result(None))

    actual_result = io_loop.run_sync(
        lambda: handler.get_minion_returns(
            events=events,
            is_finished=salt.ext.tornado.gen.Future(),
            is_timed_out=is_timed_out,
            min_wait_time=xxx,
            minions={
                "minion1": False,
                "minion2": False,
                "never returning minion": False,
            },
        ),
        timeout=RUN_SYNC_TIMEOUT,
    )

    assert actual_result == expected_result


def test_if_wait_timer_is_not_done_even_though_results_are_then_data_should_not_yet_be_returned(
    io_loop, salt_api_handler
):
    handler = salt_api_handler
    expected_result = {
        "one": {"fnordy one": "one has some data"},
        "two": {"fnordy two": "two has some data"},
    }
    events = [salt.ext.tornado.gen.Future(), salt.ext.tornado.gen.Future()]
    events[0].set_result(
        {"tag": "fnord", "data": {"id": "one", "return": expected_result["one"]}}
    )
    events[1].set_result(
        {"tag": "fnord", "data": {"id": "two", "return": expected_result["two"]}}
    )
    wait_timer = salt.ext.tornado.gen.Future()

    @salt.ext.tornado.gen.coroutine
    def run():
        fut = handler.get_minion_returns(
            events=events,
            is_finished=salt.ext.tornado.gen.Future(),
            is_timed_out=salt.ext.tornado.gen.Future(),
            min_wait_time=wait_timer,
            minions={"one": False, "two": False},
        )

        yield salt.ext.tornado.gen.sleep(0.1)

        assert not fut.done()

        wait_timer.set_result(None)
        actual_result = yield fut
        raise salt.ext.tornado.gen.Return(actual_result)

    actual_result = io_loop.run_sync(run, timeout=RUN_SYNC_TIMEOUT)

    assert actual_result == expected_result


def test_when_is_finished_any_other_futures_should_be_canceled(
    io_loop, salt_api_handler
):
    handler = salt_api_handler
    events = [
        salt.ext.tornado.gen.Future(),
        salt.ext.tornado.gen.Future(),
        salt.ext.tornado.gen.Future(),
        salt.ext.tornado.gen.Future(),
        salt.ext.tornado.gen.Future(),
    ]

    is_finished = salt.ext.tornado.gen.Future()
    is_finished.set_result(None)
    io_loop.run_sync(
        lambda: handler.get_minion_returns(
            events=events,
            is_finished=is_finished,
            is_timed_out=salt.ext.tornado.gen.Future(),
            min_wait_time=salt.ext.tornado.gen.Future(),
            minions={"one": False, "two": False},
        ),
        timeout=RUN_SYNC_TIMEOUT,
    )

    are_done = [event.done() for event in events]
    assert all(are_done)


def test_when_an_event_times_out_then_we_should_not_enter_an_infinite_loop(
    io_loop, salt_api_handler
):
    handler = salt_api_handler
    # NOTE: this test will enter an infinite loop if the code is broken. I
    # was not able to figure out a way to ensure that the test exits with
    # failure rather than stalling forever. That is because the
    # TimeoutException happens first and then tornado will never yield
    # control to another coroutine. Like a coroutine to remove the future
    # with the TimeoutException. It is also not possible to clear the
    # TimeoutException.

    events = [
        salt.ext.tornado.gen.Future(),
        salt.ext.tornado.gen.Future(),
        salt.ext.tornado.gen.Future(),
        salt.ext.tornado.gen.Future(),
        salt.ext.tornado.gen.Future(),
    ]

    # Arguably any event would work, but 3 isn't the first, so it
    # gives us a little more confidence that this test is testing
    # correctly
    events[3].set_exception(saltnado.TimeoutException())
    times_out_later = salt.ext.tornado.gen.Future()
    # 0.5s should be long enough that the test gets through doing other
    # things before hitting this timeout, which will cancel all the
    # in-flight futures.
    io_loop.call_later(0.5, lambda: times_out_later.set_result(None))
    io_loop.run_sync(
        lambda: handler.get_minion_returns(
            events=events,
            is_finished=salt.ext.tornado.gen.Future(),
            is_timed_out=times_out_later,
            min_wait_time=salt.ext.tornado.gen.Future(),
            minions={"one": False, "two": False},
        ),
        timeout=RUN_SYNC_TIMEOUT,
    )

    # Technically we don't /need/ to check that all events are done,
    # but it's incorrect to exit the function without ensuring all
    # futures are canceled.
    are_done = [event.done() for event in events]
    assert all(are_done)
    assert times_out_later.done()


def test_when_is_timed_out_any_other_futures_should_be_canceled(
    io_loop, salt_api_handler
):
    handler = salt_api_handler
    # There is some question about whether this test is or should be
    # necessary. Or if it's meaningful. The code that this is testing
    # should never actually be able to make it to this point -- because
    # when all events have completed it should exit at a different branch.
    # That being said, the worst case is that this is just a duplicate
    # or irrelevant test, and can be removed.
    events = [
        salt.ext.tornado.gen.Future(),
        salt.ext.tornado.gen.Future(),
        salt.ext.tornado.gen.Future(),
        salt.ext.tornado.gen.Future(),
        salt.ext.tornado.gen.Future(),
    ]

    is_timed_out = salt.ext.tornado.gen.Future()
    is_timed_out.set_result(None)
    io_loop.run_sync(
        lambda: handler.get_minion_returns(
            events=events,
            is_finished=salt.ext.tornado.gen.Future(),
            is_timed_out=is_timed_out,
            min_wait_time=salt.ext.tornado.gen.Future(),
            minions={"one": False, "two": False},
        ),
        timeout=RUN_SYNC_TIMEOUT,
    )

    are_done = [event.done() for event in events]
    assert all(are_done)


def test_when_min_wait_time_and_nothing_todo_any_other_futures_should_be_canceled(
    io_loop, salt_api_handler
):
    handler = salt_api_handler
    events = [
        salt.ext.tornado.gen.Future(),
        salt.ext.tornado.gen.Future(),
        salt.ext.tornado.gen.Future(),
        salt.ext.tornado.gen.Future(),
        salt.ext.tornado.gen.Future(),
    ]

    is_finished = salt.ext.tornado.gen.Future()
    min_wait_time = salt.ext.tornado.gen.Future()
    io_loop.call_later(0.2, lambda: min_wait_time.set_result(None))

    io_loop.run_sync(
        lambda: handler.get_minion_returns(
            events=events,
            is_finished=is_finished,
            is_timed_out=salt.ext.tornado.gen.Future(),
            min_wait_time=min_wait_time,
            minions={"one": True, "two": True},
        ),
        timeout=RUN_SYNC_TIMEOUT,
    )

    are_done = [event.done() for event in events] + [is_finished.done()]
    assert all(are_done)


def test_when_is_finished_but_not_is_timed_out_then_timed_out_should_not_be_set_to_done(
    io_loop, salt_api_handler
):
    handler = salt_api_handler
    events = [salt.ext.tornado.gen.Future()]
    is_timed_out = salt.ext.tornado.gen.Future()
    is_finished = salt.ext.tornado.gen.Future()
    is_finished.set_result(None)

    io_loop.run_sync(
        lambda: handler.get_minion_returns(
            events=events,
            is_finished=is_finished,
            is_timed_out=is_timed_out,
            min_wait_time=salt.ext.tornado.gen.Future(),
            minions={"one": False, "two": False},
        ),
        timeout=RUN_SYNC_TIMEOUT,
    )

    assert not is_timed_out.done()


def test_when_min_wait_time_and_all_completed_but_not_is_timed_out_then_timed_out_should_not_be_set_to_done(
    io_loop, salt_api_handler
):
    handler = salt_api_handler
    events = [salt.ext.tornado.gen.Future()]
    is_timed_out = salt.ext.tornado.gen.Future()
    min_wait_time = salt.ext.tornado.gen.Future()
    io_loop.call_later(0.2, lambda: min_wait_time.set_result(None))

    io_loop.run_sync(
        lambda: handler.get_minion_returns(
            events=events,
            is_finished=salt.ext.tornado.gen.Future(),
            is_timed_out=is_timed_out,
            min_wait_time=min_wait_time,
            minions={"one": True},
        ),
        timeout=RUN_SYNC_TIMEOUT,
    )

    assert not is_timed_out.done()


def test_when_things_are_completed_but_not_timed_out_then_timed_out_event_should_not_be_done(
    io_loop, salt_api_handler
):
    handler = salt_api_handler
    events = [
        salt.ext.tornado.gen.Future(),
    ]
    events[0].set_result({"tag": "fnord", "data": {"id": "one", "return": {}}})
    min_wait_time = salt.ext.tornado.gen.Future()
    min_wait_time.set_result(None)
    is_timed_out = salt.ext.tornado.gen.Future()

    io_loop.run_sync(
        lambda: handler.get_minion_returns(
            events=events,
            is_finished=salt.ext.tornado.gen.Future(),
            is_timed_out=is_timed_out,
            min_wait_time=min_wait_time,
            minions={"one": True},
        ),
        timeout=RUN_SYNC_TIMEOUT,
    )

    assert not is_timed_out.done()


# <----- TestGetMinionReturns ----------------------------------------------------------------------------------------


# ----- TestDisbatchLocal ------------------------------------------------------------------------------------------->
def test_when_is_timed_out_is_set_before_other_events_are_completed_then_result_should_be_empty_dictionary(
    io_loop, salt_api_handler
):
    handler = salt_api_handler
    completed_event = salt.ext.tornado.gen.Future()
    never_completed = salt.ext.tornado.gen.Future()
    # Route the gather timeout through a fake sleep that is already timed
    # out, so the ordering this test asserts (timeout strictly before any
    # event completes) is deterministic instead of racing two real timers.
    fakeo_timer = object()
    timed_out = salt.ext.tornado.gen.Future()
    timed_out.set_result(None)
    orig_sleep = salt.ext.tornado.gen.sleep

    def fake_sleep(timer):
        if timer is fakeo_timer:
            return timed_out
        return orig_sleep(timer)

    def fancy_get_event(*args, **kwargs):
        if kwargs.get("tag").endswith("/ret"):
            return never_completed
        return completed_event

    f = salt.ext.tornado.gen.Future()
    f.set_result({"jid": "42", "minions": []})
    with patch.object(
        handler.application.event_listener,
        "get_event",
        side_effect=fancy_get_event,
    ), patch(
        "salt.ext.tornado.gen.sleep",
        autospec=True,
        side_effect=fake_sleep,
    ), patch.dict(
        handler.application.opts,
        {"gather_job_timeout": fakeo_timer, "timeout": 42},
    ), patch.dict(
        handler.saltclients, {"local": lambda *args, **kwargs: f}
    ):
        result = io_loop.run_sync(
            lambda: handler._disbatch_local(
                chunk={"tgt": "*", "tgt_type": "glob", "fun": "test.ping"}
            ),
            timeout=RUN_SYNC_TIMEOUT,
        )

    assert result == {}


def test_when_is_finished_is_set_before_events_return_then_no_data_should_be_returned(
    io_loop, salt_api_handler
):
    handler = salt_api_handler
    completed_event = salt.ext.tornado.gen.Future()
    never_completed = salt.ext.tornado.gen.Future()
    gather_timeout = 2
    event_timeout = gather_timeout - 1

    def fancy_get_event(*args, **kwargs):
        if kwargs.get("tag").endswith("/ret"):
            return never_completed
        return completed_event

    def completer():
        completed_event.set_result(
            {
                "tag": "fnord",
                "data": {
                    "return": "This should never be in chunk_ret",
                    "id": "fnord",
                },
            }
        )

    io_loop.call_later(event_timeout, completer)

    def toggle_is_finished(*args, **kwargs):
        finished = kwargs.get("is_finished", args[4] if len(args) > 4 else None)
        assert finished is not None
        finished.set_result(42)

    f = salt.ext.tornado.gen.Future()
    f.set_result({"jid": "42", "minions": []})
    with patch.object(
        handler.application.event_listener,
        "get_event",
        side_effect=fancy_get_event,
    ), patch.object(
        handler,
        "job_not_running",
        autospec=True,
        side_effect=toggle_is_finished,
    ), patch.dict(
        handler.application.opts,
        {"gather_job_timeout": gather_timeout, "timeout": 42},
    ), patch.dict(
        handler.saltclients, {"local": lambda *args, **kwargs: f}
    ):
        result = io_loop.run_sync(
            lambda: handler._disbatch_local(
                chunk={"tgt": "*", "tgt_type": "glob", "fun": "test.ping"}
            ),
            timeout=RUN_SYNC_TIMEOUT,
        )

    assert result == {}


def test_when_is_finished_then_all_collected_data_should_be_returned(
    io_loop, salt_api_handler
):
    handler = salt_api_handler
    completed_event = salt.ext.tornado.gen.Future()
    never_completed = salt.ext.tornado.gen.Future()
    # This timeout should never be reached
    gather_timeout = 42
    completed_events = [salt.ext.tornado.gen.Future() for _ in range(5)]
    for i, event in enumerate(completed_events):
        event.set_result(
            {
                "tag": "fnord",
                "data": {
                    "return": f"return from fnord {i}",
                    "id": f"fnord {i}",
                },
            }
        )
    uncompleted_events = [salt.ext.tornado.gen.Future() for _ in range(5)]
    events = iter(completed_events + uncompleted_events)
    expected_result = {
        "fnord 0": "return from fnord 0",
        "fnord 1": "return from fnord 1",
        "fnord 2": "return from fnord 2",
        "fnord 3": "return from fnord 3",
        "fnord 4": "return from fnord 4",
    }

    def fancy_get_event(*args, **kwargs):
        if kwargs.get("tag").endswith("/ret"):
            return never_completed
        else:
            return next(events)

    def toggle_is_finished(*args, **kwargs):
        finished = kwargs.get("is_finished", args[4] if len(args) > 4 else None)
        assert finished is not None
        finished.set_result(42)

    f = salt.ext.tornado.gen.Future()
    f.set_result({"jid": "42", "minions": ["non-existent minion"]})
    with patch.object(
        handler.application.event_listener,
        "get_event",
        side_effect=fancy_get_event,
    ), patch.object(
        handler,
        "job_not_running",
        autospec=True,
        side_effect=toggle_is_finished,
    ), patch.dict(
        handler.application.opts,
        {"gather_job_timeout": gather_timeout, "timeout": 42},
    ), patch.dict(
        handler.saltclients, {"local": lambda *args, **kwargs: f}
    ):
        result = io_loop.run_sync(
            lambda: handler._disbatch_local(
                chunk={"tgt": "*", "tgt_type": "glob", "fun": "test.ping"}
            ),
            timeout=RUN_SYNC_TIMEOUT,
        )

    assert result == expected_result


def test_when_is_timed_out_then_all_collected_data_should_be_returned(
    io_loop, salt_api_handler
):
    handler = salt_api_handler
    completed_event = salt.ext.tornado.gen.Future()
    never_completed = salt.ext.tornado.gen.Future()
    # Route the gather timeout through a fake sleep that is already timed
    # out. The completed events still win each wait round (their callbacks
    # are scheduled first), so all collected data is returned and the test
    # no longer needs a real 2 second timer.
    fakeo_timer = object()
    timed_out = salt.ext.tornado.gen.Future()
    timed_out.set_result(None)
    orig_sleep = salt.ext.tornado.gen.sleep

    def fake_sleep(timer):
        if timer is fakeo_timer:
            return timed_out
        return orig_sleep(timer)

    completed_events = [salt.ext.tornado.gen.Future() for _ in range(5)]
    for i, event in enumerate(completed_events):
        event.set_result(
            {
                "tag": "fnord",
                "data": {
                    "return": f"return from fnord {i}",
                    "id": f"fnord {i}",
                },
            }
        )
    uncompleted_events = [salt.ext.tornado.gen.Future() for _ in range(5)]
    events = iter(completed_events + uncompleted_events)
    expected_result = {
        "fnord 0": "return from fnord 0",
        "fnord 1": "return from fnord 1",
        "fnord 2": "return from fnord 2",
        "fnord 3": "return from fnord 3",
        "fnord 4": "return from fnord 4",
    }

    def fancy_get_event(*args, **kwargs):
        if kwargs.get("tag").endswith("/ret"):
            return never_completed
        else:
            return next(events)

    f = salt.ext.tornado.gen.Future()
    f.set_result({"jid": "42", "minions": ["non-existent minion"]})
    with patch.object(
        handler.application.event_listener,
        "get_event",
        side_effect=fancy_get_event,
    ), patch(
        "salt.ext.tornado.gen.sleep",
        autospec=True,
        side_effect=fake_sleep,
    ), patch.dict(
        handler.application.opts,
        {"gather_job_timeout": fakeo_timer, "timeout": 42},
    ), patch.dict(
        handler.saltclients, {"local": lambda *args, **kwargs: f}
    ):
        result = io_loop.run_sync(
            lambda: handler._disbatch_local(
                chunk={"tgt": "*", "tgt_type": "glob", "fun": "test.ping"}
            ),
            timeout=RUN_SYNC_TIMEOUT,
        )

    assert result == expected_result


def test_when_minions_all_return_then_all_collected_data_should_be_returned(
    io_loop, salt_api_handler
):
    handler = salt_api_handler
    completed_event = salt.ext.tornado.gen.Future()
    never_completed = salt.ext.tornado.gen.Future()
    # Timeout is something ridiculously high - it should never be reached
    gather_timeout = 20
    completed_events = [salt.ext.tornado.gen.Future() for _ in range(10)]
    events_by_id = {}
    for i, event in enumerate(completed_events):
        id_ = f"fnord {i}"
        events_by_id[id_] = event
        event.set_result(
            {
                "tag": "fnord",
                "data": {"return": f"return from {id_}", "id": id_},
            }
        )
    expected_result = {
        "fnord 0": "return from fnord 0",
        "fnord 1": "return from fnord 1",
        "fnord 2": "return from fnord 2",
        "fnord 3": "return from fnord 3",
        "fnord 4": "return from fnord 4",
        "fnord 5": "return from fnord 5",
        "fnord 6": "return from fnord 6",
        "fnord 7": "return from fnord 7",
        "fnord 8": "return from fnord 8",
        "fnord 9": "return from fnord 9",
    }

    def fancy_get_event(*args, **kwargs):
        tag = kwargs.get("tag", "").rpartition("/")[-1]
        return events_by_id.get(tag, never_completed)

    f = salt.ext.tornado.gen.Future()
    f.set_result(
        {
            "jid": "42",
            "minions": [e.result()["data"]["id"] for e in completed_events],
        }
    )
    with patch.object(
        handler.application.event_listener,
        "get_event",
        side_effect=fancy_get_event,
    ), patch.dict(
        handler.application.opts,
        {"gather_job_timeout": gather_timeout, "timeout": 42},
    ), patch.dict(
        handler.saltclients, {"local": lambda *args, **kwargs: f}
    ):
        result = io_loop.run_sync(
            lambda: handler._disbatch_local(
                chunk={"tgt": "*", "tgt_type": "glob", "fun": "test.ping"}
            ),
            timeout=RUN_SYNC_TIMEOUT,
        )

    assert result == expected_result


def test_when_min_wait_time_has_not_passed_then_disbatch_should_not_return_expected_data_until_time_has_passed(
    io_loop, salt_api_handler
):
    handler = salt_api_handler
    completed_event = salt.ext.tornado.gen.Future()
    never_completed = salt.ext.tornado.gen.Future()
    wait_timer = salt.ext.tornado.gen.Future()
    gather_timeout = 20
    completed_events = [salt.ext.tornado.gen.Future() for _ in range(10)]
    events_by_id = {}
    # Setup some real-enough looking return data
    for i, event in enumerate(completed_events):
        id_ = f"fnord {i}"
        events_by_id[id_] = event
        event.set_result(
            {
                "tag": "fnord",
                "data": {"return": f"return from {id_}", "id": id_},
            }
        )
    # Hard coded instead of dynamic to avoid potentially writing a test
    # that does nothing
    expected_result = {
        "fnord 0": "return from fnord 0",
        "fnord 1": "return from fnord 1",
        "fnord 2": "return from fnord 2",
        "fnord 3": "return from fnord 3",
        "fnord 4": "return from fnord 4",
        "fnord 5": "return from fnord 5",
        "fnord 6": "return from fnord 6",
        "fnord 7": "return from fnord 7",
        "fnord 8": "return from fnord 8",
        "fnord 9": "return from fnord 9",
    }

    # If this is one of our fnord events, return that future, otherwise
    # they're bogus events that are irrelevant to our current testing.
    # They get to wait for-ev-errrrr
    def fancy_get_event(*args, **kwargs):
        tag = kwargs.get("tag", "").rpartition("/")[-1]
        return events_by_id.get(tag, never_completed)

    minions = {}

    def capture_minions(*args, **kwargs):
        """
        Take minions that would be passed to a function, and
        store them for later checking.
        """
        nonlocal minions
        minions = args[3]

    # Needed to have both a fake sleep, as well as a *real* sleep.
    # The fake sleep is necessary so that we can return our own
    # min_wait_time future. The fakeo_timer object is how we signal
    # which one we need to be returning.
    orig_sleep = salt.ext.tornado.gen.sleep

    fakeo_timer = object()

    @salt.ext.tornado.gen.coroutine
    def fake_sleep(timer):
        # only return our fake min_wait_time future when the sentinel
        # value is provided. Otherwise it's just a number.
        if timer is fakeo_timer:
            yield wait_timer
        else:
            yield orig_sleep(timer)

    f = salt.ext.tornado.gen.Future()
    f.set_result(
        {
            "jid": "42",
            "minions": [e.result()["data"]["id"] for e in completed_events],
        }
    )
    with patch.object(
        handler.application.event_listener,
        "get_event",
        side_effect=fancy_get_event,
    ), patch.object(
        handler,
        "job_not_running",
        autospec=True,
        side_effect=capture_minions,
    ), patch.dict(
        handler.application.opts,
        {
            "gather_job_timeout": gather_timeout,
            "timeout": 42,
            "syndic_wait": fakeo_timer,
            "order_masters": True,
        },
    ), patch(
        "salt.ext.tornado.gen.sleep",
        autospec=True,
        side_effect=fake_sleep,
    ), patch.dict(
        handler.saltclients, {"local": lambda *args, **kwargs: f}
    ):

        # Example timeline that we're testing:
        #
        # If there's a min wait time of 10s, and all the results come
        # back in 5s, we still need to wait the full 10s.
        #
        # Here:
        # t=0, all events are completed
        # t=0.1, we check that all minions have been set to True, i.e. all
        #        events are completed. We also ensure that the future has
        #        not completed.
        # t=0.1+, we complete our injected timer, and then ensure that all
        #         the correct data has been returned.

        @salt.ext.tornado.gen.coroutine
        def run():
            fut = handler._disbatch_local(
                chunk={"tgt": "*", "tgt_type": "glob", "fun": "test.ping"}
            )

            yield salt.ext.tornado.gen.sleep(0.1)
            # here, all the minions should be complete (i.e. "True")
            assert all(minions[m_id] for m_id in minions)
            # But _disbatch_local is not returned yet because min_wait_time has not passed
            assert not fut.done()
            wait_timer.set_result(None)
            result = yield fut
            raise salt.ext.tornado.gen.Return(result)

        result = io_loop.run_sync(run, timeout=RUN_SYNC_TIMEOUT)

    assert result == expected_result


# Question: Currently, job_not_running can add to the minions dict, which
# affects the more_todo result. However, the events are never added to
# once we have entered the loop. I'm not sure if this is an oversight, or
# simply an implicit expectation. I am making the assumption that this
# behavior is correct and does not need extra testing. Otherwise, we should
# be testing that when minions are added within job_not_running, that it
# should affect the regular loop
# -W. Werner, 2020-11-19
# <----- TestDisbatchLocal -------------------------------------------------------------------------------------------
