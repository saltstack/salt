

import shutil
import tarfile

import pytest
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


@pytest.fixture(scope="module")
def tinyproxy_port():
    return ports.get_unused_localhost_port()


@pytest.fixture(scope="module")
def tinyproxy_user():
    return random_string("tinyproxy-user-")


@pytest.fixture(scope="module")
def tinyproxy_pass():
    return random_string("tinyproxy-pass-")


@pytest.fixture(scope="module")
def tinyproxy_dir(tmp_path_factory):
    try:
        dirname = tmp_path_factory.mktemp("tinyproxy")
        print(dirname)
        yield dirname
    finally:
        shutil.rmtree(dirname, ignore_errors=True)


@pytest.fixture(scope="module")
def tinyproxy_conf(tinyproxy_dir, tinyproxy_port, tinyproxy_user, tinyproxy_pass):
    conf = """Port {port}
Listen 127.0.0.1
Timeout 600
Allow 127.0.0.1
AddHeader "X-Tinyproxy-Header" "Test custom tinyproxy header"
BasicAuth {uname} {passwd}
    """.format(
        port=tinyproxy_port, uname=tinyproxy_user, passwd=tinyproxy_pass
    )
    (tinyproxy_dir / "tinyproxy.conf").write_text(conf)


@pytest.fixture(scope="module")
def tinyproxy_container(
    salt_factories,
    tinyproxy_port,
    tinyproxy_conf,
    tinyproxy_dir,
):
    container = salt_factories.get_container(
        "tinyproxy",
        image_name="vimagick/tinyproxy",
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


@pytest.mark.slow_test
@pytest.mark.skip_if_binaries_missing("docker", "dockerd", check_all=False)
@pytest.mark.parametrize("backend", ["requests", "tornado", "urllib2"])
def test_real_proxy(
    tinyproxy_container,
    httpserver,
    tinyproxy_port,
    tinyproxy_user,
    tinyproxy_pass,
    backend,
):
    data = "mydatahere"
    opts = {
        "proxy_host": "localhost",
        "proxy_port": tinyproxy_port,
        "proxy_username": tinyproxy_user,
        "proxy_password": tinyproxy_pass,
    }

    # Expecting the headers allows verification that it went through the proxy without looking at the logs
    httpserver.expect_request(
        "/real_proxy_test",
        headers={"X-Tinyproxy-Header": "Test custom tinyproxy header"},
    ).respond_with_data(data)
    url = httpserver.url_for("/real_proxy_test")

    # We just want to be sure that it's using the proxy
    ret = salt.utils.http.query(url, method="POST", data=data, backend=backend, opts=opts)
    body = ret.get("body", "")
    assert body == data
