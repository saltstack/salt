import salt.ext.tornado
import salt.ext.tornado.testing
import salt.netapi.rest_tornado.saltnado as saltnado
from tests.support.mock import MagicMock, patch


class TestJobNotRunning(salt.ext.tornado.testing.AsyncTestCase):
    def setUp(self):
        super().setUp()
        self.mock = MagicMock()
        self.mock.opts = {
            "syndic_wait": 0.1,
            "cachedir": "/tmp/testing/cachedir",
            "sock_dir": "/tmp/testing/sock_drawer",
            "transport": "zeromq",
            "extension_modules": "/tmp/testing/moduuuuules",
            "order_masters": False,
            "gather_job_timeout": 10.001,
        }
        self.handler = saltnado.SaltAPIHandler(self.mock, self.mock)
        self.handler._write_buffer = []
        self.handler._transforms = []
        self.handler.lowstate = []
        self.handler.content_type = "text/plain"
        self.handler.dumper = lambda x: x
        f = salt.ext.tornado.gen.Future()
        f.set_result({"jid": f, "minions": []})
        self.handler.saltclients.update({"local": lambda *args, **kwargs: f})

    @salt.ext.tornado.testing.gen_test
    def test_when_disbatch_has_already_finished_then_writing_return_should_not_fail(
        self,
    ):
        self.handler.finish()
        result = yield self.handler.disbatch()
        # No assertion necessary, because we just want no failure here.
        # Asserting that it doesn't raise anything is... the default behavior
        # for a test.

    @salt.ext.tornado.testing.gen_test
    def test_when_disbatch_has_already_finished_then_finishing_should_not_fail(self):
        self.handler.finish()
        result = yield self.handler.disbatch()
        # No assertion necessary, because we just want no failure here.
        # Asserting that it doesn't raise anything is... the default behavior
        # for a test.

    @salt.ext.tornado.testing.gen_test
    def test_when_event_times_out_and_minion_is_not_running_result_should_be_True(self):
        fut = salt.ext.tornado.gen.Future()
        fut.set_exception(saltnado.TimeoutException())
        self.mock.event_listener.get_event.return_value = fut
        wrong_future = salt.ext.tornado.gen.Future()

        result = yield self.handler.job_not_running(
            jid=42, tgt="*", tgt_type="glob", minions=[], is_finished=wrong_future
        )

        self.assertTrue(result)

    @salt.ext.tornado.testing.gen_test
    def test_when_event_times_out_and_minion_is_not_running_minion_data_should_not_be_set(
        self,
    ):
        fut = salt.ext.tornado.gen.Future()
        fut.set_exception(saltnado.TimeoutException())
        self.mock.event_listener.get_event.return_value = fut
        wrong_future = salt.ext.tornado.gen.Future()
        minions = {}

        result = yield self.handler.job_not_running(
            jid=42, tgt="*", tgt_type="glob", minions=minions, is_finished=wrong_future
        )

        assert not minions

    @salt.ext.tornado.testing.gen_test
    def test_when_event_finally_finishes_and_returned_minion_not_in_minions_it_should_be_set_to_False(
        self,
    ):
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
        self.mock.event_listener.get_event.side_effect = [
            no_data_event,
            empty_return_event,
            actual_return_event,
            timed_out_event,
            timed_out_event,
        ]
        minions = {}

        yield self.handler.job_not_running(
            jid=99,
            tgt="*",
            tgt_type="fnord",
            minions=minions,
            is_finished=salt.ext.tornado.gen.Future(),
        )

        self.assertFalse(minions[expected_id])

    @salt.ext.tornado.testing.gen_test
    def test_when_event_finally_finishes_and_returned_minion_already_in_minions_it_should_not_be_changed(
        self,
    ):
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
        self.mock.event_listener.get_event.side_effect = [
            no_data_event,
            empty_return_event,
            actual_return_event,
            timed_out_event,
            timed_out_event,
        ]

        yield self.handler.job_not_running(
            jid=99,
            tgt="*",
            tgt_type="fnord",
            minions=minions,
            is_finished=salt.ext.tornado.gen.Future(),
        )

        self.assertIs(minions[expected_id], expected_value)

    @salt.ext.tornado.testing.gen_test
    def test_when_event_returns_early_and_finally_times_out_result_should_be_True(self):
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
        self.mock.event_listener.get_event.side_effect = [
            no_data_event,
            empty_return_event,
            actual_return_event,
            timed_out_event,
            timed_out_event,
        ]

        result = yield self.handler.job_not_running(
            jid=99,
            tgt="*",
            tgt_type="fnord",
            minions={},
            is_finished=salt.ext.tornado.gen.Future(),
        )
        self.assertTrue(result)

    @salt.ext.tornado.testing.gen_test
    def test_when_event_finishes_but_is_finished_is_done_then_result_should_be_True(
        self,
    ):
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

        self.mock.event_listener.get_event.side_effect = (x for x in abort())

        result = yield self.handler.job_not_running(
            jid=99,
            tgt="*",
            tgt_type="fnord",
            minions=minions,
            is_finished=is_finished,
        )
        self.assertTrue(result)

        # These are failsafes to ensure nothing super sideways happened
        self.assertTrue(len(minions) == 1, str(minions))
        self.assertIs(minions[expected_minion_id], expected_minion_value)

    @salt.ext.tornado.testing.gen_test
    def test_when_is_finished_times_out_before_event_finishes_result_should_be_True(
        self,
    ):
        # Other test times out with event - this one should time out for is_finished
        finished = salt.ext.tornado.gen.Future()
        finished.set_exception(saltnado.TimeoutException())
        wrong_future = salt.ext.tornado.gen.Future()
        self.mock.event_listener.get_event.return_value = wrong_future

        result = yield self.handler.job_not_running(
            jid=42, tgt="*", tgt_type="glob", minions=[], is_finished=finished
        )

        self.assertTrue(result)

    @salt.ext.tornado.testing.gen_test
    def test_when_is_finished_times_out_before_event_finishes_event_should_have_result_set_to_None(
        self,
    ):
        finished = salt.ext.tornado.gen.Future()
        finished.set_exception(saltnado.TimeoutException())
        wrong_future = salt.ext.tornado.gen.Future()
        self.mock.event_listener.get_event.return_value = wrong_future

        result = yield self.handler.job_not_running(
            jid=42, tgt="*", tgt_type="glob", minions=[], is_finished=finished
        )

        self.assertIsNone(wrong_future.result())


