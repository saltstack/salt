import pytest

import salt.states.grafana_datasource as grafana_datasource
from tests.support.mock import MagicMock, Mock, patch

profile = {
    "grafana_url": "http://grafana",
    "grafana_token": "token",
}


def mock_json_response(data):
    response = MagicMock()
    response.json = MagicMock(return_value=data)
    return Mock(return_value=response)


@pytest.fixture
def configure_loader_modules():
    return {grafana_datasource: {}}


def test_present():
    with patch("requests.get", mock_json_response([])):
        with patch("requests.post") as rpost:
            ret = grafana_datasource.present("test", "type", "url", profile=profile)
            rpost.assert_called_once_with(
                "http://grafana/api/datasources",
                grafana_datasource._get_json_data("test", "type", "url"),
                headers={
                    "Authorization": "Bearer token",
                    "Accept": "application/json",
                },
                timeout=3,
            )
            assert ret["result"]
            assert ret["comment"] == "New data source test added"

    data = grafana_datasource._get_json_data("test", "type", "url")
    data.update({"id": 1, "orgId": 1})
    with patch("requests.get", mock_json_response([data])):
        with patch("requests.put") as rput:
            ret = grafana_datasource.present("test", "type", "url", profile=profile)
            rput.assert_called_once_with(
                "http://grafana/api/datasources/1",
                grafana_datasource._get_json_data("test", "type", "url"),
                headers={
                    "Authorization": "Bearer token",
                    "Accept": "application/json",
                },
                timeout=3,
            )
            assert ret["result"]
            assert ret["comment"] == "Data source test already up-to-date"
            assert ret["changes"] == {}

        with patch("requests.put") as rput:
            ret = grafana_datasource.present("test", "type", "newurl", profile=profile)
            rput.assert_called_once_with(
                "http://grafana/api/datasources/1",
                grafana_datasource._get_json_data("test", "type", "newurl"),
                headers={
                    "Authorization": "Bearer token",
                    "Accept": "application/json",
                },
                timeout=3,
            )
            assert ret["result"]
            assert ret["comment"] == "Data source test updated"
            assert ret["changes"] == {"old": {"url": "url"}, "new": {"url": "newurl"}}


def test_absent():
    with patch("requests.get", mock_json_response([])):
        with patch("requests.delete") as rdelete:
            ret = grafana_datasource.absent("test", profile=profile)
            assert rdelete.call_count == 0
            assert ret["result"]
            assert ret["comment"] == "Data source test already absent"

    with patch("requests.get", mock_json_response([{"name": "test", "id": 1}])):
        with patch("requests.delete") as rdelete:
            ret = grafana_datasource.absent("test", profile=profile)
            rdelete.assert_called_once_with(
                "http://grafana/api/datasources/1",
                headers={
                    "Authorization": "Bearer token",
                    "Accept": "application/json",
                },
                timeout=3,
            )
            assert ret["result"]
            assert ret["comment"] == "Data source test was deleted"
