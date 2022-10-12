import pytest

from tests.support.mock import MagicMock, patch


@pytest.fixture
def app(app):
    app.wsgi_application.config["global"]["tools.cors_tool.on"] = True
    return app


async def test_option_request(http_client):
    with patch(
        "salt.netapi.rest_cherrypy.app.cherrypy.session", MagicMock(), create=True
    ):
        response = await http_client.fetch(
            "/", method="OPTIONS", headers={"Origin": "https://domain.com"}
        )
    assert response.code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "https://domain.com"
