import pytest

import tests.support.netapi as netapi
from salt.netapi.rest_tornado import saltnado


@pytest.fixture
def client_config(client_config, netapi_port):
    client_config["rest_tornado"] = {"port": netapi_port}
    client_config["netapi_enable_clients"] = [
        "local",
        "local_async",
        "runner",
        "runner_async",
    ]
    # The default 10 s ``gather_job_timeout`` is racy against the
    # secondary salt-sub-minion on heavily loaded CI hosts (ARM64
    # containers in particular). The minion's job executes in
    # milliseconds but the return-channel round-trip back to the master
    # routinely lands 10-11 s after the publish, so ``_disbatch_local``
    # gives up at the 10 s mark and reports a single minion. Push the
    # ceiling out so the gather window covers the slow-runner tail and
    # ``test_get_no_mid`` (et al.) see both minions reliably.
    client_config["gather_job_timeout"] = 30
    return client_config


@pytest.fixture
def app(app_urls, load_auth, client_config, minion_config, salt_sub_minion):
    app = netapi.build_tornado_app(
        app_urls, load_auth, client_config, minion_config, setup_event_listener=True
    )
    try:
        yield app
    finally:
        app.event_listener.destroy()


@pytest.fixture
def client_headers(auth_token, content_type_map):
    return {
        "Accept": content_type_map["json"],
        "Content-Type": content_type_map["json"],
        saltnado.AUTH_TOKEN_HEADER: auth_token["token"],
    }


@pytest.fixture
def http_server(io_loop, app, client_headers, netapi_port):
    with netapi.TestsTornadoHttpServer(
        io_loop=io_loop, app=app, port=netapi_port, client_headers=client_headers
    ) as server:
        yield server


@pytest.fixture
def http_client(http_server):
    return http_server.client