# TODO: I think we can extract seUp into a superclass -W. Werner, 2020-11-03
class TestGetMinionReturns(salt.ext.tornado.testing.AsyncTestCase):
    def setUp(self):
        super().setUp()
        self.mock = MagicMock()
        self.mock.opts = {
            "syndic_wait": 0.1,
            "cachedir": "/tmp/testing/cachedir",
            "sock_dir": "/tmp/testing/sock_drawer",
            "transport": "zeromq",
            "extension_modules": "/tmp/testing/moduuuuules",
            "order_masters": False,
            "gather_job_timeout": 10.001,
        }
        self.handler = saltnado.SaltAPIHandler(self.mock, self.mock)
        f = salt.ext.tornado.gen.Future()
        f.set_result({"jid": f, "minions": []})

    @salt.ext.tornado.testing.gen_test
    def test_if_finished_before_any_events_return_then_result_should_be_empty_dictionary(
        self,
    ):
        expected_result = {}
        xxx = salt.ext.tornado.gen.Future()
        xxx.set_result(None)
        is_finished = salt.ext.tornado.gen.Future()
        is_finished.set_result(None)
        actual_result = yield self.handler.get_minion_returns(
            events=[],
            is_finished=is_finished,
            is_timed_out=salt.ext.tornado.gen.Future(),
            min_wait_time=xxx,
            minions={},
        )
        self.assertDictEqual(actual_result, expected_result)

    # TODO: Copy above - test with timed out -W. Werner, 2020-11-05

    @salt.ext.tornado.testing.gen_test
    def test_if_is_finished_after_events_return_then_result_should_contain_event_result_data(
        self,
    ):
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
        self.io_loop.call_later(0.2, lambda: is_finished.set_result(None))

        actual_result = yield self.handler.get_minion_returns(
            events=events,
            is_finished=is_finished,
            is_timed_out=salt.ext.tornado.gen.Future(),
            min_wait_time=xxx,
            minions={
                "minion1": False,
                "minion2": False,
                "never returning minion": False,
            },
        )

        assert actual_result == expected_result

    @salt.ext.tornado.testing.gen_test
    def test_if_timed_out_after_events_return_then_result_should_contain_event_result_data(
        self,
    ):
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
        self.io_loop.call_later(0.2, lambda: is_timed_out.set_result(None))

        actual_result = yield self.handler.get_minion_returns(
            events=events,
            is_finished=salt.ext.tornado.gen.Future(),
            is_timed_out=is_timed_out,
            min_wait_time=xxx,
            minions={
                "minion1": False,
                "minion2": False,
                "never returning minion": False,
            },
        )

        assert actual_result == expected_result

    @salt.ext.tornado.testing.gen_test
    def test_if_wait_timer_is_not_done_even_though_results_are_then_data_should_not_yet_be_returned(
        self,
    ):
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
        fut = self.handler.get_minion_returns(
            events=events,
            is_finished=salt.ext.tornado.gen.Future(),
            is_timed_out=salt.ext.tornado.gen.Future(),
            min_wait_time=wait_timer,
            minions={"one": False, "two": False},
        )

        def boop():
            yield fut

        self.io_loop.spawn_callback(boop)
        yield salt.ext.tornado.gen.sleep(0.1)

        assert not fut.done()

        wait_timer.set_result(None)
        actual_result = yield fut

        assert actual_result == expected_result

    @salt.ext.tornado.testing.gen_test
    def test_when_is_finished_any_other_futures_should_be_canceled(self):
        events = [
            salt.ext.tornado.gen.Future(),
            salt.ext.tornado.gen.Future(),
            salt.ext.tornado.gen.Future(),
            salt.ext.tornado.gen.Future(),
            salt.ext.tornado.gen.Future(),
        ]

        is_finished = salt.ext.tornado.gen.Future()
        is_finished.set_result(None)
        yield self.handler.get_minion_returns(
            events=events,
            is_finished=is_finished,
            is_timed_out=salt.ext.tornado.gen.Future(),
            min_wait_time=salt.ext.tornado.gen.Future(),
            minions={"one": False, "two": False},
        )

        are_done = [event.done() for event in events]
        assert all(are_done)

    @salt.ext.tornado.testing.gen_test
    def test_when_an_event_times_out_then_we_should_not_enter_an_infinite_loop(self):
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
        self.io_loop.call_later(0.5, lambda: times_out_later.set_result(None))
        yield self.handler.get_minion_returns(
            events=events,
            is_finished=salt.ext.tornado.gen.Future(),
            is_timed_out=times_out_later,
            min_wait_time=salt.ext.tornado.gen.Future(),
            minions={"one": False, "two": False},
        )

        # Technically we don't /need/ to check that all events are done,
        # but it's incorrect to exit the function without ensuring all
        # futures are canceled.
        are_done = [event.done() for event in events]
        assert all(are_done)
        assert times_out_later.done()

    @salt.ext.tornado.testing.gen_test
    def test_when_is_timed_out_any_other_futures_should_be_canceled(self):
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
        yield self.handler.get_minion_returns(
            events=events,
            is_finished=salt.ext.tornado.gen.Future(),
            is_timed_out=is_timed_out,
            min_wait_time=salt.ext.tornado.gen.Future(),
            minions={"one": False, "two": False},
        )

        are_done = [event.done() for event in events]
        assert all(are_done)

    @salt.ext.tornado.testing.gen_test
    def test_when_min_wait_time_and_nothing_todo_any_other_futures_should_be_canceled(
        self,
    ):
        events = [
            salt.ext.tornado.gen.Future(),
            salt.ext.tornado.gen.Future(),
            salt.ext.tornado.gen.Future(),
            salt.ext.tornado.gen.Future(),
            salt.ext.tornado.gen.Future(),
        ]

        is_finished = salt.ext.tornado.gen.Future()
        min_wait_time = salt.ext.tornado.gen.Future()
        self.io_loop.call_later(0.2, lambda: min_wait_time.set_result(None))

        yield self.handler.get_minion_returns(
            events=events,
            is_finished=is_finished,
            is_timed_out=salt.ext.tornado.gen.Future(),
            min_wait_time=min_wait_time,
            minions={"one": True, "two": True},
        )

        are_done = [event.done() for event in events] + [is_finished.done()]
        assert all(are_done)

    @salt.ext.tornado.testing.gen_test
    def test_when_is_finished_but_not_is_timed_out_then_timed_out_should_not_be_set_to_done(
        self,
    ):
        events = [salt.ext.tornado.gen.Future()]
        is_timed_out = salt.ext.tornado.gen.Future()
        is_finished = salt.ext.tornado.gen.Future()
        is_finished.set_result(None)

        yield self.handler.get_minion_returns(
            events=events,
            is_finished=is_finished,
            is_timed_out=is_timed_out,
            min_wait_time=salt.ext.tornado.gen.Future(),
            minions={"one": False, "two": False},
        )

        assert not is_timed_out.done()

    @salt.ext.tornado.testing.gen_test
    def test_when_min_wait_time_and_all_completed_but_not_is_timed_out_then_timed_out_should_not_be_set_to_done(
        self,
    ):
        events = [salt.ext.tornado.gen.Future()]
        is_timed_out = salt.ext.tornado.gen.Future()
        min_wait_time = salt.ext.tornado.gen.Future()
        self.io_loop.call_later(0.2, lambda: min_wait_time.set_result(None))

        yield self.handler.get_minion_returns(
            events=events,
            is_finished=salt.ext.tornado.gen.Future(),
            is_timed_out=is_timed_out,
            min_wait_time=min_wait_time,
            minions={"one": True},
        )

        assert not is_timed_out.done()

    @salt.ext.tornado.testing.gen_test
    def test_when_things_are_completed_but_not_timed_out_then_timed_out_event_should_not_be_done(
        self,
    ):
        events = [
            salt.ext.tornado.gen.Future(),
        ]
        events[0].set_result({"tag": "fnord", "data": {"id": "one", "return": {}}})
        min_wait_time = salt.ext.tornado.gen.Future()
        min_wait_time.set_result(None)
        is_timed_out = salt.ext.tornado.gen.Future()

        yield self.handler.get_minion_returns(
            events=events,
            is_finished=salt.ext.tornado.gen.Future(),
            is_timed_out=is_timed_out,
            min_wait_time=min_wait_time,
            minions={"one": True},
        )

        assert not is_timed_out.done()


