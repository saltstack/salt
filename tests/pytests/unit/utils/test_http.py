import sys
import urllib

import pytest
import requests
from pytestshellutils.utils import ports
from werkzeug.wrappers import Response  # pylint: disable=3rd-party-module-not-gated

import salt.utils.http as http
from tests.support.mock import MagicMock, patch


def test_requests_session_verify_ssl_false(ssl_webserver, integration_files_dir):
    """
    test salt.utils.http.session when using verify_ssl
    """
    for verify in [True, False, None]:
        kwargs = {"verify_ssl": verify}
        if verify is None:
            kwargs.pop("verify_ssl")

        if verify is True or verify is None:
            with pytest.raises(requests.exceptions.SSLError) as excinfo:
                session = http.session(**kwargs)
                ret = session.get(ssl_webserver.url("this.txt"))
        else:
            session = http.session(**kwargs)
            ret = session.get(ssl_webserver.url("this.txt"))
            assert ret.status_code == 200


def test_session_ca_bundle_verify_false():
    """
    test salt.utils.http.session when using
    both ca_bunlde and verify_ssl false
    """
    ret = http.session(ca_bundle="/tmp/test_bundle", verify_ssl=False)
    assert ret is False


def test_session_headers():
    """
    test salt.utils.http.session when setting
    headers
    """
    ret = http.session(headers={"Content-Type": "application/json"})
    assert ret.headers["Content-Type"] == "application/json"


def test_session_ca_bundle():
    """
    test salt.utils.https.session when setting ca_bundle
    """
    fpath = "/tmp/test_bundle"
    patch_os = patch("os.path.exists", MagicMock(return_value=True))
    with patch_os:
        ret = http.session(ca_bundle=fpath)
    assert ret.verify == fpath


def test_sanitize_url_hide_fields_none():
    """
    Tests sanitizing a url when the hide_fields kwarg is None.
    """
    mock_url = "https://api.testing.com/?&foo=bar&test=testing"
    ret = http.sanitize_url(mock_url, hide_fields=None)
    assert ret == mock_url


def test_sanitize_url_no_elements():
    """
    Tests sanitizing a url when no elements should be sanitized.
    """
    mock_url = "https://api.testing.com/?&foo=bar&test=testing"
    ret = http.sanitize_url(mock_url, [""])
    assert ret == mock_url


def test_sanitize_url_single_element():
    """
    Tests sanitizing a url with only a single element to be sanitized.
    """
    mock_url = (
        "https://api.testing.com/?&keep_it_secret=abcdefghijklmn"
        "&api_action=module.function"
    )
    mock_ret = (
        "https://api.testing.com/?&keep_it_secret=XXXXXXXXXX&"
        "api_action=module.function"
    )
    ret = http.sanitize_url(mock_url, ["keep_it_secret"])
    assert ret == mock_ret


def test_sanitize_url_multiple_elements():
    """
    Tests sanitizing a url with multiple elements to be sanitized.
    """
    mock_url = (
        "https://api.testing.com/?rootPass=badpassword%21"
        "&skipChecks=True&api_key=abcdefghijklmn"
        "&NodeID=12345&api_action=module.function"
    )
    mock_ret = (
        "https://api.testing.com/?rootPass=XXXXXXXXXX"
        "&skipChecks=True&api_key=XXXXXXXXXX"
        "&NodeID=12345&api_action=module.function"
    )
    ret = http.sanitize_url(mock_url, ["api_key", "rootPass"])
    assert ret == mock_ret


# _sanitize_components tests


def test_sanitize_components_no_elements():
    """
    Tests when zero elements need to be sanitized.
    """
    mock_component_list = ["foo=bar", "bar=baz", "hello=world"]
    mock_ret = "foo=bar&bar=baz&hello=world&"
    ret = http._sanitize_url_components(mock_component_list, "api_key")
    assert ret == mock_ret


def test_sanitize_components_one_element():
    """
    Tests a single component to be sanitized.
    """
    mock_component_list = ["foo=bar", "api_key=abcdefghijklmnop"]
    mock_ret = "foo=bar&api_key=XXXXXXXXXX&"
    ret = http._sanitize_url_components(mock_component_list, "api_key")
    assert ret == mock_ret


def test_sanitize_components_multiple_elements():
    """
    Tests two componenets to be sanitized.
    """
    mock_component_list = ["foo=bar", "foo=baz", "api_key=testing"]
    mock_ret = "foo=XXXXXXXXXX&foo=XXXXXXXXXX&api_key=testing&"
    ret = http._sanitize_url_components(mock_component_list, "foo")
    assert ret == mock_ret


@pytest.mark.slow_test
def test_query_null_response():
    """
    This tests that we get a null response when raise_error=False and the
    host/port cannot be reached.
    """
    host = "127.0.0.1"

    port = ports.get_unused_localhost_port()

    url = f"http://{host}:{port}/"
    result = http.query(url, raise_error=False)
    if sys.platform.startswith("win"):
        assert result == {"error": "[Errno 10061] Unknown error"}, result
    else:
        assert result == {"error": "[Errno 111] Connection refused"}


