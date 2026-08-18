import pytest

import salt.proxy.restconf as restconf
from tests.support.mock import patch


@pytest.fixture
def configure_loader_modules():
    return {restconf: {}}


@pytest.fixture
def patch_conn_args():
    with patch.dict(
        restconf.restconf_device,
        {
            "conn_args": {
                "hostname": None,
                "transport": None,
                "verify": None,
                "username": None,
                "password": None,
            }
        },
    ):
        yield


@pytest.fixture
def fake_query():
    with patch("salt.utils.http.query", autospec=True) as fake_query:
        yield fake_query


def test_result_of_request_should_be_returned(patch_conn_args, fake_query):
    expected_result = object()
    fake_query.return_value = expected_result
    result = restconf.request("https://example.com")
    assert result is expected_result


def test_if_None_is_provided_as_dict_payload_then_empty_string_should_be_provided_instead(
    patch_conn_args, fake_query
):
    expected_data = ""
    restconf.request("https://example.com", dict_payload=None)
    call = fake_query.mock_calls[0]

    assert call.kwargs["data"] == expected_data


def test_if_text_is_provided_as_dict_payload_then_provided_string_should_be_used(
    patch_conn_args, fake_query
):
    expected_data = "this is my fake payload"
    restconf.request("https://example.com", dict_payload=expected_data)
    call = fake_query.mock_calls[0]

    assert call.kwargs["data"] == expected_data


def test_if_dict_is_provided_as_dict_payload_then_json_text_should_be_provided(
    patch_conn_args, fake_query
):
    dict_payload = {"fnord": "something", "cool": "beans"}
    expected_data = '{"fnord": "something", "cool": "beans"}'
    restconf.request("https://example.com", dict_payload=dict_payload)
    call = fake_query.mock_calls[0]
    import json

    actual_data = json.loads(call.kwargs["data"])

    assert call.kwargs["data"] == expected_data
    assert actual_data == dict_payload


def test_if_proxy_def_connectiontest_passes_correctly(patch_conn_args, fake_query):
    fake_query.return_value = """{'body': '{\n    "ietf-restconf:yang-library-version": "2016-06-21"\n}', 'status': 200, 'dict': {'ietf-restconf:yang-library-version': '2016-06-21'}}"""
    result = restconf.connection_test()
    assert result[0] is True
    assert "yang-library-version" in result[1]


def test_if_proxy_def_connectiontest_fails_correctly(patch_conn_args, fake_query):
    fake_query.return_value = """{'body': 'fnord', 'status': 200 }"""
    result = restconf.connection_test()
    assert result[0] is False
    assert "yang-library-version" not in result[1]
