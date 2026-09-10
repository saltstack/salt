"""
Tests for salt.modules.debuild_pkgbuild
"""

import pytest

import salt.modules.debuild_pkgbuild as debuild_pkgbuild
import salt.utils.secret
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.skip_on_windows(reason="deb-only module"),
]

GPG_PILLAR = {
    "gpg_pkg_pub_keyname": "gpg_pkg_key.pub",
    "gpg_pkg_priv_keyname": "gpg_pkg_key.pem",
    "gpg_passphrase": "sup3r_s3cr3t",
}


@pytest.fixture
def configure_loader_modules():
    return {
        debuild_pkgbuild: {
            "__grains__": {"os": "Debian", "osmajorrelease": 11},
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


def test_make_repo_unmasks_gpg_pillar_values(tmp_path):
    """
    make_repo must read the gpg key filenames and passphrase with
    unmask=True, otherwise gpg-preset-passphrase and gpg.import_key
    get fed the redact placeholder.
    """
    repodir = tmp_path / "repo"
    repodir.mkdir()
    gnupghome = tmp_path / "gpgkeys"
    gnupghome.mkdir()
    # older-gnupg path: agent info file must exist and be readable
    (gnupghome / "gpg-agent-info-salt").write_text(
        "GPG_AGENT_INFO=/run/user/0/gnupg/S.gpg-agent:0:1\n"
    )

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
        "file.file_exists": MagicMock(return_value=True),
    }

    with patch.dict(debuild_pkgbuild.__salt__, salt_dunder), patch.object(
        debuild_pkgbuild, "_check_repo_sign_utils_support", MagicMock(return_value=True)
    ), patch.object(
        debuild_pkgbuild, "_check_repo_gpg_phrase_utils", MagicMock(return_value=True)
    ):
        debuild_pkgbuild.make_repo(
            str(repodir),
            keyid="07123E1F",
            use_passphrase=True,
            gnupghome=str(gnupghome),
        )

    # key files imported into gpg must carry the real pillar filenames
    imported = [call.kwargs["filename"] for call in import_key_mock.call_args_list]
    assert f"{gnupghome}/gpg_pkg_key.pub" in imported
    assert f"{gnupghome}/gpg_pkg_key.pem" in imported
    for filename in imported:
        assert salt.utils.secret.REDACT_PLACEHOLDER not in filename

    # gpg-preset-passphrase must be invoked with the real passphrase
    preset_cmds = [
        call.args[0]
        for call in retcode_mock.call_args_list
        if "gpg-preset-passphrase" in call.args[0]
    ]
    assert len(preset_cmds) == 1
    assert GPG_PILLAR["gpg_passphrase"] in preset_cmds[0]
    assert salt.utils.secret.REDACT_PLACEHOLDER not in preset_cmds[0]
