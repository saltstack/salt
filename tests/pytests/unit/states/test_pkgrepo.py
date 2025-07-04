"""
    :codeauthor: Tyler Johnson <tjohnson@saltstack.com>
"""

import pytest

import salt.states.pkgrepo as pkgrepo
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        pkgrepo: {
            "__opts__": {"test": True},
            "__grains__": {"os": "", "os_family": ""},
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
