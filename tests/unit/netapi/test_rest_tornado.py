# coding: utf-8

# Import Python libs
from __future__ import absolute_import

import copy
import hashlib
import os
import shutil

# Import Salt libs
import salt.auth
import salt.utils.event
import salt.utils.json
import salt.utils.yaml
from salt.ext import six
from salt.ext.six.moves import map, range  # pylint: disable=import-error
from salt.ext.six.moves.urllib.parse import (  # pylint: disable=no-name-in-module
    urlencode,
    urlparse,
)
from tests.support.events import eventpublisher_process
from tests.support.helpers import patched_environ

# Import Salt Testing Libs
from tests.support.mixins import AdaptedConfigurationTestCaseMixin
from tests.support.mock import MagicMock, patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase, skipIf

try:
    HAS_TORNADO = True
except ImportError:
    HAS_TORNADO = False

# Import 3rd-party libs
# pylint: disable=import-error
try:
    import salt.ext.tornado.escape
    import salt.ext.tornado.testing
    import salt.ext.tornado.concurrent
    from salt.ext.tornado.testing import AsyncTestCase, AsyncHTTPTestCase, gen_test
    from salt.ext.tornado.httpclient import HTTPRequest, HTTPError
    from salt.ext.tornado.websocket import websocket_connect
    import salt.netapi.rest_tornado as rest_tornado
    from salt.netapi.rest_tornado import saltnado

    HAS_TORNADO = True
except ImportError:
    HAS_TORNADO = False

    # Create fake test case classes so we can properly skip the test case
    class AsyncTestCase(object):
        pass

    class AsyncHTTPTestCase(object):
        pass


# pylint: enable=import-error


@skipIf(
    not HAS_TORNADO, "The tornado package needs to be installed"
)  # pylint: disable=W0223
class SaltnadoTestCase(TestCase, AdaptedConfigurationTestCaseMixin, AsyncHTTPTestCase):
    """
    Mixin to hold some shared things
    """

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
        """ Mint and return a valid token for auth_creds """
        return self.auth.mk_token(self.auth_creds_dict)

    def setUp(self):
        super(SaltnadoTestCase, self).setUp()
        self.patched_environ = patched_environ(ASYNC_TEST_TIMEOUT="30")
        self.patched_environ.__enter__()
        self.addCleanup(self.patched_environ.__exit__)

    def tearDown(self):
        super(SaltnadoTestCase, self).tearDown()
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
        if hasattr(self, "_SaltnadoTestCase__auth"):
            del self._SaltnadoTestCase__auth
        if hasattr(self, "_test_generator"):
            del self._test_generator
        if hasattr(self, "application"):
            del self.application

    def build_tornado_app(self, urls):
        application = salt.ext.tornado.web.Application(urls, debug=True)

        application.auth = self.auth
        application.opts = self.opts
        application.mod_opts = self.mod_opts

        return application

    def decode_body(self, response):
        if response is None:
            return response
        if six.PY2:
            return response
        if response.body:
            # Decode it
            if response.headers.get("Content-Type") == "application/json":
                response._body = response.body.decode("utf-8")
            else:
                response._body = salt.ext.tornado.escape.native_str(response.body)
        return response

    def fetch(self, path, **kwargs):
        return self.decode_body(super(SaltnadoTestCase, self).fetch(path, **kwargs))


