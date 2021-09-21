import pytest
import salt.utils.json
from salt.ext.tornado.httpclient import HTTPError
from salt.netapi.rest_tornado import saltnado


@pytest.fixture
def app_urls():
    return [
        (r"/minions/(.*)", saltnado.MinionSaltAPIHandler),
        (r"/minions", saltnado.MinionSaltAPIHandler),
    ]


async def test_get_no_mid(http_client):
    response = await http_client.fetch(
        "/minions",
        method="GET",
        follow_redirects=False,
    )
    response_obj = salt.utils.json.loads(response.body)
    assert len(response_obj["return"]) == 1
    # one per minion
    assert len(response_obj["return"][0]) == 2
    # check a single grain
    for minion_id, grains in response_obj["return"][0].items():
        assert minion_id == grains["id"]


@pytest.mark.slow_test
async def test_get(http_client, salt_minion):
    response = await http_client.fetch(
        "/minions/{}".format(salt_minion.id),
        method="GET",
        follow_redirects=False,
    )
    response_obj = salt.utils.json.loads(response.body)
    assert len(response_obj["return"]) == 1
    assert len(response_obj["return"][0]) == 1
    # check a single grain
    assert response_obj["return"][0][salt_minion.id]["id"] == salt_minion.id


async def test_post(http_client, salt_minion, salt_sub_minion):
    low = [{"tgt": "*minion-*", "fun": "test.ping"}]
    response = await http_client.fetch(
        "/minions",
        method="POST",
        body=salt.utils.json.dumps(low),
    )

    response_obj = salt.utils.json.loads(response.body)
    ret = response_obj["return"]

    # TODO: verify pub function? Maybe look at how we test the publisher
    assert len(ret) == 1
    assert "jid" in ret[0]
    assert sorted(ret[0]["minions"]) == sorted([salt_minion.id, salt_sub_minion.id])


@pytest.mark.slow_test
async def test_post_with_client(http_client, salt_minion, salt_sub_minion):
    # get a token for this test
    low = [{"client": "local_async", "tgt": "*minion-*", "fun": "test.ping"}]
    response = await http_client.fetch(
        "/minions",
        method="POST",
        body=salt.utils.json.dumps(low),
    )

    response_obj = salt.utils.json.loads(response.body)
    ret = response_obj["return"]

    # TODO: verify pub function? Maybe look at how we test the publisher
    assert len(ret) == 1
    assert "jid" in ret[0]
    assert sorted(ret[0]["minions"]) == sorted([salt_minion.id, salt_sub_minion.id])


@pytest.mark.slow_test
async def test_post_with_incorrect_client(http_client):
    """
    The /minions endpoint is asynchronous only, so if you try something else
    make sure you get an error
    """
    # get a token for this test
    low = [{"client": "local", "tgt": "*", "fun": "test.ping"}]
    with pytest.raises(HTTPError) as exc:
        await http_client.fetch(
            "/minions",
            method="POST",
            body=salt.utils.json.dumps(low),
        )
    assert exc.value.code == 400
