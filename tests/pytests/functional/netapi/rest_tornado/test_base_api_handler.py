import urllib.parse

import pytest

import salt.utils.json
import salt.utils.yaml
from salt.ext.tornado.httpclient import HTTPError
from salt.netapi.rest_tornado import saltnado


class StubHandler(saltnado.BaseSaltAPIHandler):  # pylint: disable=abstract-method
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


@pytest.fixture
def app_urls():
    return [
        ("/", StubHandler),
        ("/(.*)", StubHandler),
    ]


async def test_accept_content_type(http_client, content_type_map, subtests):
    """
    Test the base handler's accept picking
    """

    with subtests.test("Send NO accept header, should come back with json"):
        response = await http_client.fetch("/")
        assert response.headers["Content-Type"] == content_type_map["json"]
        assert isinstance(salt.utils.json.loads(response.body), dict)

    with subtests.test("Request application/json"):
        response = await http_client.fetch(
            "/", headers={"Accept": content_type_map["json"]}
        )
        assert response.headers["Content-Type"] == content_type_map["json"]
        assert isinstance(salt.utils.json.loads(response.body), dict)

    with subtests.test("Request application/x-yaml"):
        response = await http_client.fetch(
            "/", headers={"Accept": content_type_map["yaml"]}
        )
        assert response.headers["Content-Type"] == content_type_map["yaml"]
        assert isinstance(salt.utils.yaml.safe_load(response.body), dict)

    with subtests.test("Request not supported content-type"):
        with pytest.raises(HTTPError) as error:
            await http_client.fetch("/", headers={"Accept": content_type_map["xml"]})
        assert error.value.code == 406

    with subtests.test("Request some JSON with a browser like Accept"):
        accept_header = content_type_map["real-accept-header-json"]
        response = await http_client.fetch("/", headers={"Accept": accept_header})
        assert response.headers["Content-Type"] == content_type_map["json"]
        assert isinstance(salt.utils.json.loads(response.body), dict)

    with subtests.test("Request some YAML with a browser like Accept"):
        accept_header = content_type_map["real-accept-header-yaml"]
        response = await http_client.fetch("/", headers={"Accept": accept_header})
        assert response.headers["Content-Type"] == content_type_map["yaml"]
        assert isinstance(salt.utils.yaml.safe_load(response.body), dict)


async def test_token(http_client):
    """
    Test that the token is returned correctly
    """
    response = await http_client.fetch("/")
    token = salt.utils.json.loads(response.body)["token"]
    assert token is None

    # send a token as a header
    response = await http_client.fetch("/", headers={saltnado.AUTH_TOKEN_HEADER: "foo"})
    token = salt.utils.json.loads(response.body)["token"]
    assert token == "foo"

    # send a token as a cookie
    response = await http_client.fetch(
        "/", headers={"Cookie": f"{saltnado.AUTH_COOKIE_NAME}=foo"}
    )
    token = salt.utils.json.loads(response.body)["token"]
    assert token == "foo"

    # send both, make sure its the header
    response = await http_client.fetch(
        "/",
        headers={
            saltnado.AUTH_TOKEN_HEADER: "foo",
            "Cookie": f"{saltnado.AUTH_COOKIE_NAME}=bar",
        },
    )
    token = salt.utils.json.loads(response.body)["token"]
    assert token == "foo"


