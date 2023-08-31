import pytest

import salt.utils.json
from salt.modules import http
from salt.pillar import http_yaml


@pytest.fixture
def configure_loader_modules():
    return {
        http_yaml: {
            "__salt__": {
                "http.query": http.query,
            },
        },
        http: {
            "__opts__": {},
        },
    }


@pytest.mark.requires_network
@pytest.mark.parametrize("backend", ["requests", "tornado", "urllib2"])
def test_ext_pillar_can_take_http_query_kwargs(backend, httpserver):
    response = {
        "dict": {
            "backend": backend,
            "pillar_type": "http_yaml",
        },
    }
    header_dict = {"custom-backend-header": backend}

    # If the headers in header_dict are not in the request, httpserver will return an empty dictionary, so we know it will fail
    httpserver.expect_request(
        "/http_yaml_pillar/{}".format(backend),
        headers={"custom-backend-header": backend},
    ).respond_with_data(salt.utils.json.dumps(response), content_type="text/plain")
    url = httpserver.url_for("/http_yaml_pillar/{}".format(backend))

    actual = http_yaml.ext_pillar("test-minion-id", {}, url, header_dict=header_dict)
    assert actual == response
