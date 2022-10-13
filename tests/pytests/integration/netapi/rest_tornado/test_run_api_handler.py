import pytest

import salt.utils.json
from salt.netapi.rest_tornado import saltnado

# TODO: run all the same tests from the root handler, but for now since they are
# the same code, we'll just sanity check


@pytest.fixture
def app_urls():
    return [
        ("/run", saltnado.RunSaltAPIHandler),
    ]


@pytest.mark.slow_test
async def test_get(http_client, salt_minion, salt_sub_minion):
    low = [{"client": "local", "tgt": "*", "fun": "test.ping"}]
    response = await http_client.fetch(
        "/run",
        method="POST",
        body=salt.utils.json.dumps(low),
    )
    response_obj = salt.utils.json.loads(response.body)
    ret = response_obj["return"]
    assert sorted(ret[0]) == sorted([salt_minion.id, salt_sub_minion.id])
