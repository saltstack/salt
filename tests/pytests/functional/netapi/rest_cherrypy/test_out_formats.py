import pytest

from salt.ext.tornado.httpclient import HTTPError


@pytest.fixture
def app(app):
    app.wsgi_application.config["global"]["tools.hypermedia_out.on"] = True
    return app


async def test_default_accept(http_client, content_type_map):
    response = await http_client.fetch("/", method="GET")
    assert response.headers["Content-Type"] == content_type_map["json"]


async def test_unsupported_accept(http_client):
    with pytest.raises(HTTPError) as exc:
        await http_client.fetch(
            "/", method="GET", headers={"Accept": "application/ms-word"}
        )
    assert exc.value.code == 406


async def test_json_out(http_client, content_type_map):
    response = await http_client.fetch(
        "/", method="GET", headers={"Accept": content_type_map["json"]}
    )
    assert response.headers["Content-Type"] == content_type_map["json"]


async def test_yaml_out(http_client, content_type_map):
    response = await http_client.fetch(
        "/", method="GET", headers={"Accept": content_type_map["yaml"]}
    )
    assert response.headers["Content-Type"] == content_type_map["yaml"]
