import shutil
import ssl
import tarfile

import pytest

try:
    import trustme
except ImportError:
    pass

from pytestshellutils.utils import ports
from saltfactories.utils import random_string

import salt.utils.http


@pytest.mark.parametrize("backend", ["requests", "urllib2", "tornado"])
def test_decode_body(webserver, integration_files_dir, backend):
    with tarfile.open(integration_files_dir / "test.tar.gz", "w:gz") as tar:
        tar.add(integration_files_dir / "this.txt")

    ret = salt.utils.http.query(
        webserver.url("test.tar.gz"), backend=backend, decode_body=False
    )
    assert isinstance(ret["body"], bytes)


pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("docker", "dockerd", check_all=False),
]


@pytest.fixture(scope="module")
def tinyproxy_port():
    return ports.get_unused_localhost_port()


@pytest.fixture(scope="module")
def tinyproxy_user():
    return random_string("tinyproxy-user-")


@pytest.fixture(scope="module")
def tinyproxy_pass():
    return random_string("tinyproxy-pass-")


@pytest.fixture(scope="session")
def ca():
    return trustme.CA()


@pytest.fixture(scope="session")
def httpserver_ssl_context(ca):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    localhost_cert = ca.issue_cert("127.0.0.1")
    localhost_cert.configure_cert(context)
    return context


@pytest.fixture(scope="session")
def httpclient_ssl_context(ca):
    with ca.cert_pem.tempfile() as ca_temp_path:
        return ssl.create_default_context(cafile=ca_temp_path)


@pytest.fixture(params=[True, False], ids=lambda x: "basic-auth" if x else "no-auth")
def tinyproxy_basic_auth(request):
    return request.param


@pytest.fixture(params=[True, False], ids=lambda x: "no-proxy" if x else "with-proxy")
def no_proxy(request):
    return request.param


@pytest.fixture(params=["POST", "GET"], ids=lambda x: x)
def http_method(request):
    return request.param


@pytest.fixture(scope="module")
def tinyproxy_dir(tmp_path_factory):
    try:
        dirname = tmp_path_factory.mktemp("tinyproxy")
        yield dirname
    finally:
        shutil.rmtree(dirname, ignore_errors=True)


@pytest.fixture
def tinyproxy_conf(
    tinyproxy_dir, tinyproxy_port, tinyproxy_user, tinyproxy_pass, tinyproxy_basic_auth
):
    basic_auth = (
        f"\nBasicAuth {tinyproxy_user} {tinyproxy_pass}" if tinyproxy_basic_auth else ""
    )
    conf = """Port {port}
Listen 127.0.0.1
Timeout 600
Allow 127.0.0.1
AddHeader "X-Tinyproxy-Header" "Test custom tinyproxy header"{auth}
    """.format(
        port=tinyproxy_port, auth=basic_auth
    )
    (tinyproxy_dir / "tinyproxy.conf").write_text(conf)


@pytest.fixture
def tinyproxy_container(
    salt_factories,
    tinyproxy_conf,
    tinyproxy_dir,
):
    container = salt_factories.get_container(
        "tinyproxy",
        image_name="ghcr.io/saltstack/salt-ci-containers/tinyproxy:latest",
        container_run_kwargs={
            "network_mode": "host",
            "volumes": {str(tinyproxy_dir): {"bind": "/etc/tinyproxy", "mode": "z"}},
        },
        pull_before_start=True,
        skip_on_pull_failure=True,
        skip_if_docker_client_not_connectable=True,
    )
    with container.started() as factory:
        yield factory


@pytest.mark.parametrize("backend", ["requests", "tornado", "urllib2"])
def test_real_proxy(
    tinyproxy_container,
    httpserver,
    ca,
    tinyproxy_port,
    tinyproxy_user,
    tinyproxy_pass,
    backend,
    tinyproxy_basic_auth,
    no_proxy,
    http_method,
):
    data = b"mydatahere"
    opts = {
        "proxy_host": "localhost",
        "proxy_port": tinyproxy_port,
    }
    if tinyproxy_basic_auth:
        opts.update(
            {
                "proxy_username": tinyproxy_user,
                "proxy_password": tinyproxy_pass,
            }
        )

    # Expecting the headers allows verification that it went through the proxy without looking at the logs
    if no_proxy:
        opts["no_proxy"] = ["random.hostname.io", httpserver.host]
        httpserver.expect_request(
            "/real_proxy_test",
        ).respond_with_data(data, content_type="application/octet-stream")
    else:
        httpserver.expect_request(
            "/real_proxy_test",
        ).respond_with_data(data, content_type="application/octet-stream")
    url = httpserver.url_for("/real_proxy_test").replace("localhost", "127.0.0.1")

    # We just want to be sure that it's using the proxy
    with ca.cert_pem.tempfile() as ca_temp_path:
        ret = salt.utils.http.query(
            url,
            method=http_method,
            data=data,
            backend=backend,
            opts=opts,
            decode_body=False,
            verify_ssl=ca_temp_path,
        )
    body = ret.get("body", "")
    assert body == data