class TestBaseSaltAPIHandler(SaltnadoTestCase):
    def get_app(self):
        class StubHandler(saltnado.BaseSaltAPIHandler):  # pylint: disable=W0223
            def get(self, *args, **kwargs):
                return self.echo_stuff()

            def post(self):  # pylint: disable=arguments-differ
                return self.echo_stuff()

            def echo_stuff(self):
                ret_dict = {"foo": "bar"}
                attrs = (
                    "token",
                    "start",
                    "connected",
                    "lowstate",
                )
                for attr in attrs:
                    ret_dict[attr] = getattr(self, attr)

                self.write(self.serialize(ret_dict))

        urls = [("/", StubHandler), ("/(.*)", StubHandler)]
        return self.build_tornado_app(urls)

    def test_accept_content_type(self):
        """
        Test the base handler's accept picking
        """

        # send NO accept header, should come back with json
        response = self.fetch("/")
        self.assertEqual(
            response.headers["Content-Type"], self.content_type_map["json"]
        )
        self.assertEqual(type(salt.utils.json.loads(response.body)), dict)

        # Request application/json
        response = self.fetch("/", headers={"Accept": self.content_type_map["json"]})
        self.assertEqual(
            response.headers["Content-Type"], self.content_type_map["json"]
        )
        self.assertEqual(type(salt.utils.json.loads(response.body)), dict)

        # Request application/x-yaml
        response = self.fetch("/", headers={"Accept": self.content_type_map["yaml"]})
        self.assertEqual(
            response.headers["Content-Type"], self.content_type_map["yaml"]
        )
        self.assertEqual(type(salt.utils.yaml.safe_load(response.body)), dict)

        # Request not supported content-type
        response = self.fetch("/", headers={"Accept": self.content_type_map["xml"]})
        self.assertEqual(response.code, 406)

        # Request some JSON with a browser like Accept
        accept_header = self.content_type_map["real-accept-header-json"]
        response = self.fetch("/", headers={"Accept": accept_header})
        self.assertEqual(
            response.headers["Content-Type"], self.content_type_map["json"]
        )
        self.assertEqual(type(salt.utils.json.loads(response.body)), dict)

        # Request some YAML with a browser like Accept
        accept_header = self.content_type_map["real-accept-header-yaml"]
        response = self.fetch("/", headers={"Accept": accept_header})
        self.assertEqual(
            response.headers["Content-Type"], self.content_type_map["yaml"]
        )
        self.assertEqual(type(salt.utils.yaml.safe_load(response.body)), dict)

    def test_token(self):
        """
        Test that the token is returned correctly
        """
        token = salt.utils.json.loads(self.fetch("/").body)["token"]
        self.assertIs(token, None)

        # send a token as a header
        response = self.fetch("/", headers={saltnado.AUTH_TOKEN_HEADER: "foo"})
        token = salt.utils.json.loads(response.body)["token"]
        self.assertEqual(token, "foo")

        # send a token as a cookie
        response = self.fetch(
            "/", headers={"Cookie": "{0}=foo".format(saltnado.AUTH_COOKIE_NAME)}
        )
        token = salt.utils.json.loads(response.body)["token"]
        self.assertEqual(token, "foo")

        # send both, make sure its the header
        response = self.fetch(
            "/",
            headers={
                saltnado.AUTH_TOKEN_HEADER: "foo",
                "Cookie": "{0}=bar".format(saltnado.AUTH_COOKIE_NAME),
            },
        )
        token = salt.utils.json.loads(response.body)["token"]
        self.assertEqual(token, "foo")

    def test_deserialize(self):
        """
        Send various encoded forms of lowstates (and bad ones) to make sure we
        handle deserialization correctly
        """
        valid_lowstate = [
            {"client": "local", "tgt": "*", "fun": "test.fib", "arg": ["10"]},
            {
                "client": "runner",
                "fun": "jobs.lookup_jid",
                "jid": "20130603122505459265",
            },
        ]

        # send as JSON
        response = self.fetch(
            "/",
            method="POST",
            body=salt.utils.json.dumps(valid_lowstate),
            headers={"Content-Type": self.content_type_map["json"]},
        )

        self.assertEqual(
            valid_lowstate, salt.utils.json.loads(response.body)["lowstate"]
        )

        # send yaml as json (should break)
        response = self.fetch(
            "/",
            method="POST",
            body=salt.utils.yaml.safe_dump(valid_lowstate),
            headers={"Content-Type": self.content_type_map["json"]},
        )
        self.assertEqual(response.code, 400)

        # send as yaml
        response = self.fetch(
            "/",
            method="POST",
            body=salt.utils.yaml.safe_dump(valid_lowstate),
            headers={"Content-Type": self.content_type_map["yaml"]},
        )
        self.assertEqual(
            valid_lowstate, salt.utils.json.loads(response.body)["lowstate"]
        )

        # send json as yaml (works since yaml is a superset of json)
        response = self.fetch(
            "/",
            method="POST",
            body=salt.utils.json.dumps(valid_lowstate),
            headers={"Content-Type": self.content_type_map["yaml"]},
        )
        self.assertEqual(
            valid_lowstate, salt.utils.json.loads(response.body)["lowstate"]
        )

        # send json as text/plain
        response = self.fetch(
            "/",
            method="POST",
            body=salt.utils.json.dumps(valid_lowstate),
            headers={"Content-Type": self.content_type_map["text"]},
        )
        self.assertEqual(
            valid_lowstate, salt.utils.json.loads(response.body)["lowstate"]
        )

        # send form-urlencoded
        form_lowstate = (
            ("client", "local"),
            ("tgt", "*"),
            ("fun", "test.fib"),
            ("arg", "10"),
            ("arg", "foo"),
        )
        response = self.fetch(
            "/",
            method="POST",
            body=urlencode(form_lowstate),
            headers={"Content-Type": self.content_type_map["form"]},
        )
        returned_lowstate = salt.utils.json.loads(response.body)["lowstate"]
        self.assertEqual(len(returned_lowstate), 1)
        returned_lowstate = returned_lowstate[0]

        self.assertEqual(returned_lowstate["client"], "local")
        self.assertEqual(returned_lowstate["tgt"], "*")
        self.assertEqual(returned_lowstate["fun"], "test.fib")
        self.assertEqual(returned_lowstate["arg"], ["10", "foo"])

        # Send json with utf8 charset
        response = self.fetch(
            "/",
            method="POST",
            body=salt.utils.json.dumps(valid_lowstate),
            headers={"Content-Type": self.content_type_map["json-utf8"]},
        )
        self.assertEqual(
            valid_lowstate, salt.utils.json.loads(response.body)["lowstate"]
        )

    def test_get_lowstate(self):
        """
        Test transformations low data of the function _get_lowstate
        """
        valid_lowstate = [
            {u"client": u"local", u"tgt": u"*", u"fun": u"test.fib", u"arg": [u"10"]}
        ]

        # Case 1. dictionary type of lowstate
        request_lowstate = {
            "client": "local",
            "tgt": "*",
            "fun": "test.fib",
            "arg": ["10"],
        }

        response = self.fetch(
            "/",
            method="POST",
            body=salt.utils.json.dumps(request_lowstate),
            headers={"Content-Type": self.content_type_map["json"]},
        )

        self.assertEqual(
            valid_lowstate, salt.utils.json.loads(response.body)["lowstate"]
        )

        # Case 2. string type of arg
        request_lowstate = {
            "client": "local",
            "tgt": "*",
            "fun": "test.fib",
            "arg": "10",
        }

        response = self.fetch(
            "/",
            method="POST",
            body=salt.utils.json.dumps(request_lowstate),
            headers={"Content-Type": self.content_type_map["json"]},
        )

        self.assertEqual(
            valid_lowstate, salt.utils.json.loads(response.body)["lowstate"]
        )

        # Case 3. Combine Case 1 and Case 2.
        request_lowstate = {
            "client": "local",
            "tgt": "*",
            "fun": "test.fib",
            "arg": "10",
        }

        # send as json
        response = self.fetch(
            "/",
            method="POST",
            body=salt.utils.json.dumps(request_lowstate),
            headers={"Content-Type": self.content_type_map["json"]},
        )

        self.assertEqual(
            valid_lowstate, salt.utils.json.loads(response.body)["lowstate"]
        )

        # send as yaml
        response = self.fetch(
            "/",
            method="POST",
            body=salt.utils.yaml.safe_dump(request_lowstate),
            headers={"Content-Type": self.content_type_map["yaml"]},
        )
        self.assertEqual(
            valid_lowstate, salt.utils.json.loads(response.body)["lowstate"]
        )

        # send as plain text
        response = self.fetch(
            "/",
            method="POST",
            body=salt.utils.json.dumps(request_lowstate),
            headers={"Content-Type": self.content_type_map["text"]},
        )
        self.assertEqual(
            valid_lowstate, salt.utils.json.loads(response.body)["lowstate"]
        )

        # send as form-urlencoded
        request_form_lowstate = (
            ("client", "local"),
            ("tgt", "*"),
            ("fun", "test.fib"),
            ("arg", "10"),
        )

        response = self.fetch(
            "/",
            method="POST",
            body=urlencode(request_form_lowstate),
            headers={"Content-Type": self.content_type_map["form"]},
        )
        self.assertEqual(
            valid_lowstate, salt.utils.json.loads(response.body)["lowstate"]
        )

    def test_cors_origin_wildcard(self):
        """
        Check that endpoints returns Access-Control-Allow-Origin
        """
        self._app.mod_opts["cors_origin"] = "*"

        headers = self.fetch("/").headers
        self.assertEqual(headers["Access-Control-Allow-Origin"], "*")

    def test_cors_origin_single(self):
        """
        Check that endpoints returns the Access-Control-Allow-Origin when
        only one origins is set
        """
        self._app.mod_opts["cors_origin"] = "http://example.foo"

        # Example.foo is an authorized origin
        headers = self.fetch("/", headers={"Origin": "http://example.foo"}).headers
        self.assertEqual(headers["Access-Control-Allow-Origin"], "http://example.foo")

        # Example2.foo is not an authorized origin
        headers = self.fetch("/", headers={"Origin": "http://example2.foo"}).headers
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), None)

    def test_cors_origin_multiple(self):
        """
        Check that endpoints returns the Access-Control-Allow-Origin when
        multiple origins are set
        """
        self._app.mod_opts["cors_origin"] = ["http://example.foo", "http://foo.example"]

        # Example.foo is an authorized origin
        headers = self.fetch("/", headers={"Origin": "http://example.foo"}).headers
        self.assertEqual(headers["Access-Control-Allow-Origin"], "http://example.foo")

        # Example2.foo is not an authorized origin
        headers = self.fetch("/", headers={"Origin": "http://example2.foo"}).headers
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), None)

    def test_cors_preflight_request(self):
        """
        Check that preflight request contains right headers
        """
        self._app.mod_opts["cors_origin"] = "*"

        request_headers = "X-Auth-Token, accept, content-type"
        preflight_headers = {
            "Access-Control-Request-Headers": request_headers,
            "Access-Control-Request-Method": "GET",
        }

        response = self.fetch("/", method="OPTIONS", headers=preflight_headers)
        headers = response.headers

        self.assertEqual(response.code, 204)
        self.assertEqual(headers["Access-Control-Allow-Headers"], request_headers)
        self.assertEqual(headers["Access-Control-Expose-Headers"], "X-Auth-Token")
        self.assertEqual(headers["Access-Control-Allow-Methods"], "OPTIONS, GET, POST")

        self.assertEqual(response.code, 204)

    def test_cors_origin_url_with_arguments(self):
        """
        Check that preflight requests works with url with components
        like jobs or minions endpoints.
        """
        self._app.mod_opts["cors_origin"] = "*"

        request_headers = "X-Auth-Token, accept, content-type"
        preflight_headers = {
            "Access-Control-Request-Headers": request_headers,
            "Access-Control-Request-Method": "GET",
        }
        response = self.fetch(
            "/1234567890", method="OPTIONS", headers=preflight_headers
        )
        headers = response.headers

        self.assertEqual(response.code, 204)
        self.assertEqual(headers["Access-Control-Allow-Origin"], "*")


