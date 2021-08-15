import os
import threading
import time

import pytest
import salt.ext.tornado.ioloop
import salt.utils.json
import salt.utils.stringutils
from salt.netapi.rest_tornado import saltnado
from tests.support.helpers import TstSuiteLoggingHandler
from tests.support.unit import skipIf
from tests.unit.netapi.test_rest_tornado import SaltnadoTestsBase


class SaltnadoIntegrationTestsBase(SaltnadoTestsBase):
    @property
    def opts(self):
        return self.get_config("client_config", from_scratch=True)

    @property
    def mod_opts(self):
        return self.get_config("minion", from_scratch=True)

    def get_app(self):
        raise NotImplementedError


@pytest.mark.usefixtures("salt_sub_minion")
class TestSaltAPIHandler(SaltnadoIntegrationTestsBase):
    def setUp(self):
        super().setUp()
        os.environ["ASYNC_TEST_TIMEOUT"] = "300"

    def get_app(self):
        urls = [("/", saltnado.SaltAPIHandler)]

        application = self.build_tornado_app(urls)

        application.event_listener = saltnado.EventListener({}, self.opts)
        self.application = application
        return application

    def test_root(self):
        """
        Test the root path which returns the list of clients we support
        """
        response = self.fetch(
            "/",
            connect_timeout=30,
            request_timeout=30,
        )
        self.assertEqual(response.code, 200)
        response_obj = salt.utils.json.loads(response.body)
        self.assertEqual(
            sorted(response_obj["clients"]),
            ["local", "local_async", "runner", "runner_async"],
        )
        self.assertEqual(response_obj["return"], "Welcome")

    @pytest.mark.slow_test
    def test_post_no_auth(self):
        """
        Test post with no auth token, should 401
        """
        # get a token for this test
        low = [{"client": "local", "tgt": "*", "fun": "test.ping"}]
        response = self.fetch(
            "/",
            method="POST",
            body=salt.utils.json.dumps(low),
            headers={"Content-Type": self.content_type_map["json"]},
            follow_redirects=False,
            connect_timeout=30,
            request_timeout=30,
        )
        self.assertEqual(response.code, 302)
        self.assertEqual(response.headers["Location"], "/login")

    # Local client tests

    @pytest.mark.slow_test
    def test_regression_49572(self):
        with TstSuiteLoggingHandler() as handler:
            GATHER_JOB_TIMEOUT = 1
            self.application.opts["gather_job_timeout"] = GATHER_JOB_TIMEOUT

            low = [{"client": "local", "tgt": "*", "fun": "test.ping"}]
            fetch_kwargs = {
                "method": "POST",
                "body": salt.utils.json.dumps(low),
                "headers": {
                    "Content-Type": self.content_type_map["json"],
                    saltnado.AUTH_TOKEN_HEADER: self.token["token"],
                },
                "connect_timeout": 30,
                "request_timeout": 30,
            }

            self.fetch("/", **fetch_kwargs)
            time.sleep(GATHER_JOB_TIMEOUT + 0.1)  # ick

            #  While the traceback is in the logs after the sleep without this
            #  follow up fetch, the logging handler doesn't see it in its list
            #  of messages unless something else runs.
            self.fetch("/", **fetch_kwargs)

            for message in handler.messages:
                if "TypeError: 'NoneType' object is not iterable" in message:
                    raise AssertionError(
                        "#49572: regression: set_result on completed event"
                    )

    def test_simple_local_post(self):
        """
        Test a basic API of /
        """
        low = [{"client": "local", "tgt": "*", "fun": "test.ping"}]
        response = self.fetch(
            "/",
            method="POST",
            body=salt.utils.json.dumps(low),
            headers={
                "Content-Type": self.content_type_map["json"],
                saltnado.AUTH_TOKEN_HEADER: self.token["token"],
            },
            connect_timeout=30,
            request_timeout=30,
        )
        response_obj = salt.utils.json.loads(response.body)
        self.assertEqual(len(response_obj["return"]), 1)
        # If --proxy is set, it will cause an extra minion_id to be in the
        # response. Since there's not a great way to know if the test
        # runner's proxy minion is running, and we're not testing proxy
        # minions here anyway, just remove it from the response.
        response_obj["return"][0].pop("proxytest", None)
        self.assertEqual(
            response_obj["return"][0], {"minion": True, "sub_minion": True}
        )

    def test_simple_local_post_no_tgt(self):
        """
        POST job with invalid tgt
        """
        low = [{"client": "local", "tgt": "minion_we_dont_have", "fun": "test.ping"}]
        response = self.fetch(
            "/",
            method="POST",
            body=salt.utils.json.dumps(low),
            headers={
                "Content-Type": self.content_type_map["json"],
                saltnado.AUTH_TOKEN_HEADER: self.token["token"],
            },
            connect_timeout=30,
            request_timeout=30,
        )
        response_obj = salt.utils.json.loads(response.body)
        self.assertEqual(
            response_obj["return"],
            [
                "No minions matched the target. No command was sent, no jid was"
                " assigned."
            ],
        )

    # local client request body test

    def test_simple_local_post_only_dictionary_request(self):
        """
        Test a basic API of /
        """
        low = {
            "client": "local",
            "tgt": "*",
            "fun": "test.ping",
        }
        response = self.fetch(
            "/",
            method="POST",
            body=salt.utils.json.dumps(low),
            headers={
                "Content-Type": self.content_type_map["json"],
                saltnado.AUTH_TOKEN_HEADER: self.token["token"],
            },
            connect_timeout=30,
            request_timeout=30,
        )
        response_obj = salt.utils.json.loads(response.body)
        self.assertEqual(len(response_obj["return"]), 1)
        # If --proxy is set, it will cause an extra minion_id to be in the
        # response. Since there's not a great way to know if the test
        # runner's proxy minion is running, and we're not testing proxy
        # minions here anyway, just remove it from the response.
        response_obj["return"][0].pop("proxytest", None)
        self.assertEqual(
            response_obj["return"][0], {"minion": True, "sub_minion": True}
        )

    def test_simple_local_post_invalid_request(self):
        """
        Test a basic API of /
        """
        low = ["invalid request"]
        response = self.fetch(
            "/",
            method="POST",
            body=salt.utils.json.dumps(low),
            headers={
                "Content-Type": self.content_type_map["json"],
                saltnado.AUTH_TOKEN_HEADER: self.token["token"],
            },
            connect_timeout=30,
            request_timeout=30,
        )
        self.assertEqual(response.code, 400)

    # local_async tests
    def test_simple_local_async_post(self):
        low = [{"client": "local_async", "tgt": "*", "fun": "test.ping"}]
        response = self.fetch(
            "/",
            method="POST",
            body=salt.utils.json.dumps(low),
            headers={
                "Content-Type": self.content_type_map["json"],
                saltnado.AUTH_TOKEN_HEADER: self.token["token"],
            },
        )

        response_obj = salt.utils.json.loads(response.body)
        ret = response_obj["return"]
        ret[0]["minions"] = sorted(ret[0]["minions"])
        try:
            # If --proxy is set, it will cause an extra minion_id to be in the
            # response. Since there's not a great way to know if the test
            # runner's proxy minion is running, and we're not testing proxy
            # minions here anyway, just remove it from the response.
            ret[0]["minions"].remove("proxytest")
        except ValueError:
            pass

        # TODO: verify pub function? Maybe look at how we test the publisher
        self.assertEqual(len(ret), 1)
        self.assertIn("jid", ret[0])
        self.assertEqual(ret[0]["minions"], sorted(["minion", "sub_minion"]))

    def test_multi_local_async_post(self):
        low = [
            {"client": "local_async", "tgt": "*", "fun": "test.ping"},
            {"client": "local_async", "tgt": "*", "fun": "test.ping"},
        ]
        response = self.fetch(
            "/",
            method="POST",
            body=salt.utils.json.dumps(low),
            headers={
                "Content-Type": self.content_type_map["json"],
                saltnado.AUTH_TOKEN_HEADER: self.token["token"],
            },
        )

        response_obj = salt.utils.json.loads(response.body)
        ret = response_obj["return"]
        ret[0]["minions"] = sorted(ret[0]["minions"])
        ret[1]["minions"] = sorted(ret[1]["minions"])
        try:
            # If --proxy is set, it will cause an extra minion_id to be in the
            # response. Since there's not a great way to know if the test
            # runner's proxy minion is running, and we're not testing proxy
            # minions here anyway, just remove it from the response.
            ret[0]["minions"].remove("proxytest")
            ret[1]["minions"].remove("proxytest")
        except ValueError:
            pass

        self.assertEqual(len(ret), 2)
        self.assertIn("jid", ret[0])
        self.assertIn("jid", ret[1])
        self.assertEqual(ret[0]["minions"], sorted(["minion", "sub_minion"]))
        self.assertEqual(ret[1]["minions"], sorted(["minion", "sub_minion"]))

    @pytest.mark.slow_test
    def test_multi_local_async_post_multitoken(self):
        low = [
            {"client": "local_async", "tgt": "*", "fun": "test.ping"},
            {
                "client": "local_async",
                "tgt": "*",
                "fun": "test.ping",
                "token": self.token[
                    "token"
                ],  # send a different (but still valid token)
            },
            {
                "client": "local_async",
                "tgt": "*",
                "fun": "test.ping",
                "token": "BAD_TOKEN",  # send a bad token
            },
        ]
        response = self.fetch(
            "/",
            method="POST",
            body=salt.utils.json.dumps(low),
            headers={
                "Content-Type": self.content_type_map["json"],
                saltnado.AUTH_TOKEN_HEADER: self.token["token"],
            },
        )

        response_obj = salt.utils.json.loads(response.body)
        ret = response_obj["return"]
        ret[0]["minions"] = sorted(ret[0]["minions"])
        ret[1]["minions"] = sorted(ret[1]["minions"])
        try:
            # If --proxy is set, it will cause an extra minion_id to be in the
            # response. Since there's not a great way to know if the test
            # runner's proxy minion is running, and we're not testing proxy
            # minions here anyway, just remove it from the response.
            ret[0]["minions"].remove("proxytest")
            ret[1]["minions"].remove("proxytest")
        except ValueError:
            pass

        self.assertEqual(len(ret), 3)  # make sure we got 3 responses
        self.assertIn("jid", ret[0])  # the first 2 are regular returns
        self.assertIn("jid", ret[1])
        self.assertIn("Failed to authenticate", ret[2])  # bad auth
        self.assertEqual(ret[0]["minions"], sorted(["minion", "sub_minion"]))
        self.assertEqual(ret[1]["minions"], sorted(["minion", "sub_minion"]))

    @pytest.mark.slow_test
    def test_simple_local_async_post_no_tgt(self):
        low = [
            {"client": "local_async", "tgt": "minion_we_dont_have", "fun": "test.ping"}
        ]
        response = self.fetch(
            "/",
            method="POST",
            body=salt.utils.json.dumps(low),
            headers={
                "Content-Type": self.content_type_map["json"],
                saltnado.AUTH_TOKEN_HEADER: self.token["token"],
            },
        )
        response_obj = salt.utils.json.loads(response.body)
        self.assertEqual(response_obj["return"], [{}])

    @skipIf(True, "Undetermined race condition in test. Temporarily disabled.")
    def test_simple_local_post_only_dictionary_request_with_order_masters(self):
        """
        Test a basic API of /
        """
        low = {
            "client": "local",
            "tgt": "*",
            "fun": "test.ping",
        }

        self.application.opts["order_masters"] = True
        self.application.opts["syndic_wait"] = 5

        response = self.fetch(
            "/",
            method="POST",
            body=salt.utils.json.dumps(low),
            headers={
                "Content-Type": self.content_type_map["json"],
                saltnado.AUTH_TOKEN_HEADER: self.token["token"],
            },
            connect_timeout=30,
            request_timeout=30,
        )
        response_obj = salt.utils.json.loads(response.body)
        self.application.opts["order_masters"] = []
        self.application.opts["syndic_wait"] = 5
        # If --proxy is set, it will cause an extra minion_id to be in the
        # response. Since there's not a great way to know if the test runner's
        # proxy minion is running, and we're not testing proxy minions here
        # anyway, just remove it from the response.
        response_obj[0]["return"].pop("proxytest", None)
        self.assertEqual(response_obj["return"], [{"minion": True, "sub_minion": True}])

    # runner tests
    @pytest.mark.slow_test
    def test_simple_local_runner_post(self):
        low = [{"client": "runner", "fun": "manage.up"}]
        response = self.fetch(
            "/",
            method="POST",
            body=salt.utils.json.dumps(low),
            headers={
                "Content-Type": self.content_type_map["json"],
                saltnado.AUTH_TOKEN_HEADER: self.token["token"],
            },
            connect_timeout=30,
            request_timeout=300,
        )
        response_obj = salt.utils.json.loads(response.body)
        self.assertEqual(len(response_obj["return"]), 1)
        try:
            # If --proxy is set, it will cause an extra minion_id to be in the
            # response. Since there's not a great way to know if the test
            # runner's proxy minion is running, and we're not testing proxy
            # minions here anyway, just remove it from the response.
            response_obj["return"][0].remove("proxytest")
        except ValueError:
            pass
        self.assertEqual(
            sorted(response_obj["return"][0]), sorted(["minion", "sub_minion"])
        )

    # runner_async tests
    def test_simple_local_runner_async_post(self):
        low = [{"client": "runner_async", "fun": "manage.up"}]
        response = self.fetch(
            "/",
            method="POST",
            body=salt.utils.json.dumps(low),
            headers={
                "Content-Type": self.content_type_map["json"],
                saltnado.AUTH_TOKEN_HEADER: self.token["token"],
            },
            connect_timeout=10,
            request_timeout=10,
        )
        response_obj = salt.utils.json.loads(response.body)
        self.assertIn("return", response_obj)
        self.assertEqual(1, len(response_obj["return"]))
        self.assertIn("jid", response_obj["return"][0])
        self.assertIn("tag", response_obj["return"][0])