def test_query_error_handling():
    ret = http.query("http://127.0.0.1:0")
    assert isinstance(ret, dict)
    assert isinstance(ret.get("error", None), str)
    # use RFC6761 invalid domain that does not exist
    ret = http.query("http://myfoobardomainthatnotexist.invalid")
    assert isinstance(ret, dict)
    assert isinstance(ret.get("error", None), str)


def test_parse_cookie_header():
    header = "; ".join(
        [
            "foo=bar",
            "expires=Mon, 03-Aug-20 14:26:27 GMT",
            "path=/",
            "domain=.mydomain.tld",
            "HttpOnly",
            "SameSite=Lax",
            "Secure",
        ]
    )
    ret = http.parse_cookie_header(header)
    cookie = ret.pop(0)
    assert cookie.name == "foo", cookie.name
    assert cookie.value == "bar", cookie.value
    assert cookie.expires == 1596464787, cookie.expires
    assert cookie.path == "/", cookie.path
    assert cookie.domain == ".mydomain.tld", cookie.domain
    assert cookie.secure
    # Only one cookie should have been returned, if anything is left in the
    # parse_cookie_header return then something went wrong.
    assert not ret


@pytest.mark.requires_network
def test_requests_multipart_formdata_post(httpserver):
    """
    Test handling of a multipart/form-data POST using the requests backend
    """
    match_this = (
        "{0}\r\nContent-Disposition: form-data;"
        ' name="fieldname_here"\r\n\r\nmydatahere\r\n{0}--\r\n'
    )

    def mirror_post_handler(request):
        return Response(request.data)

    httpserver.expect_request(
        "/multipart_form_data",
    ).respond_with_handler(mirror_post_handler)
    url = httpserver.url_for("/multipart_form_data")

    ret = http.query(
        url,
        method="POST",
        data="mydatahere",
        formdata=True,
        formdata_fieldname="fieldname_here",
        backend="requests",
    )
    body = ret.get("body", "")
    boundary = body[: body.find("\r")]
    assert body == match_this.format(boundary)


def test_query_proxy(httpserver):
    """
    Test http.query with tornado and with proxy opts set
    and then test with no_proxy set to ensure we dont
    run into issue #55192 again.
    """
    data = "mydatahere"
    opts = {
        "proxy_host": "127.0.0.1",
        "proxy_port": 88,
        "proxy_username": "salt_test",
        "proxy_password": "super_secret",
    }

    with patch("requests.Session") as mock_session:
        mock_session.return_value = MagicMock()
        ret = http.query(
            "https://fake_url",
            method="POST",
            data=data,
            backend="tornado",
            opts=opts,
        )

        assert mock_session.return_value.proxies == {
            "http": "http://salt_test:super_secret@127.0.0.1:88",
            "https": "http://salt_test:super_secret@127.0.0.1:88",
        }

    opts["no_proxy"] = [httpserver.host]

    httpserver.expect_request(
        "/no_proxy_test",
    ).respond_with_data(data)
    url = httpserver.url_for("/no_proxy_test")

    with patch("requests.Session") as mock_session:
        mock_session.return_value = MagicMock()
        ret = http.query(
            url,
            method="POST",
            data=data,
            backend="tornado",
            opts=opts,
        )
        assert not isinstance(mock_session.return_value.proxies, dict)

    ret = http.query(url, method="POST", data=data, backend="tornado", opts=opts)
    body = ret.get("body", "")
    assert body == data


@pytest.mark.parametrize("backend", ["requests", "tornado", "urllib2"])
def test_backends_decode_body_false(httpserver, backend):
    """
    test all backends when using
    decode_body=False that it returns
    bytes and does not try to decode
    """
    url = "/test-bytes"
    data = b"test-bytes"
    httpserver.expect_request(
        url,
    ).respond_with_data(data, content_type="application/octet-stream")
    ret = http.query(
        httpserver.url_for(url),
        backend=backend,
        decode_body=False,
    )
    body = ret.get("body", "")
    assert isinstance(body, bytes)


@pytest.mark.parametrize("backend", ["requests", "tornado", "urllib2"])
def test_backends_decode_body_true(httpserver, backend):
    """
    test all backends when using decode_body=True that it returns string and decodes it.
    """
    url = "/test-decoded-bytes"
    data = b"test-decoded-bytes"
    httpserver.expect_request(
        url,
    ).respond_with_data(data, content_type="application/octet-stream")
    ret = http.query(
        httpserver.url_for(url),
        backend=backend,
    )
    body = ret.get("body", "")
    assert isinstance(body, str)


def test_requests_post_content_type(httpserver):
    url = httpserver.url_for("/post-content-type")
    data = urllib.parse.urlencode({"payload": "test"})
    opts = {
        "proxy_host": "127.0.0.1",
        "proxy_port": 88,
    }
    with patch("requests.Session") as mock_session:
        sess = MagicMock()
        sess.headers = {}
        mock_session.return_value = sess
        ret = http.query(
            url,
            method="POST",
            data=data,
            backend="tornado",
            opts=opts,
        )
        assert "Content-Type" in sess.headers
        assert sess.headers["Content-Type"] == "application/x-www-form-urlencoded"
        assert "Content-Length" in sess.headers
        assert sess.headers["Content-Length"] == "12"