class TestWebhookSaltHandler(SaltnadoTestCase):
    def get_app(self):
        urls = [
            (r"/hook(/.*)?", saltnado.WebhookSaltAPIHandler),
        ]
        return self.build_tornado_app(urls)

    def test_hook_can_handle_get_parameters(self):
        with patch("salt.utils.event.get_event") as get_event:
            with patch.dict(self._app.mod_opts, {"webhook_disable_auth": True}):
                event = MagicMock()
                event.fire_event.return_value = True
                get_event.return_value = event
                response = self.fetch(
                    "/hook/my_service/?param=1&param=2",
                    body=salt.utils.json.dumps({}),
                    method="POST",
                    headers={"Content-Type": self.content_type_map["json"]},
                )
                self.assertEqual(response.code, 200, response.body)
                host = urlparse(response.effective_url).netloc
                event.fire_event.assert_called_once_with(
                    {
                        "headers": {
                            "Content-Length": "2",
                            "Connection": "close",
                            "Content-Type": "application/json",
                            "Host": host,
                            "Accept-Encoding": "gzip",
                        },
                        "post": {},
                        "get": {"param": ["1", "2"]},
                    },
                    "salt/netapi/hook/my_service/",
                )


class TestSaltAuthHandler(SaltnadoTestCase):
    def get_app(self):
        urls = [("/login", saltnado.SaltAuthHandler)]
        return self.build_tornado_app(urls)

    def test_get(self):
        """
        We don't allow gets, so assert we get 401s
        """
        response = self.fetch("/login")
        self.assertEqual(response.code, 401)

    def test_login(self):
        """
        Test valid logins
        """
        # Test in form encoded
        response = self.fetch(
            "/login",
            method="POST",
            body=urlencode(self.auth_creds),
            headers={"Content-Type": self.content_type_map["form"]},
        )

        cookies = response.headers["Set-Cookie"]
        self.assertEqual(response.code, 200)
        response_obj = salt.utils.json.loads(response.body)["return"][0]
        token = response_obj["token"]
        self.assertIn("session_id={0}".format(token), cookies)
        self.assertEqual(
            sorted(response_obj["perms"]),
            sorted(
                self.opts["external_auth"]["auto"][self.auth_creds_dict["username"]]
            ),
        )
        self.assertIn("token", response_obj)  # TODO: verify that its valid?
        self.assertEqual(response_obj["user"], self.auth_creds_dict["username"])
        self.assertEqual(response_obj["eauth"], self.auth_creds_dict["eauth"])

        # Test in JSON
        response = self.fetch(
            "/login",
            method="POST",
            body=salt.utils.json.dumps(self.auth_creds_dict),
            headers={"Content-Type": self.content_type_map["json"]},
        )

        cookies = response.headers["Set-Cookie"]
        self.assertEqual(response.code, 200)
        response_obj = salt.utils.json.loads(response.body)["return"][0]
        token = response_obj["token"]
        self.assertIn("session_id={0}".format(token), cookies)
        self.assertEqual(
            sorted(response_obj["perms"]),
            sorted(
                self.opts["external_auth"]["auto"][self.auth_creds_dict["username"]]
            ),
        )
        self.assertIn("token", response_obj)  # TODO: verify that its valid?
        self.assertEqual(response_obj["user"], self.auth_creds_dict["username"])
        self.assertEqual(response_obj["eauth"], self.auth_creds_dict["eauth"])

        # Test in YAML
        response = self.fetch(
            "/login",
            method="POST",
            body=salt.utils.yaml.safe_dump(self.auth_creds_dict),
            headers={"Content-Type": self.content_type_map["yaml"]},
        )

        cookies = response.headers["Set-Cookie"]
        self.assertEqual(response.code, 200)
        response_obj = salt.utils.json.loads(response.body)["return"][0]
        token = response_obj["token"]
        self.assertIn("session_id={0}".format(token), cookies)
        self.assertEqual(
            sorted(response_obj["perms"]),
            sorted(
                self.opts["external_auth"]["auto"][self.auth_creds_dict["username"]]
            ),
        )
        self.assertIn("token", response_obj)  # TODO: verify that its valid?
        self.assertEqual(response_obj["user"], self.auth_creds_dict["username"])
        self.assertEqual(response_obj["eauth"], self.auth_creds_dict["eauth"])

    def test_login_missing_password(self):
        """
        Test logins with bad/missing passwords
        """
        bad_creds = []
        for key, val in six.iteritems(self.auth_creds_dict):
            if key == "password":
                continue
            bad_creds.append((key, val))
        response = self.fetch(
            "/login",
            method="POST",
            body=urlencode(bad_creds),
            headers={"Content-Type": self.content_type_map["form"]},
        )

        self.assertEqual(response.code, 400)

    def test_login_bad_creds(self):
        """
        Test logins with bad/missing passwords
        """
        bad_creds = []
        for key, val in six.iteritems(self.auth_creds_dict):
            if key == "username":
                val = val + "foo"
            if key == "eauth":
                val = "sharedsecret"
            bad_creds.append((key, val))

        response = self.fetch(
            "/login",
            method="POST",
            body=urlencode(bad_creds),
            headers={"Content-Type": self.content_type_map["form"]},
        )

        self.assertEqual(response.code, 401)

    def test_login_invalid_data_structure(self):
        """
        Test logins with either list or string JSON payload
        """
        response = self.fetch(
            "/login",
            method="POST",
            body=salt.utils.json.dumps(self.auth_creds),
            headers={"Content-Type": self.content_type_map["form"]},
        )

        self.assertEqual(response.code, 400)

        response = self.fetch(
            "/login",
            method="POST",
            body=salt.utils.json.dumps(42),
            headers={"Content-Type": self.content_type_map["form"]},
        )

        self.assertEqual(response.code, 400)

        response = self.fetch(
            "/login",
            method="POST",
            body=salt.utils.json.dumps("mystring42"),
            headers={"Content-Type": self.content_type_map["form"]},
        )

        self.assertEqual(response.code, 400)