async def test_deserialize(http_client, content_type_map, subtests):
    """
    Send various encoded forms of lowstates (and bad ones) to make sure we
    handle deserialization correctly
    """
    valid_lowstate = [
        {"client": "local", "tgt": "*", "fun": "test.fib", "arg": ["10"]},
        {"client": "runner", "fun": "jobs.lookup_jid", "jid": "20130603122505459265"},
    ]

    with subtests.test("send as JSON"):
        response = await http_client.fetch(
            "/",
            method="POST",
            body=salt.utils.json.dumps(valid_lowstate),
            headers={"Content-Type": content_type_map["json"]},
        )

        assert valid_lowstate == salt.utils.json.loads(response.body)["lowstate"]

    with subtests.test("send yaml as json (should break)"):
        with pytest.raises(HTTPError) as exc:
            await http_client.fetch(
                "/",
                method="POST",
                body=salt.utils.yaml.safe_dump(valid_lowstate),
                headers={"Content-Type": content_type_map["json"]},
            )
        assert exc.value.code == 400

    with subtests.test("send as yaml"):
        response = await http_client.fetch(
            "/",
            method="POST",
            body=salt.utils.yaml.safe_dump(valid_lowstate),
            headers={"Content-Type": content_type_map["yaml"]},
        )
        assert valid_lowstate == salt.utils.json.loads(response.body)["lowstate"]

    with subtests.test("send json as yaml (works since yaml is a superset of json)"):
        response = await http_client.fetch(
            "/",
            method="POST",
            body=salt.utils.json.dumps(valid_lowstate),
            headers={"Content-Type": content_type_map["yaml"]},
        )
        assert valid_lowstate == salt.utils.json.loads(response.body)["lowstate"]

    with subtests.test("send json as text/plain"):
        response = await http_client.fetch(
            "/",
            method="POST",
            body=salt.utils.json.dumps(valid_lowstate),
            headers={"Content-Type": content_type_map["text"]},
        )
        assert valid_lowstate == salt.utils.json.loads(response.body)["lowstate"]

    with subtests.test("send form-urlencoded"):
        form_lowstate = (
            ("client", "local"),
            ("tgt", "*"),
            ("fun", "test.fib"),
            ("arg", "10"),
            ("arg", "foo"),
        )
        response = await http_client.fetch(
            "/",
            method="POST",
            body=urllib.parse.urlencode(form_lowstate),
            headers={"Content-Type": content_type_map["form"]},
        )
        returned_lowstate = salt.utils.json.loads(response.body)["lowstate"]
        assert len(returned_lowstate) == 1
        returned_lowstate = returned_lowstate[0]

        assert returned_lowstate["client"] == "local"
        assert returned_lowstate["tgt"] == "*"
        assert returned_lowstate["fun"] == "test.fib"
        assert returned_lowstate["arg"] == ["10", "foo"]

    with subtests.test("Send json with utf8 charset"):
        response = await http_client.fetch(
            "/",
            method="POST",
            body=salt.utils.json.dumps(valid_lowstate),
            headers={"Content-Type": content_type_map["json-utf8"]},
        )
        assert valid_lowstate == salt.utils.json.loads(response.body)["lowstate"]


async def test_get_lowstate(http_client, content_type_map, subtests):
    """
    Test transformations low data of the function _get_lowstate
    """
    valid_lowstate = [{"client": "local", "tgt": "*", "fun": "test.fib", "arg": ["10"]}]

    with subtests.test("Case 1. dictionary type of lowstate"):
        request_lowstate = {
            "client": "local",
            "tgt": "*",
            "fun": "test.fib",
            "arg": ["10"],
        }

        response = await http_client.fetch(
            "/",
            method="POST",
            body=salt.utils.json.dumps(request_lowstate),
            headers={"Content-Type": content_type_map["json"]},
        )

        assert valid_lowstate == salt.utils.json.loads(response.body)["lowstate"]

    with subtests.test("Case 2. string type of arg"):
        request_lowstate = {
            "client": "local",
            "tgt": "*",
            "fun": "test.fib",
            "arg": "10",
        }

        response = await http_client.fetch(
            "/",
            method="POST",
            body=salt.utils.json.dumps(request_lowstate),
            headers={"Content-Type": content_type_map["json"]},
        )

        assert valid_lowstate == salt.utils.json.loads(response.body)["lowstate"]

    with subtests.test("Case 3. Combine Case 1 and Case 2."):
        request_lowstate = {
            "client": "local",
            "tgt": "*",
            "fun": "test.fib",
            "arg": "10",
        }

        # send as json
        response = await http_client.fetch(
            "/",
            method="POST",
            body=salt.utils.json.dumps(request_lowstate),
            headers={"Content-Type": content_type_map["json"]},
        )

        assert valid_lowstate == salt.utils.json.loads(response.body)["lowstate"]

    with subtests.test("send as yaml"):
        response = await http_client.fetch(
            "/",
            method="POST",
            body=salt.utils.yaml.safe_dump(request_lowstate),
            headers={"Content-Type": content_type_map["yaml"]},
        )
        assert valid_lowstate == salt.utils.json.loads(response.body)["lowstate"]

    with subtests.test("send as plain text"):
        response = await http_client.fetch(
            "/",
            method="POST",
            body=salt.utils.json.dumps(request_lowstate),
            headers={"Content-Type": content_type_map["text"]},
        )
        assert valid_lowstate == salt.utils.json.loads(response.body)["lowstate"]

    with subtests.test("send as form-urlencoded"):
        request_form_lowstate = (
            ("client", "local"),
            ("tgt", "*"),
            ("fun", "test.fib"),
            ("arg", "10"),
        )

        response = await http_client.fetch(
            "/",
            method="POST",
            body=urllib.parse.urlencode(request_form_lowstate),
            headers={"Content-Type": content_type_map["form"]},
        )
        assert valid_lowstate == salt.utils.json.loads(response.body)["lowstate"]


