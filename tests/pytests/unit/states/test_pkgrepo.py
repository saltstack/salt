"""
    :codeauthor: Tyler Johnson <tjohnson@saltstack.com>
"""

import pytest

import salt.states.pkgrepo as pkgrepo
import salt.utils.files
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        pkgrepo: {
            "__opts__": {"test": True},
            "__grains__": {"os": "", "os_family": ""},
            "__env__": "base",
        }
    }


def test_name_change():
    """
    Test when only the key_url is changed that a change is triggered
    """
    kwargs = {
        "name": "deb http://apt.example.com/{{grains['os'] | lower}} {{grains['oscodename']}} main",
        "disabled": False,
        "key_url": "https://mock/changed_gpg.key",
    }

    new = kwargs.copy()
    new["name"] = (
        "deb [arch=amd64] http://apt.example.com/{{grains['os'] | lower}} {{grains['oscodename']}} main"
    )

    with patch.dict(pkgrepo.__salt__, {"pkg.get_repo": MagicMock(return_value=kwargs)}):
        ret = pkgrepo.managed(**new)
        assert ret["changes"] == {"name": {"old": kwargs["name"], "new": new["name"]}}


def test_new_key_url():
    """
    Test when only the key_url is changed that a change is triggered
    """
    kwargs = {
        "name": "deb https://mock/ sid main",
        "disabled": False,
    }
    key_url = "https://mock/changed_gpg.key"

    with patch.dict(pkgrepo.__salt__, {"pkg.get_repo": MagicMock(return_value=kwargs)}):
        ret = pkgrepo.managed(key_url=key_url, **kwargs)
        assert ret["changes"] == {"key_url": {"old": None, "new": key_url}}


def test_update_key_url():
    """
    Test when only the key_url is changed that a change is triggered
    """
    kwargs = {
        "name": "deb https://mock/ sid main",
        "gpgcheck": 1,
        "disabled": False,
        "key_url": "https://mock/gpg.key",
    }
    changed_kwargs = kwargs.copy()
    changed_kwargs["key_url"] = "https://mock/gpg2.key"

    with patch.dict(pkgrepo.__salt__, {"pkg.get_repo": MagicMock(return_value=kwargs)}):
        ret = pkgrepo.managed(**changed_kwargs)
        assert "key_url" in ret["changes"], "Expected a change to key_url"
        assert ret["changes"] == {
            "key_url": {"old": kwargs["key_url"], "new": changed_kwargs["key_url"]}
        }


def test_managed_insecure_key():
    """
    Test when only the key_url is changed that a change is triggered
    """
    kwargs = {
        "name": "deb http://mock/ sid main",
        "gpgcheck": 1,
        "disabled": False,
        "key_url": "http://mock/gpg.key",
        "allow_insecure_key": False,
    }
    with patch.dict(pkgrepo.__salt__, {"pkg.get_repo": MagicMock(return_value=kwargs)}):
        ret = pkgrepo.managed(**kwargs)
        assert ret["result"] is False
        assert (
            ret["comment"]
            == "Cannot have 'key_url' using http with 'allow_insecure_key' set to True"
        )


def test_managed_clean_file_with_matching_existing_repo_68208(tmp_path):
    """
    Regression test for #68208.

    When pkgrepo.managed is called with ``clean_file: True`` and the desired
    repo line already exists in the file *alongside other stale lines*,
    the state must still empty the file and reconfigure the repo. Prior to
    the fix it would return ``already configured`` and silently skip the
    clean+reconfigure, leaving the stale lines in place.
    """
    backports_file = tmp_path / "backports.list"
    desired_line = "deb http://deb.debian.org/debian bookworm-backports main"
    stale_line = "deb http://deb.debian.org/debian bullseye-backports main"
    backports_file.write_text(stale_line + "\n" + desired_line + "\n")

    kwargs = {
        "name": desired_line,
        "disabled": False,
        "file": str(backports_file),
        "clean_file": True,
    }
    # pkg.get_repo returns the matching definition because the desired
    # line is already present (along with an unrelated stale entry).
    get_repo = MagicMock(return_value=kwargs.copy())
    mod_repo = MagicMock(return_value=None)

    # We want salt.utils.files.fopen to behave normally for the file-read
    # (probing for stale content) but be observable for the "w" truncation
    # call. Use a wrapper that delegates to the real fopen.
    real_fopen = salt.utils.files.fopen
    fopen_calls = []

    def _track_fopen(*args, **kw):
        fopen_calls.append((args, kw))
        return real_fopen(*args, **kw)

    with patch.dict(
        pkgrepo.__salt__,
        {"pkg.get_repo": get_repo, "pkg.mod_repo": mod_repo},
    ), patch.dict(pkgrepo.__opts__, {"test": False}), patch.dict(
        pkgrepo.__grains__,
        {"os": "Debian", "os_family": "Debian", "oscodename": "bookworm"},
    ), patch(
        "salt.modules.aptpkg._expand_repo_def",
        MagicMock(side_effect=lambda os_name, os_codename, repo, **kw: kw),
    ), patch(
        "salt.utils.files.fopen", side_effect=_track_fopen
    ), patch(
        "salt.utils.path.which", MagicMock(return_value=None)
    ):
        ret = pkgrepo.managed(**kwargs)

    # The state must NOT short-circuit with "already configured" when
    # clean_file is requested and there is stale content in the file.
    assert ret["comment"] != (
        "Package repo '{}' already configured".format(kwargs["name"])
    )
    # The file must have been opened for writing (truncation) before
    # pkg.mod_repo is invoked.
    assert ((str(backports_file), "w"), {}) in fopen_calls
    # pkg.mod_repo must be called so the repo line is re-written to the
    # now-empty file.
    assert mod_repo.called


def test_managed_clean_file_with_only_desired_line_no_changes_68208(tmp_path):
    """
    Companion to #68208 regression. When ``clean_file: True`` is set and
    the managed file already contains exactly (and only) the desired repo
    line, the state must still short-circuit to "already configured" so
    repeated runs are idempotent. Without this, the fix for #68208 would
    falsely report a change on every run.
    """
    backports_file = tmp_path / "backports.list"
    desired_line = "deb http://deb.debian.org/debian bookworm-backports main"
    backports_file.write_text(desired_line + "\n")

    kwargs = {
        "name": desired_line,
        "disabled": False,
        "file": str(backports_file),
        "clean_file": True,
    }
    get_repo = MagicMock(return_value=kwargs.copy())
    mod_repo = MagicMock(return_value=None)

    with patch.dict(
        pkgrepo.__salt__,
        {"pkg.get_repo": get_repo, "pkg.mod_repo": mod_repo},
    ), patch.dict(pkgrepo.__opts__, {"test": False}), patch.dict(
        pkgrepo.__grains__,
        {"os": "Debian", "os_family": "Debian", "oscodename": "bookworm"},
    ), patch(
        "salt.modules.aptpkg._expand_repo_def",
        MagicMock(side_effect=lambda os_name, os_codename, repo, **kw: kw),
    ), patch(
        "salt.utils.path.which", MagicMock(return_value=None)
    ):
        ret = pkgrepo.managed(**kwargs)

    assert ret["comment"] == (
        "Package repo '{}' already configured".format(kwargs["name"])
    )
    assert ret["changes"] == {}
    assert not mod_repo.called