class TestSaltRunHandler(SaltnadoTestCase):
    def get_app(self):
        urls = [("/run", saltnado.RunSaltAPIHandler)]
        return self.build_tornado_app(urls)

    def test_authentication_exception_consistency(self):
        """
        Test consistency of authentication exception of each clients.
        """
        valid_response = {"return": ["Failed to authenticate"]}

        clients = ["local", "local_async", "runner", "runner_async"]
        request_lowstates = map(
            lambda client: {
                "client": client,
                "tgt": "*",
                "fun": "test.fib",
                "arg": ["10"],
            },
            clients,
        )

        for request_lowstate in request_lowstates:
            response = self.fetch(
                "/run",
                method="POST",
                body=salt.utils.json.dumps(request_lowstate),
                headers={"Content-Type": self.content_type_map["json"]},
            )

            self.assertEqual(valid_response, salt.utils.json.loads(response.body))


@skipIf(
    not HAS_TORNADO, "The tornado package needs to be installed"
)  # pylint: disable=W0223
class TestWebsocketSaltAPIHandler(SaltnadoTestCase):
    def get_app(self):
        opts = copy.deepcopy(self.opts)
        opts.setdefault("rest_tornado", {})["websockets"] = True
        return rest_tornado.get_application(opts)

    @gen_test
    def test_websocket_handler_upgrade_to_websocket(self):
        response = yield self.http_client.fetch(
            self.get_url("/login"),
            method="POST",
            body=urlencode(self.auth_creds),
            headers={"Content-Type": self.content_type_map["form"]},
        )
        token = salt.utils.json.loads(self.decode_body(response).body)["return"][0][
            "token"
        ]

        url = "ws://127.0.0.1:{0}/all_events/{1}".format(self.get_http_port(), token)
        request = HTTPRequest(
            url, headers={"Origin": "http://example.com", "Host": "example.com"}
        )
        ws = yield websocket_connect(request)
        ws.write_message("websocket client ready")
        ws.close()

    @gen_test
    def test_websocket_handler_bad_token(self):
        """
        A bad token should returns a 401 during a websocket connect
        """
        token = "A" * len(
            getattr(hashlib, self.opts.get("hash_type", "md5"))().hexdigest()
        )

        url = "ws://127.0.0.1:{0}/all_events/{1}".format(self.get_http_port(), token)
        request = HTTPRequest(
            url, headers={"Origin": "http://example.com", "Host": "example.com"}
        )
        try:
            ws = yield websocket_connect(request)
        except HTTPError as error:
            self.assertEqual(error.code, 401)

    @gen_test
    def test_websocket_handler_cors_origin_wildcard(self):
        self._app.mod_opts["cors_origin"] = "*"

        response = yield self.http_client.fetch(
            self.get_url("/login"),
            method="POST",
            body=urlencode(self.auth_creds),
            headers={"Content-Type": self.content_type_map["form"]},
        )
        token = salt.utils.json.loads(self.decode_body(response).body)["return"][0][
            "token"
        ]

        url = "ws://127.0.0.1:{0}/all_events/{1}".format(self.get_http_port(), token)
        request = HTTPRequest(
            url, headers={"Origin": "http://foo.bar", "Host": "example.com"}
        )
        ws = yield websocket_connect(request)
        ws.write_message("websocket client ready")
        ws.close()

    @gen_test
    def test_cors_origin_single(self):
        self._app.mod_opts["cors_origin"] = "http://example.com"

        response = yield self.http_client.fetch(
            self.get_url("/login"),
            method="POST",
            body=urlencode(self.auth_creds),
            headers={"Content-Type": self.content_type_map["form"]},
        )
        token = salt.utils.json.loads(self.decode_body(response).body)["return"][0][
            "token"
        ]
        url = "ws://127.0.0.1:{0}/all_events/{1}".format(self.get_http_port(), token)

        # Example.com should works
        request = HTTPRequest(
            url, headers={"Origin": "http://example.com", "Host": "example.com"}
        )
        ws = yield websocket_connect(request)
        ws.write_message("websocket client ready")
        ws.close()

        # But foo.bar not
        request = HTTPRequest(
            url, headers={"Origin": "http://foo.bar", "Host": "example.com"}
        )
        try:
            ws = yield websocket_connect(request)
        except HTTPError as error:
            self.assertEqual(error.code, 403)

    @gen_test
    def test_cors_origin_multiple(self):
        self._app.mod_opts["cors_origin"] = ["http://example.com", "http://foo.bar"]

        response = yield self.http_client.fetch(
            self.get_url("/login"),
            method="POST",
            body=urlencode(self.auth_creds),
            headers={"Content-Type": self.content_type_map["form"]},
        )
        token = salt.utils.json.loads(self.decode_body(response).body)["return"][0][
            "token"
        ]
        url = "ws://127.0.0.1:{0}/all_events/{1}".format(self.get_http_port(), token)

        # Example.com should works
        request = HTTPRequest(
            url, headers={"Origin": "http://example.com", "Host": "example.com"}
        )
        ws = yield websocket_connect(request)
        ws.write_message("websocket client ready")
        ws.close()

        # Foo.bar too
        request = HTTPRequest(
            url, headers={"Origin": "http://foo.bar", "Host": "example.com"}
        )
        ws = yield websocket_connect(request)
        ws.write_message("websocket client ready")
        ws.close()