@pytest.mark.flaky(max_runs=4)
class TestMinionSaltAPIHandler(SaltnadoIntegrationTestsBase):
    def get_app(self):
        urls = [
            (r"/minions/(.*)", saltnado.MinionSaltAPIHandler),
            (r"/minions", saltnado.MinionSaltAPIHandler),
        ]
        application = self.build_tornado_app(urls)
        application.event_listener = saltnado.EventListener({}, self.opts)
        return application

    def test_get_no_mid(self):
        response = self.fetch(
            "/minions",
            method="GET",
            headers={saltnado.AUTH_TOKEN_HEADER: self.token["token"]},
            follow_redirects=False,
        )
        response_obj = salt.utils.json.loads(response.body)
        self.assertEqual(len(response_obj["return"]), 1)
        # one per minion
        self.assertEqual(len(response_obj["return"][0]), 2)
        # check a single grain
        for minion_id, grains in response_obj["return"][0].items():
            self.assertEqual(minion_id, grains["id"])

    @pytest.mark.slow_test
    def test_get(self):
        response = self.fetch(
            "/minions/minion",
            method="GET",
            headers={saltnado.AUTH_TOKEN_HEADER: self.token["token"]},
            follow_redirects=False,
        )
        response_obj = salt.utils.json.loads(response.body)
        self.assertEqual(len(response_obj["return"]), 1)
        self.assertEqual(len(response_obj["return"][0]), 1)
        # check a single grain
        self.assertEqual(response_obj["return"][0]["minion"]["id"], "minion")

    def test_post(self):
        low = [{"tgt": "*minion", "fun": "test.ping"}]
        response = self.fetch(
            "/minions",
            method="POST",
            body=salt.utils.json.dumps(low),
            headers={
                "Content-Type": self.content_type_map["json"],
                saltnado.AUTH_TOKEN_HEADER: self.token["token"],
            },
        )

        response_obj = salt.utils.json.loads(response.body)
        ret = response_obj["return"]
        ret[0]["minions"] = sorted(ret[0]["minions"])

        # TODO: verify pub function? Maybe look at how we test the publisher
        self.assertEqual(len(ret), 1)
        self.assertIn("jid", ret[0])
        self.assertEqual(ret[0]["minions"], sorted(["minion", "sub_minion"]))

    @pytest.mark.slow_test
    def test_post_with_client(self):
        # get a token for this test
        low = [{"client": "local_async", "tgt": "*minion", "fun": "test.ping"}]
        response = self.fetch(
            "/minions",
            method="POST",
            body=salt.utils.json.dumps(low),
            headers={
                "Content-Type": self.content_type_map["json"],
                saltnado.AUTH_TOKEN_HEADER: self.token["token"],
            },
        )

        response_obj = salt.utils.json.loads(response.body)
        ret = response_obj["return"]
        ret[0]["minions"] = sorted(ret[0]["minions"])

        # TODO: verify pub function? Maybe look at how we test the publisher
        self.assertEqual(len(ret), 1)
        self.assertIn("jid", ret[0])
        self.assertEqual(ret[0]["minions"], sorted(["minion", "sub_minion"]))

    @pytest.mark.slow_test
    def test_post_with_incorrect_client(self):
        """
        The /minions endpoint is asynchronous only, so if you try something else
        make sure you get an error
        """
        # get a token for this test
        low = [{"client": "local", "tgt": "*", "fun": "test.ping"}]
        response = self.fetch(
            "/minions",
            method="POST",
            body=salt.utils.json.dumps(low),
            headers={
                "Content-Type": self.content_type_map["json"],
                saltnado.AUTH_TOKEN_HEADER: self.token["token"],
            },
        )
        self.assertEqual(response.code, 400)


