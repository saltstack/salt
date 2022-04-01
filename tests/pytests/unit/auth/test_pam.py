import pytest
import salt.auth.pam
from tests.support.mock import patch

@pytest.fixture
def configure_loader_modules():
    return {salt.auth.pam: {}}


@pytest.fixture
def mock_pam():
    with patch('salt.auth.pam.CALLOC', autospec=True
            ), patch('salt.auth.pam.pointer', autospec=True
            ), patch('salt.auth.pam.PamHandle', autospec=True
            ), patch('salt.auth.pam.PAM_START', autospec=True, return_value=0
            ), patch('salt.auth.pam.PAM_AUTHENTICATE', autospec=True, return_value=0
            ), patch('salt.auth.pam.PAM_END', autospec=True
                    ):
        yield 


@pytest.mark.xfail
def test_cve_if_pam_acct_mgmt_returns_nonzero_authenticate_should_be_false(mock_pam):
    with patch('salt.auth.pam.PAM_ACCT_MGMT', autospec=True, return_value=42):
        assert salt.auth.pam.authenticate(username='fnord', password='fnord') is False


def test_if_pam_acct_mgmt_returns_zero_authenticate_should_be_true(mock_pam):
    with patch('salt.auth.pam.PAM_ACCT_MGMT', autospec=True, return_value=0):
        assert salt.auth.pam.authenticate(username='fnord', password='fnord') is True