@skipIf(not HAS_TORNADO, "The tornado package needs to be installed")
class TestSaltnadoUtils(AsyncTestCase):
    def test_any_future(self):
        """
        Test that the Any Future does what we think it does
        """
        # create a few futures
        futures = []
        for x in range(0, 3):
            future = salt.ext.tornado.concurrent.Future()
            future.add_done_callback(self.stop)
            futures.append(future)

        # create an any future, make sure it isn't immediately done
        any_ = saltnado.Any(futures)
        self.assertIs(any_.done(), False)

        # finish one, lets see who finishes
        futures[0].set_result("foo")
        self.wait()

        self.assertIs(any_.done(), True)
        self.assertIs(futures[0].done(), True)
        self.assertIs(futures[1].done(), False)
        self.assertIs(futures[2].done(), False)

        # make sure it returned the one that finished
        self.assertEqual(any_.result(), futures[0])

        futures = futures[1:]
        # re-wait on some other futures
        any_ = saltnado.Any(futures)
        futures[0].set_result("foo")
        self.wait()
        self.assertIs(any_.done(), True)
        self.assertIs(futures[0].done(), True)
        self.assertIs(futures[1].done(), False)


@skipIf(not HAS_TORNADO, "The tornado package needs to be installed")
class TestEventListener(AsyncTestCase):
    def setUp(self):
        self.sock_dir = os.path.join(RUNTIME_VARS.TMP, "test-socks")
        if not os.path.exists(self.sock_dir):
            os.makedirs(self.sock_dir)
        self.addCleanup(shutil.rmtree, self.sock_dir, ignore_errors=True)
        super(TestEventListener, self).setUp()

    def test_simple(self):
        """
        Test getting a few events
        """
        with eventpublisher_process(self.sock_dir):
            me = salt.utils.event.MasterEvent(self.sock_dir)
            event_listener = saltnado.EventListener(
                {},  # we don't use mod_opts, don't save?
                {"sock_dir": self.sock_dir, "transport": "zeromq"},
            )
            self._finished = False  # fit to event_listener's behavior
            event_future = event_listener.get_event(
                self, "evt1", callback=self.stop
            )  # get an event future
            me.fire_event({"data": "foo2"}, "evt2")  # fire an event we don't want
            me.fire_event({"data": "foo1"}, "evt1")  # fire an event we do want
            self.wait()  # wait for the future

            # check that we got the event we wanted
            self.assertTrue(event_future.done())
            self.assertEqual(event_future.result()["tag"], "evt1")
            self.assertEqual(event_future.result()["data"]["data"], "foo1")

    def test_set_event_handler(self):
        """
        Test subscribing events using set_event_handler
        """
        with eventpublisher_process(self.sock_dir):
            me = salt.utils.event.MasterEvent(self.sock_dir)
            event_listener = saltnado.EventListener(
                {},  # we don't use mod_opts, don't save?
                {"sock_dir": self.sock_dir, "transport": "zeromq"},
            )
            self._finished = False  # fit to event_listener's behavior
            event_future = event_listener.get_event(
                self, tag="evt", callback=self.stop, timeout=1,
            )  # get an event future
            me.fire_event({"data": "foo"}, "evt")  # fire an event we do want
            self.wait()

            # check that we subscribed the event we wanted
            self.assertEqual(len(event_listener.timeout_map), 0)

    def test_timeout(self):
        """
        Make sure timeouts work correctly
        """
        with eventpublisher_process(self.sock_dir):
            event_listener = saltnado.EventListener(
                {},  # we don't use mod_opts, don't save?
                {"sock_dir": self.sock_dir, "transport": "zeromq"},
            )
            self._finished = False  # fit to event_listener's behavior
            event_future = event_listener.get_event(
                self, tag="evt1", callback=self.stop, timeout=1,
            )  # get an event future
            self.wait()
            self.assertTrue(event_future.done())
            with self.assertRaises(saltnado.TimeoutException):
                event_future.result()

    def test_clean_by_request(self):
        """
        Make sure the method clean_by_request clean up every related data in EventListener
        request_future_1 : will be timeout-ed by clean_by_request(self)
        request_future_2 : will be finished by me.fire_event ...
        dummy_request_future_1 : will be finished by me.fire_event ...
        dummy_request_future_2 : will be timeout-ed by clean-by_request(dummy_request)
        """

        class DummyRequest(object):
            """
            Dummy request object to simulate the request object
            """

            @property
            def _finished(self):
                """
                Simulate _finished of the request object
                """
                return False

        # Inner functions never permit modifying primitive values directly
        cnt = [0]

        def stop():
            """
            To realize the scenario of this test, define a custom stop method to call
            self.stop after finished two events.
            """
            cnt[0] += 1
            if cnt[0] == 2:
                self.stop()

        with eventpublisher_process(self.sock_dir):
            me = salt.utils.event.MasterEvent(self.sock_dir)
            event_listener = saltnado.EventListener(
                {},  # we don't use mod_opts, don't save?
                {"sock_dir": self.sock_dir, "transport": "zeromq"},
            )

            self.assertEqual(0, len(event_listener.tag_map))
            self.assertEqual(0, len(event_listener.request_map))

            self._finished = False  # fit to event_listener's behavior
            dummy_request = DummyRequest()
            request_future_1 = event_listener.get_event(self, tag="evt1")
            request_future_2 = event_listener.get_event(
                self, tag="evt2", callback=lambda f: stop()
            )
            dummy_request_future_1 = event_listener.get_event(
                dummy_request, tag="evt3", callback=lambda f: stop()
            )
            dummy_request_future_2 = event_listener.get_event(
                dummy_request, timeout=10, tag="evt4"
            )

            self.assertEqual(4, len(event_listener.tag_map))
            self.assertEqual(2, len(event_listener.request_map))

            me.fire_event({"data": "foo2"}, "evt2")
            me.fire_event({"data": "foo3"}, "evt3")
            self.wait()
            event_listener.clean_by_request(self)
            me.fire_event({"data": "foo1"}, "evt1")

            self.assertTrue(request_future_1.done())
            with self.assertRaises(saltnado.TimeoutException):
                request_future_1.result()

            self.assertTrue(request_future_2.done())
            self.assertEqual(request_future_2.result()["tag"], "evt2")
            self.assertEqual(request_future_2.result()["data"]["data"], "foo2")

            self.assertTrue(dummy_request_future_1.done())
            self.assertEqual(dummy_request_future_1.result()["tag"], "evt3")
            self.assertEqual(dummy_request_future_1.result()["data"]["data"], "foo3")

            self.assertFalse(dummy_request_future_2.done())

            self.assertEqual(2, len(event_listener.tag_map))
            self.assertEqual(1, len(event_listener.request_map))

            event_listener.clean_by_request(dummy_request)

            with self.assertRaises(saltnado.TimeoutException):
                dummy_request_future_2.result()

            self.assertEqual(0, len(event_listener.tag_map))
            self.assertEqual(0, len(event_listener.request_map))
