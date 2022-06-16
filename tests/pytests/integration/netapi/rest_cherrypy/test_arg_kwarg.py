import urllib.parse

import pytest
import salt.utils.json


@pytest.mark.slow_test
async def test_accepts_arg_kwarg_keys(
    http_client, auth_creds, content_type_map, subtests
):
    """
    Ensure that (singular) arg and kwarg keys (for passing parameters)
    are supported by runners.
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
    low = {
        "client": "runner",
        "fun": "test.arg",
        "arg": [1234, 5678],
        "kwarg": {"ext_source": "redis"},
    }
    for content_type in ("json", "form"):
        with subtests.test(content_type=content_type):
            if content_type == "json":
                body = salt.utils.json.dumps(low)
            else:
                _low = low.copy()
                arg = _low.pop("arg")
                body = urllib.parse.urlencode(_low)
                for _arg in arg:
                    body += "&arg={}".format(_arg)
            response = await http_client.fetch(
                "/",
                method="POST",
                body=body,
                headers={
                    "Accept": content_type_map["json"],
                    "Content-Type": content_type_map[content_type],
                    "X-Auth-Token": token,
                },
            )
            assert response.code == 200
            body = salt.utils.json.loads(response.body)
            ret = body["return"][0]
            assert ret["args"] == low["arg"]
            assert ret["kwargs"] == low["kwarg"]
