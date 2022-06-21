import urllib.parse

import pytest


@pytest.fixture
def client_config(client_config):
    client_config["rest_cherrypy"]["webhook_disable_auth"] = True
    return client_config


async def test_webhook_noauth(http_client):
    """
    Auth can be disabled for requests to the webhook URL

    See the above ``client_config`` fixture where we disable it
    """
    body = urllib.parse.urlencode({"foo": "Foo!"})
    response = await http_client.fetch("/hook", method="POST", body=body)
    assert response.code == 200
