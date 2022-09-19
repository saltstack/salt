import pytest

import salt.utils.json


@pytest.mark.slow_test
async def test_all_jobs(http_client, auth_creds, content_type_map):
    """
    test query to /jobs returns job data
    """
    # Login to get the token
    body = salt.utils.json.dumps(auth_creds)
    response = await http_client.fetch(
        "/login",
        method="POST",
        body=body,
        headers={
            "Accept": content_type_map["json"],
            "Content-Type": content_type_map["json"],
        },
    )
    assert response.code == 200
    token = response.headers["X-Auth-Token"]

    low = {"client": "local", "tgt": "*", "fun": "test.ping", **auth_creds}
    body = salt.utils.json.dumps(low)
    # Add a job
    response = await http_client.fetch(
        "/run",
        method="POST",
        body=body,
        headers={
            "Accept": content_type_map["json"],
            "Content-Type": content_type_map["json"],
        },
    )
    assert response.code == 200
    body = salt.utils.json.loads(response.body)

    # Get Jobs
    response = await http_client.fetch(
        "/jobs",
        method="GET",
        headers={"Accept": content_type_map["json"], "X-Auth-Token": token},
    )
    assert response.code == 200
    body = salt.utils.json.loads(response.body)
    for ret in body["return"][0].values():
        assert "Function" in ret
        if ret["Function"] == "test.ping":
            break
    else:
        pytest.fail("Failed to get the 'test.ping' job")
