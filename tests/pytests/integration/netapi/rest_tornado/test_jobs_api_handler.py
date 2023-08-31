import pytest

import salt.utils.json
from salt.netapi.rest_tornado import saltnado


@pytest.fixture
def app_urls():
    return [
        (r"/jobs/(.*)", saltnado.JobsSaltAPIHandler),
        (r"/jobs", saltnado.JobsSaltAPIHandler),
    ]


@pytest.mark.slow_test
@pytest.mark.async_timeout(seconds=120)
async def test_get(http_client, subtests):
    # test with no JID
    response = await http_client.fetch("/jobs", method="GET", follow_redirects=False)
    response_obj = salt.utils.json.loads(response.body)["return"][0]
    assert response_obj
    assert isinstance(response_obj, dict)
    for ret in response_obj.values():
        with subtests.test('assert "Function" in ret'):
            assert "Function" in ret
        with subtests.test('assert "Target" in ret'):
            assert "Target" in ret
        with subtests.test('assert "Target-type" in ret'):
            assert "Target-type" in ret
        with subtests.test('assert "User" in ret'):
            assert "User" in ret
        with subtests.test('assert "StartTime" in ret'):
            assert "StartTime" in ret
        with subtests.test('assert "Arguments" in ret'):
            assert "Arguments" in ret

    # test with a specific JID passed in
    jid = next(iter(response_obj.keys()))
    response = await http_client.fetch(
        "/jobs/{}".format(jid),
        method="GET",
        follow_redirects=False,
    )
    response_obj = salt.utils.json.loads(response.body)["return"][0]
    assert response_obj
    assert isinstance(response_obj, dict)

    with subtests.test('assert "Function" in response_obj'):
        assert "Function" in response_obj
    with subtests.test('assert "Target" in response_obj'):
        assert "Target" in response_obj
    with subtests.test('assert "Target-type" in response_obj'):
        assert "Target-type" in response_obj
    with subtests.test('assert "User" in response_obj'):
        assert "User" in response_obj
    with subtests.test('assert "StartTime" in response_obj'):
        assert "StartTime" in response_obj
    with subtests.test('assert "Arguments" in response_obj'):
        assert "Arguments" in response_obj
    with subtests.test('assert "Result" in response_obj'):
        assert "Result" in response_obj