class TestJobsSaltAPIHandler(SaltnadoIntegrationTestsBase):
    def get_app(self):
        urls = [
            (r"/jobs/(.*)", saltnado.JobsSaltAPIHandler),
            (r"/jobs", saltnado.JobsSaltAPIHandler),
        ]
        application = self.build_tornado_app(urls)
        application.event_listener = saltnado.EventListener({}, self.opts)
        return application

    @pytest.mark.slow_test
    def test_get(self):
        # test with no JID
        self.http_client.fetch(
            self.get_url("/jobs"),
            self.stop,
            method="GET",
            headers={saltnado.AUTH_TOKEN_HEADER: self.token["token"]},
            follow_redirects=False,
        )
        response = self.wait(timeout=30)
        response_obj = salt.utils.json.loads(response.body)["return"][0]
        try:
            for jid, ret in response_obj.items():
                self.assertIn("Function", ret)
                self.assertIn("Target", ret)
                self.assertIn("Target-type", ret)
                self.assertIn("User", ret)
                self.assertIn("StartTime", ret)
                self.assertIn("Arguments", ret)
        except AttributeError as attribute_error:
            print(salt.utils.json.loads(response.body))
            raise

        # test with a specific JID passed in
        jid = next(iter(response_obj.keys()))
        self.http_client.fetch(
            self.get_url("/jobs/{}".format(jid)),
            self.stop,
            method="GET",
            headers={saltnado.AUTH_TOKEN_HEADER: self.token["token"]},
            follow_redirects=False,
        )
        response = self.wait(timeout=30)
        response_obj = salt.utils.json.loads(response.body)["return"][0]
        self.assertIn("Function", response_obj)
        self.assertIn("Target", response_obj)
        self.assertIn("Target-type", response_obj)
        self.assertIn("User", response_obj)
        self.assertIn("StartTime", response_obj)
        self.assertIn("Arguments", response_obj)
        self.assertIn("Result", response_obj)


