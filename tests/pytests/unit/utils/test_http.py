import pytest
import requests
import salt.utils.http
from tests.support.mock import MagicMock, patch


def test_requests_session_verify_ssl_false(ssl_webserver, integration_files_dir):
    """
    test salt.utils.http.session when using verify_ssl
    """
    for verify in [True, False, None]:
        kwargs = {"verify_ssl": verify}
        if verify is None:
            kwargs.pop("verify_ssl")

        if verify is True or verify is None:
            with pytest.raises(requests.exceptions.SSLError) as excinfo:
                session = salt.utils.http.session(**kwargs)
                ret = session.get(ssl_webserver.url("this.txt"))
        else:
            session = salt.utils.http.session(**kwargs)
            ret = session.get(ssl_webserver.url("this.txt"))
            assert ret.status_code == 200


def test_session_ca_bundle_verify_false():
    """
    test salt.utils.http.session when using
    both ca_bunlde and verify_ssl false
    """
    ret = salt.utils.http.session(ca_bundle="/tmp/test_bundle", verify_ssl=False)
    assert ret is False


def test_session_headers():
    """
    test salt.utils.http.session when setting
    headers
    """
    ret = salt.utils.http.session(headers={"Content-Type": "application/json"})
    assert ret.headers["Content-Type"] == "application/json"


def test_session_ca_bundle():
    """
    test salt.utils.https.session when setting ca_bundle
    """
    fpath = "/tmp/test_bundle"
    patch_os = patch("os.path.exists", MagicMock(return_value=True))
    with patch_os:
        ret = salt.utils.http.session(ca_bundle=fpath)
    assert ret.verify == fpath
