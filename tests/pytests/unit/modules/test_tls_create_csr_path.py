"""
Regression test for #60877 / PR #68835.

When ``csr_path`` lacks a trailing slash, the return/log message from
``tls.create_csr`` must still produce a path with a proper separator
between the directory and the filename.

Pre-fix:  f"{csr_path}{csr_filename}.key" -> "/etc/ssl/MYCA/certsMY.key"
Post-fix: f"{os.path.join(csr_path, csr_filename)}.key"
         -> "/etc/ssl/MYCA/certs/MY.key"
"""

import os

import pytest

import salt.modules.tls as tls
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {tls: {}}


@pytest.fixture(scope="module")
def csr_kwargs():
    return {
        "bits": 2048,
        "CN": "MY.HOSTNAME",
        "C": "US",
        "ST": "Utah",
        "L": "Salt Lake City",
        "O": "SaltStack",
        "OU": "Test Unit",
        "emailAddress": "xyz@pdq.net",
        "digest": "sha256",
        "replace": False,
    }


@pytest.mark.skip_on_windows(reason="POSIX path separators are the bug under test")
def test_create_csr_return_message_uses_separator_when_csr_path_has_no_trailing_slash(
    tmp_path, csr_kwargs
):
    """
    Pins the fix for #60877: the return message must contain
    '<csr_path>/<csr_filename>.key' and '...csr', not concatenation.
    """
    ca_path = tmp_path
    ca_name = "test_ca"
    csr_dir = ca_path / ca_name / "certs"  # no trailing slash
    csr_dir.mkdir(parents=True, exist_ok=True)

    mock_opt = MagicMock(return_value=str(ca_path))
    mock_ret = MagicMock(return_value=0)
    mock_pgt = MagicMock(return_value=False)

    with patch.dict(
        tls.__salt__,
        {
            "config.option": mock_opt,
            "cmd.retcode": mock_ret,
            "pillar.get": mock_pgt,
        },
    ), patch.dict(
        tls.__opts__, {"hash_type": "sha256", "cachedir": str(ca_path)}
    ), patch(
        "salt.modules.tls.maybe_fix_ssl_version", MagicMock(return_value=True)
    ):
        tls.create_ca(ca_name)
        ret = tls.create_csr(ca_name, csr_path=str(csr_dir), **csr_kwargs)

    expected_key = os.path.join(str(csr_dir), csr_kwargs["CN"]) + ".key"
    expected_csr = os.path.join(str(csr_dir), csr_kwargs["CN"]) + ".csr"

    # Post-fix: separator present.
    assert f'Created Private Key: "{expected_key}"' in ret
    assert f'Created CSR for "{csr_kwargs["CN"]}": "{expected_csr}"' in ret

    # Pre-fix: would have produced "certsMY.HOSTNAME.key" (no separator).
    bad_key = f"{csr_dir}{csr_kwargs['CN']}.key"
    bad_csr = f"{csr_dir}{csr_kwargs['CN']}.csr"
    assert bad_key not in ret
    assert bad_csr not in ret
