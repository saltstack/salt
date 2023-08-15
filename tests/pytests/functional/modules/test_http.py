import pytest

import salt.modules.http as http


@pytest.fixture
def configure_loader_modules():
    return {http: {}}


def test_query_error_tornado(webserver):
    """
    Ensure we return expected data when website does not return
    a 200 with tornado
    """
    url = webserver.url("doesnotexist")
    ret = http.query(url, backend="tornado")
    assert (
        ret["body"]
        == "<html><title>404: Not Found</title><body>404: Not Found</body></html>"
    )
    assert ret["error"] == "HTTP 404: Not Found"
    assert ret["status"] == 404


@pytest.mark.parametrize("backend", ["requests", "urllib2", "tornado"])
def test_query_success(webserver, backend):
    """
    Ensure we return a success when querying
    a website
    """
    url = webserver.url("this.txt")
    ret = http.query(url, backend=backend)
    assert ret == {"body": "test"}
