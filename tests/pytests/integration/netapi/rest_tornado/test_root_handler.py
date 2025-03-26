import pytest
from tornado.httpclient import HTTPError

import salt.utils.json
from salt.netapi.rest_tornado import saltnado


@pytest.fixture
def app_urls(salt_sub_minion):
    return [
        ("/", saltnado.SaltAPIHandler),
    ]


async def test_root(http_client):
    """
    Test the root path which returns the list of clients we support
    """
    response = await http_client.fetch(
        "/", connect_timeout=30, request_timeout=30, headers=None
    )
    assert response.code == 200
    response_obj = salt.utils.json.loads(response.body)
    assert sorted(response_obj["clients"]) == [
        "local",
        "local_async",
        "runner",
        "runner_async",
    ]
    assert response_obj["return"] == "Welcome"


@pytest.mark.slow_test
async def test_post_no_auth(http_client, content_type_map):
    """
    Test post with no auth token, should 401
    """
    # get a token for this test
    low = [{"client": "local", "tgt": "*", "fun": "test.ping"}]
    with pytest.raises(HTTPError) as exc:
        await http_client.fetch(
            "/",
            method="POST",
            body=salt.utils.json.dumps(low),
            headers={"Content-Type": content_type_map["json"]},
            follow_redirects=False,
            connect_timeout=30,
            request_timeout=30,
        )
    assert exc.value.code == 302
    assert exc.value.response.headers["Location"] == "/login"


# Local client tests


async def test_simple_local_post(http_client, salt_minion, salt_sub_minion):
    """
    Test a basic API of /
    """
    low = [{"client": "local", "tgt": "*", "fun": "test.ping"}]
    response = await http_client.fetch(
        "/",
        method="POST",
        body=salt.utils.json.dumps(low),
        connect_timeout=30,
        request_timeout=30,
    )
    response_obj = salt.utils.json.loads(response.body)
    assert len(response_obj["return"]) == 1
    assert response_obj["return"][0] == {salt_minion.id: True, salt_sub_minion.id: True}


async def test_simple_local_post_no_tgt(http_client):
    """
    POST job with invalid tgt
    """
    low = [{"client": "local", "tgt": "minion_we_dont_have", "fun": "test.ping"}]
    response = await http_client.fetch(
        "/",
        method="POST",
        body=salt.utils.json.dumps(low),
        connect_timeout=30,
        request_timeout=30,
    )
    response_obj = salt.utils.json.loads(response.body)
    assert response_obj["return"] == [
        "No minions matched the target. No command was sent, no jid was assigned."
    ]


# local client request body test


async def test_simple_local_post_only_dictionary_request(
    http_client, salt_minion, salt_sub_minion
):
    """
    Test a basic API of /
    """
    low = {
        "client": "local",
        "tgt": "*",
        "fun": "test.ping",
    }
    response = await http_client.fetch(
        "/",
        method="POST",
        body=salt.utils.json.dumps(low),
        connect_timeout=30,
        request_timeout=30,
    )
    response_obj = salt.utils.json.loads(response.body)
    assert len(response_obj["return"]) == 1
    assert response_obj["return"][0] == {salt_minion.id: True, salt_sub_minion.id: True}


async def test_simple_local_post_invalid_request(http_client):
    """
    Test a basic API of /
    """
    low = ["invalid request"]
    with pytest.raises(HTTPError) as exc:
        await http_client.fetch(
            "/",
            method="POST",
            body=salt.utils.json.dumps(low),
            connect_timeout=30,
            request_timeout=30,
        )
    assert exc.value.code == 400


# local_async tests
async def test_simple_local_async_post(http_client, salt_minion, salt_sub_minion):
    low = [{"client": "local_async", "tgt": "*", "fun": "test.ping"}]
    response = await http_client.fetch(
        "/",
        method="POST",
        body=salt.utils.json.dumps(low),
    )

    response_obj = salt.utils.json.loads(response.body)
    ret = response_obj["return"]
    ret[0]["minions"] = sorted(ret[0]["minions"])

    # TODO: verify pub function? Maybe look at how we test the publisher
    assert len(ret) == 1
    assert "jid" in ret[0]
    assert ret[0]["minions"] == sorted([salt_minion.id, salt_sub_minion.id])