# TODO: run all the same tests from the root handler, but for now since they are
# the same code, we'll just sanity check
class TestRunSaltAPIHandler(SaltnadoIntegrationTestsBase):
    def get_app(self):
        urls = [
            ("/run", saltnado.RunSaltAPIHandler),
        ]
        application = self.build_tornado_app(urls)
        application.event_listener = saltnado.EventListener({}, self.opts)
        return application

    @pytest.mark.slow_test
    def test_get(self):
        low = [{"client": "local", "tgt": "*", "fun": "test.ping"}]
        response = self.fetch(
            "/run",
            method="POST",
            body=salt.utils.json.dumps(low),
            headers={
                "Content-Type": self.content_type_map["json"],
                saltnado.AUTH_TOKEN_HEADER: self.token["token"],
            },
        )
        response_obj = salt.utils.json.loads(response.body)
        self.assertEqual(response_obj["return"], [{"minion": True, "sub_minion": True}])


class TestEventsSaltAPIHandler(SaltnadoIntegrationTestsBase):
    def get_app(self):
        urls = [
            (r"/events", saltnado.EventsSaltAPIHandler),
        ]
        application = self.build_tornado_app(urls)
        application.event_listener = saltnado.EventListener({}, self.opts)

        # store a reference, for magic later!
        self.application = application
        self.events_to_fire = 0
        return application

    @pytest.mark.slow_test
    def test_get(self):
        self.events_to_fire = 5
        response = self.fetch(
            "/events",
            headers={saltnado.AUTH_TOKEN_HEADER: self.token["token"]},
            streaming_callback=self.on_event,
        )

    def _stop(self):
        self.stop()

    def on_event(self, event):
        event = event.decode("utf-8")
        if self.events_to_fire > 0:
            self.application.event_listener.event.fire_event(
                {"foo": "bar", "baz": "qux"}, "salt/netapi/test"
            )
            self.events_to_fire -= 1
        # once we've fired all the events, lets call it a day
        else:
            # wait so that we can ensure that the next future is ready to go
            # to make sure we don't explode if the next one is ready
            salt.ext.tornado.ioloop.IOLoop.current().add_timeout(
                time.time() + 0.5, self._stop
            )

        event = event.strip()
        # if we got a retry, just continue
        if event != "retry: 400":
            tag, data = event.splitlines()
            self.assertTrue(tag.startswith("tag: "))
            self.assertTrue(data.startswith("data: "))