class TestDisbatchLocal(salt.ext.tornado.testing.AsyncTestCase):
    def setUp(self):
        super().setUp()
        self.mock = MagicMock()
        self.mock.opts = {
            "syndic_wait": 0.1,
            "cachedir": "/tmp/testing/cachedir",
            "sock_dir": "/tmp/testing/sock_drawer",
            "transport": "zeromq",
            "extension_modules": "/tmp/testing/moduuuuules",
            "order_masters": False,
            "gather_job_timeout": 10.001,
        }
        self.handler = saltnado.SaltAPIHandler(self.mock, self.mock)

    @salt.ext.tornado.testing.gen_test
    def test_when_is_timed_out_is_set_before_other_events_are_completed_then_result_should_be_empty_dictionary(
        self,
    ):
        completed_event = salt.ext.tornado.gen.Future()
        never_completed = salt.ext.tornado.gen.Future()
        # TODO: We may need to tweak these values to get them close enough but not so far away -W. Werner, 2020-11-17
        gather_timeout = 0.1
        event_timeout = gather_timeout + 0.05

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

        self.io_loop.call_later(event_timeout, completer)

        f = salt.ext.tornado.gen.Future()
        f.set_result({"jid": "42", "minions": []})
        with patch.object(
            self.handler.application.event_listener,
            "get_event",
            autospec=True,
            side_effect=fancy_get_event,
        ), patch.dict(
            self.handler.application.opts,
            {"gather_job_timeout": gather_timeout, "timeout": 42},
        ), patch.dict(
            self.handler.saltclients, {"local": lambda *args, **kwargs: f}
        ):
            result = yield self.handler._disbatch_local(
                chunk={"tgt": "*", "tgt_type": "glob", "fun": "test.ping"}
            )

        assert result == {}

    @salt.ext.tornado.testing.gen_test
    def test_when_is_finished_is_set_before_events_return_then_no_data_should_be_returned(
        self,
    ):
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

        self.io_loop.call_later(event_timeout, completer)

        def toggle_is_finished(*args, **kwargs):
            finished = kwargs.get("is_finished", args[4] if len(args) > 4 else None)
            assert finished is not None
            finished.set_result(42)

        f = salt.ext.tornado.gen.Future()
        f.set_result({"jid": "42", "minions": []})
        with patch.object(
            self.handler.application.event_listener,
            "get_event",
            autospec=True,
            side_effect=fancy_get_event,
        ), patch.object(
            self.handler,
            "job_not_running",
            autospec=True,
            side_effect=toggle_is_finished,
        ), patch.dict(
            self.handler.application.opts,
            {"gather_job_timeout": gather_timeout, "timeout": 42},
        ), patch.dict(
            self.handler.saltclients, {"local": lambda *args, **kwargs: f}
        ):
            result = yield self.handler._disbatch_local(
                chunk={"tgt": "*", "tgt_type": "glob", "fun": "test.ping"}
            )

        assert result == {}

    @salt.ext.tornado.testing.gen_test
    def test_when_is_finished_then_all_collected_data_should_be_returned(self):
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
                        "return": "return from fnord {}".format(i),
                        "id": "fnord {}".format(i),
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
            self.handler.application.event_listener,
            "get_event",
            autospec=True,
            side_effect=fancy_get_event,
        ), patch.object(
            self.handler,
            "job_not_running",
            autospec=True,
            side_effect=toggle_is_finished,
        ), patch.dict(
            self.handler.application.opts,
            {"gather_job_timeout": gather_timeout, "timeout": 42},
        ), patch.dict(
            self.handler.saltclients, {"local": lambda *args, **kwargs: f}
        ):
            result = yield self.handler._disbatch_local(
                chunk={"tgt": "*", "tgt_type": "glob", "fun": "test.ping"}
            )

        assert result == expected_result

    @salt.ext.tornado.testing.gen_test
    def test_when_is_timed_out_then_all_collected_data_should_be_returned(self):
        completed_event = salt.ext.tornado.gen.Future()
        never_completed = salt.ext.tornado.gen.Future()
        # 2s is probably enough for any kind of computer to manage to
        # do all the other processing. We could maybe reduce this - just
        # depends on how slow of a system we're running on.
        # TODO: Maybe we should have a test helper/fixture that benchmarks the system and gets a reasonable timeout? -W. Werner, 2020-11-19
        gather_timeout = 2
        completed_events = [salt.ext.tornado.gen.Future() for _ in range(5)]
        for i, event in enumerate(completed_events):
            event.set_result(
                {
                    "tag": "fnord",
                    "data": {
                        "return": "return from fnord {}".format(i),
                        "id": "fnord {}".format(i),
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
            self.handler.application.event_listener,
            "get_event",
            autospec=True,
            side_effect=fancy_get_event,
        ), patch.dict(
            self.handler.application.opts,
            {"gather_job_timeout": gather_timeout, "timeout": 42},
        ), patch.dict(
            self.handler.saltclients, {"local": lambda *args, **kwargs: f}
        ):
            result = yield self.handler._disbatch_local(
                chunk={"tgt": "*", "tgt_type": "glob", "fun": "test.ping"}
            )

        assert result == expected_result

    @salt.ext.tornado.testing.gen_test
    def test_when_minions_all_return_then_all_collected_data_should_be_returned(self):
        completed_event = salt.ext.tornado.gen.Future()
        never_completed = salt.ext.tornado.gen.Future()
        # Timeout is something ridiculously high - it should never be reached
        gather_timeout = 20
        completed_events = [salt.ext.tornado.gen.Future() for _ in range(10)]
        events_by_id = {}
        for i, event in enumerate(completed_events):
            id_ = "fnord {}".format(i)
            events_by_id[id_] = event
            event.set_result(
                {
                    "tag": "fnord",
                    "data": {"return": "return from {}".format(id_), "id": id_},
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
            self.handler.application.event_listener,
            "get_event",
            autospec=True,
            side_effect=fancy_get_event,
        ), patch.dict(
            self.handler.application.opts,
            {"gather_job_timeout": gather_timeout, "timeout": 42},
        ), patch.dict(
            self.handler.saltclients, {"local": lambda *args, **kwargs: f}
        ):
            result = yield self.handler._disbatch_local(
                chunk={"tgt": "*", "tgt_type": "glob", "fun": "test.ping"}
            )

        assert result == expected_result

    @salt.ext.tornado.testing.gen_test
    def test_when_min_wait_time_has_not_passed_then_disbatch_should_not_return_expected_data_until_time_has_passed(
        self,
    ):
        completed_event = salt.ext.tornado.gen.Future()
        never_completed = salt.ext.tornado.gen.Future()
        wait_timer = salt.ext.tornado.gen.Future()
        gather_timeout = 20
        completed_events = [salt.ext.tornado.gen.Future() for _ in range(10)]
        events_by_id = {}
        # Setup some real-enough looking return data
        for i, event in enumerate(completed_events):
            id_ = "fnord {}".format(i)
            events_by_id[id_] = event
            event.set_result(
                {
                    "tag": "fnord",
                    "data": {"return": "return from {}".format(id_), "id": id_},
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
            self.handler.application.event_listener,
            "get_event",
            autospec=True,
            side_effect=fancy_get_event,
        ), patch.object(
            self.handler,
            "job_not_running",
            autospec=True,
            side_effect=capture_minions,
        ), patch.dict(
            self.handler.application.opts,
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
            self.handler.saltclients, {"local": lambda *args, **kwargs: f}
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

            fut = self.handler._disbatch_local(
                chunk={"tgt": "*", "tgt_type": "glob", "fun": "test.ping"}
            )

            def boop():
                yield fut

            self.io_loop.spawn_callback(boop)
            yield salt.ext.tornado.gen.sleep(0.1)
            # here, all the minions should be complete (i.e. "True")
            assert all(minions[m_id] for m_id in minions)
            # But _disbatch_local is not returned yet because min_wait_time has not passed
            assert not fut.done()
            wait_timer.set_result(None)
            result = yield fut

        assert result == expected_result

    # Question: Currently, job_not_running can add to the minions dict, which
    # affects the more_todo result. However, the events are never added to
    # once we have entered the loop. I'm not sure if this is an oversight, or
    # simply an implicit expectation. I am making the assumption that this
    # behavior is correct and does not need extra testing. Otherwise, we should
    # be testing that when minions are added within job_not_running, that it
    # should affect the regular loop
    # -W. Werner, 2020-11-19
