import pytest

import salt.utils.json
from salt.netapi.rest_tornado import saltnado


@pytest.fixture
def app_urls():
    return [
        ("/run", saltnado.RunSaltAPIHandler),
    ]


@pytest.mark.parametrize("client", ["local", "local_async", "runner", "runner_async"])
async def test_authentication_exception_consistency(
    http_client, client, content_type_map
):
    """
    Test consistency of authentication exception of each clients.
    """
    valid_response = {"return": ["Failed to authenticate"]}

    request_lowstate = {
        "client": client,
        "tgt": "*",
        "fun": "test.fib",
        "arg": ["10"],
    }

    response = await http_client.fetch(
        "/run",
        method="POST",
        body=salt.utils.json.dumps(request_lowstate),
        headers={"Content-Type": content_type_map["json"]},
    )

    assert salt.utils.json.loads(response.body) == valid_response
