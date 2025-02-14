import os
import threading
import time

import pytest

import salt.auth
import salt.ext.tornado.escape
import salt.ext.tornado.web
import salt.utils.json
import salt.utils.stringutils
from salt.ext.tornado.testing import AsyncHTTPTestCase
from salt.netapi.rest_tornado import saltnado
from tests.support.helpers import TstSuiteLoggingHandler, patched_environ
from tests.support.mixins import AdaptedConfigurationTestCaseMixin


@pytest.fixture(scope="module", autouse=True)
def salt_api_account(salt_api_account_factory):
    with salt_api_account_factory as account:
        yield account


class SaltnadoIntegrationTestsBase(
    AsyncHTTPTestCase, AdaptedConfigurationTestCaseMixin
):

    content_type_map = {
        "json": "application/json",
        "json-utf8": "application/json; charset=utf-8",
        "yaml": "application/x-yaml",
        "text": "text/plain",
        "form": "application/x-www-form-urlencoded",
        "xml": "application/xml",
        "real-accept-header-json": "application/json, text/javascript, */*; q=0.01",
        "real-accept-header-yaml": "application/x-yaml, text/yaml, */*; q=0.01",
    }
    auth_creds = (
        ("username", "saltdev_api"),
        ("password", "saltdev"),
        ("eauth", "auto"),
    )

    @property
    def auth_creds_dict(self):
        return dict(self.auth_creds)

    @property
    def opts(self):
        return self.get_temp_config("client_config")

    @property
    def mod_opts(self):
        return self.get_temp_config("minion")

    @property
    def auth(self):
        if not hasattr(self, "__auth"):
            self.__auth = salt.auth.LoadAuth(self.opts)
        return self.__auth

    @property
    def token(self):
        """Mint and return a valid token for auth_creds"""
        return self.auth.mk_token(self.auth_creds_dict)

    def setUp(self):
        super().setUp()
        self.patched_environ = patched_environ(ASYNC_TEST_TIMEOUT="30")
        self.patched_environ.__enter__()  # pylint: disable=unnecessary-dunder-call
        self.addCleanup(self.patched_environ.__exit__)

    def tearDown(self):
        super().tearDown()
        if hasattr(self, "http_server"):
            del self.http_server
        if hasattr(self, "io_loop"):
            del self.io_loop
        if hasattr(self, "_app"):
            del self._app
        if hasattr(self, "http_client"):
            del self.http_client
        if hasattr(self, "__port"):
            del self.__port
        if hasattr(self, "_AsyncHTTPTestCase__port"):
            del self._AsyncHTTPTestCase__port
        if hasattr(self, "__auth"):
            del self.__auth
        if hasattr(self, "_SaltnadoIntegrationTestsBase__auth"):
            del self._SaltnadoIntegrationTestsBase__auth
        if hasattr(self, "_test_generator"):
            del self._test_generator
        if hasattr(self, "application"):
            del self.application
        if hasattr(self, "patched_environ"):
            del self.patched_environ

    def build_tornado_app(self, urls):
        application = salt.ext.tornado.web.Application(urls, debug=True)

        application.auth = self.auth
        application.opts = self.opts
        application.mod_opts = self.mod_opts

        return application

    def decode_body(self, response):
        if response is None:
            return response
        if response.body:
            # Decode it
            if response.headers.get("Content-Type") == "application/json":
                response._body = response.body.decode("utf-8")
            else:
                response._body = salt.ext.tornado.escape.native_str(response.body)
        return response

    def fetch(self, path, **kwargs):
        return self.decode_body(super().fetch(path, **kwargs))

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

    @pytest.mark.skip(
        reason="Undetermined race condition in test. Temporarily disabled."
    )
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


class TestWebhookSaltAPIHandler(SaltnadoIntegrationTestsBase):
    def get_app(self):

        urls = [
            (r"/hook(/.*)?", saltnado.WebhookSaltAPIHandler),
        ]

        application = self.build_tornado_app(urls)

        self.application = application

        application.event_listener = saltnado.EventListener({}, self.opts)
        return application

    @pytest.mark.skip(
        reason="Skipping until we can devote more resources to debugging this test."
    )
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