async def test_cors_origin_wildcard(http_client, app):
    """
    Check that endpoints returns Access-Control-Allow-Origin
    """
    app.mod_opts["cors_origin"] = "*"

    response = await http_client.fetch("/")
    assert response.headers["Access-Control-Allow-Origin"] == "*"


async def test_cors_origin_single(http_client, app, subtests):
    """
    Check that endpoints returns the Access-Control-Allow-Origin when
    only one origins is set
    """
    app.mod_opts["cors_origin"] = "http://example.foo"

    with subtests.test("Example.foo is an authorized origin"):
        response = await http_client.fetch(
            "/", headers={"Origin": "http://example.foo"}
        )
        assert response.headers["Access-Control-Allow-Origin"] == "http://example.foo"

    with subtests.test("Example2.foo is not an authorized origin"):
        response = await http_client.fetch(
            "/", headers={"Origin": "http://example2.foo"}
        )
        assert response.headers.get("Access-Control-Allow-Origin") is None


async def test_cors_origin_multiple(http_client, app, subtests):
    """
    Check that endpoints returns the Access-Control-Allow-Origin when
    multiple origins are set
    """
    app.mod_opts["cors_origin"] = ["http://example.foo", "http://foo.example"]

    with subtests.test("Example.foo is an authorized origin"):
        response = await http_client.fetch(
            "/", headers={"Origin": "http://example.foo"}
        )
        assert response.headers["Access-Control-Allow-Origin"] == "http://example.foo"

    with subtests.test("Example2.foo is not an authorized origin"):
        response = await http_client.fetch(
            "/", headers={"Origin": "http://example2.foo"}
        )
        assert response.headers.get("Access-Control-Allow-Origin") is None


async def test_cors_preflight_request(http_client, app):
    """
    Check that preflight request contains right headers
    """
    app.mod_opts["cors_origin"] = "*"

    request_headers = "X-Auth-Token, accept, content-type"
    preflight_headers = {
        "Access-Control-Request-Headers": request_headers,
        "Access-Control-Request-Method": "GET",
    }

    response = await http_client.fetch("/", method="OPTIONS", headers=preflight_headers)
    headers = response.headers

    assert response.code == 204
    assert headers["Access-Control-Allow-Headers"] == request_headers
    assert headers["Access-Control-Expose-Headers"] == "X-Auth-Token"
    assert headers["Access-Control-Allow-Methods"] == "OPTIONS, GET, POST"

    assert response.code == 204


async def test_cors_origin_url_with_arguments(app, http_client):
    """
    Check that preflight requests works with url with components
    like jobs or minions endpoints.
    """
    app.mod_opts["cors_origin"] = "*"

    request_headers = "X-Auth-Token, accept, content-type"
    preflight_headers = {
        "Access-Control-Request-Headers": request_headers,
        "Access-Control-Request-Method": "GET",
    }
    response = await http_client.fetch(
        "/1234567890", method="OPTIONS", headers=preflight_headers
    )
    headers = response.headers

    assert response.code == 204
    assert headers["Access-Control-Allow-Origin"] == "*"
