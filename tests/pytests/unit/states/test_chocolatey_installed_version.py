"""
Regression test for chocolatey.installed forcing reinstall (#68827).

chocolatey.list returns ``{name: [version, ...]}`` (lists per package),
so indexing the dict gave the state a list where a string was expected.
``salt.utils.versions.compare(ver1=[ver], oper="==", ver2=ver)`` then
returned False, the "matches installed version" branch never fired,
and force=True was set causing reinstall every run.
"""

import pytest

import salt.modules.chocolatey as chocolatey_mod
import salt.states.chocolatey as chocolatey
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules(minion_opts):
    minion_opts["test"] = True
    return {
        chocolatey: {
            "__opts__": minion_opts,
            "__salt__": {},
            "__context__": {},
        },
        chocolatey_mod: {
            "__opts__": minion_opts,
            "__context__": {},
        },
    }


def test_installed_does_not_reinstall_when_version_matches():
    """
    chocolatey.installed must report "already installed" and not
    trigger an install when the requested version matches what
    chocolatey.list reports as installed.
    """
    list_return = {"vim": ["9.0.1672"]}
    install_mock = MagicMock(return_value="installed ok")
    salt_dunder = {
        "chocolatey.list": MagicMock(return_value=list_return),
        "chocolatey.install": install_mock,
    }
    with patch.dict(chocolatey.__salt__, salt_dunder):
        ret = chocolatey.installed(name="vim", version="9.0.1672")
    assert ret["result"] is None
    assert "is already installed" in ret["comment"]
    assert "will be installed over" not in ret["comment"]
    install_mock.assert_not_called()
