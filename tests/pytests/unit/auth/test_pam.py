import pytest

import salt.auth.pam
from tests.support.mock import patch

pytestmark = [
    pytest.mark.skip_on_windows,
]


@pytest.fixture
def configure_loader_modules():
    return {salt.auth.pam: {}}


@pytest.fixture
def mock_pam():
    with patch("salt.auth.pam.CALLOC", autospec=True), patch(
        "salt.auth.pam.pointer", autospec=True
    ), patch("salt.auth.pam.PamHandle", autospec=True), patch(
        "salt.auth.pam.PAM_START", autospec=True, return_value=0
    ), patch(
        "salt.auth.pam.PAM_AUTHENTICATE", autospec=True, return_value=0
    ), patch(
        "salt.auth.pam.PAM_END", autospec=True
    ):
        yield


def test_cve_if_pam_acct_mgmt_returns_nonzero_authenticate_should_be_false(mock_pam):
    with patch("salt.auth.pam.PAM_ACCT_MGMT", autospec=True, return_value=42):
        assert (
            salt.auth.pam._authenticate(
                username="fnord", password="fnord", service="login", encoding="utf-8"
            )
            is False
        )


def test_if_pam_acct_mgmt_returns_zero_authenticate_should_be_true(mock_pam):
    with patch("salt.auth.pam.PAM_ACCT_MGMT", autospec=True, return_value=0):
        assert (
            salt.auth.pam._authenticate(
                username="fnord", password="fnord", service="login", encoding="utf-8"
            )
            is True
        )