class TestWebhookSaltAPIHandler(SaltnadoIntegrationTestsBase):
    def get_app(self):

        urls = [
            (r"/hook(/.*)?", saltnado.WebhookSaltAPIHandler),
        ]

        application = self.build_tornado_app(urls)

        self.application = application

        application.event_listener = saltnado.EventListener({}, self.opts)
        return application

    @skipIf(True, "Skipping until we can devote more resources to debugging this test.")
    def test_post(self):
        self._future_resolved = threading.Event()
        try:

            def verify_event(future):
                """
                Notify the threading event that the future is resolved
                """
                self._future_resolved.set()

            self._finished = (
                False  # TODO: remove after some cleanup of the event listener
            )

            # get an event future
            future = self.application.event_listener.get_event(
                self, tag="salt/netapi/hook", callback=verify_event
            )
            # fire the event
            response = self.fetch(
                "/hook",
                method="POST",
                body="foo=bar",
                headers={saltnado.AUTH_TOKEN_HEADER: self.token["token"]},
            )
            response_obj = salt.utils.json.loads(response.body)
            self.assertTrue(response_obj["success"])
            resolve_future_timeout = 60
            self._future_resolved.wait(resolve_future_timeout)
            try:
                event = future.result()
            except Exception as exc:  # pylint: disable=broad-except
                self.fail(
                    "Failed to resolve future under {} secs: {}".format(
                        resolve_future_timeout, exc
                    )
                )
            self.assertEqual(event["tag"], "salt/netapi/hook")
            self.assertIn("headers", event["data"])
            self.assertEqual(event["data"]["post"], {"foo": "bar"})
        finally:
            self._future_resolved.clear()
            del self._future_resolved