async def test_multi_local_async_post(http_client, salt_minion, salt_sub_minion):
    low = [
        {"client": "local_async", "tgt": "*", "fun": "test.ping"},
        {"client": "local_async", "tgt": "*", "fun": "test.ping"},
    ]
    response = await http_client.fetch(
        "/",
        method="POST",
        body=salt.utils.json.dumps(low),
    )

    response_obj = salt.utils.json.loads(response.body)
    ret = response_obj["return"]
    ret[0]["minions"] = sorted(ret[0]["minions"])
    ret[1]["minions"] = sorted(ret[1]["minions"])

    assert len(ret) == 2
    assert "jid" in ret[0]
    assert "jid" in ret[1]
    assert ret[0]["minions"] == sorted([salt_minion.id, salt_sub_minion.id])
    assert ret[1]["minions"] == sorted([salt_minion.id, salt_sub_minion.id])


@pytest.mark.slow_test
async def test_multi_local_async_post_multitoken(
    http_client, auth_token, salt_minion, salt_sub_minion
):
    low = [
        {"client": "local_async", "tgt": "*", "fun": "test.ping"},
        {
            "client": "local_async",
            "tgt": "*",
            "fun": "test.ping",
            # send a different (but still valid token)
            "token": auth_token["token"],
        },
        {
            "client": "local_async",
            "tgt": "*",
            "fun": "test.ping",
            "token": "BAD_TOKEN",  # send a bad token
        },
    ]
    response = await http_client.fetch(
        "/",
        method="POST",
        body=salt.utils.json.dumps(low),
    )

    response_obj = salt.utils.json.loads(response.body)
    ret = response_obj["return"]
    ret[0]["minions"] = sorted(ret[0]["minions"])
    ret[1]["minions"] = sorted(ret[1]["minions"])

    assert len(ret) == 3  # make sure we got 3 responses
    assert "jid" in ret[0]  # the first 2 are regular returns
    assert "jid" in ret[1]
    assert "Failed to authenticate" in ret[2]  # bad auth
    assert ret[0]["minions"] == sorted([salt_minion.id, salt_sub_minion.id])
    assert ret[1]["minions"] == sorted([salt_minion.id, salt_sub_minion.id])


@pytest.mark.slow_test
async def test_simple_local_async_post_no_tgt(http_client):
    low = [{"client": "local_async", "tgt": "minion_we_dont_have", "fun": "test.ping"}]
    response = await http_client.fetch(
        "/",
        method="POST",
        body=salt.utils.json.dumps(low),
    )
    response_obj = salt.utils.json.loads(response.body)
    assert response_obj["return"] == [{}]


# runner tests
@pytest.mark.slow_test
async def test_simple_local_runner_post(http_client, salt_minion, salt_sub_minion):
    low = [{"client": "runner", "fun": "manage.up"}]
    response = await http_client.fetch(
        "/",
        method="POST",
        body=salt.utils.json.dumps(low),
        connect_timeout=30,
        request_timeout=300,
    )
    response_obj = salt.utils.json.loads(response.body)
    assert len(response_obj["return"]) == 1
    assert sorted(response_obj["return"][0]) == sorted(
        [salt_minion.id, salt_sub_minion.id]
    )


# runner_async tests
async def test_simple_local_runner_async_post(http_client):
    low = [{"client": "runner_async", "fun": "manage.up"}]
    response = await http_client.fetch(
        "/",
        method="POST",
        body=salt.utils.json.dumps(low),
        connect_timeout=10,
        request_timeout=10,
    )
    response_obj = salt.utils.json.loads(response.body)
    assert "return" in response_obj
    assert 1 == len(response_obj["return"])
    assert "jid" in response_obj["return"][0]
    assert "tag" in response_obj["return"][0]
