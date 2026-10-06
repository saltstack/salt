"""
Tests for salt.modules.rpmbuild_pkgbuild
"""

import pytest

import salt.modules.rpmbuild_pkgbuild as rpmbuild_pkgbuild
import salt.utils.secret
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.skip_on_windows(reason="rpm-only module"),
]

GPG_PILLAR = {
    "gpg_pkg_pub_keyname": "gpg_pkg_key.pub",
    "gpg_pkg_priv_keyname": "gpg_pkg_key.pem",
    "gpg_passphrase": "sup3r_s3cr3t",
}


@pytest.fixture
def configure_loader_modules():
    return {
        rpmbuild_pkgbuild: {
            "__grains__": {"os_family": "RedHat", "osmajorrelease": 7},
        }
    }


def _masking_pillar_get(key, default=None, **kwargs):
    """
    Mimic 3008 pillar.get masking: scalar strings are redacted unless the
    caller passes unmask=True.
    """
    value = GPG_PILLAR.get(key, default)
    if kwargs.get("unmask"):
        return salt.utils.secret.expose(value)
    return salt.utils.secret.serial(value)


def test_get_gpg_key_resources_unmasks_pillar_values():
    """
    _get_gpg_key_resources must read the gpg key filenames and passphrase
    with unmask=True, otherwise gpg gets fed the redact placeholder.
    """
    import_key_mock = MagicMock(return_value=True)
    list_keys_mock = MagicMock(
        return_value=[
            {
                "keyid": "AAAAAAAA07123E1F",
                "fingerprint": "1234567890ABCDEF1234567890ABCDEF07123E1F",
                "uids": ["Packaging Key <pkg@example.com>"],
            }
        ]
    )
    retcode_mock = MagicMock(return_value=0)
    salt_dunder = {
        "pillar.get": _masking_pillar_get,
        "gpg.import_key": import_key_mock,
        "gpg.list_keys": list_keys_mock,
        "cmd.retcode": retcode_mock,
        "cmd.run": MagicMock(return_value=""),
    }

    with patch.dict(rpmbuild_pkgbuild.__salt__, salt_dunder):
        use_gpg_agent, local_keyid, define_gpg_name, phrase = (
            rpmbuild_pkgbuild._get_gpg_key_resources(
                keyid="07123E1F",
                env={},
                use_passphrase=True,
                gnupghome="/etc/salt/gpgkeys",
                runas="root",
            )
        )

    assert use_gpg_agent is False
    assert local_keyid == "AAAAAAAA07123E1F"

    # the passphrase handed back for signing must be the real value
    assert phrase == GPG_PILLAR["gpg_passphrase"]
    assert salt.utils.secret.REDACT_PLACEHOLDER not in phrase

    # key files imported into gpg must carry the real pillar filenames
    imported = [call.kwargs["filename"] for call in import_key_mock.call_args_list]
    assert "/etc/salt/gpgkeys/gpg_pkg_key.pub" in imported
    assert "/etc/salt/gpgkeys/gpg_pkg_key.pem" in imported
    for filename in imported:
        assert salt.utils.secret.REDACT_PLACEHOLDER not in filename

    # rpm --import must reference the real public key file
    rpm_import_cmd = retcode_mock.call_args_list[0].args[0]
    assert rpm_import_cmd == "rpm --import /etc/salt/gpgkeys/gpg_pkg_key.pub"
