import pytest

import salt.utils.pkg

CURRENT_PKGS = {
    "acl": "2.2.53-4",
    "adduser": "3.118",
    "apparmor": "2.13.2-10",
    "apt": "1.8.2.3",
    "apt-listchanges": "3.19",
    "apt-transport-https": "1.8.2.3",
    "apt-utils": "1.8.2.3",
    "base-files": "10.3+deb10u13",
    "base-passwd": "3.5.46",
    "bash": "5.0-4",
    "bash-completion": "1:2.8-6",
}


@pytest.mark.parametrize(
    "current_pkgs,pkg_params,expected",
    [
        [CURRENT_PKGS, {"apt": ""}, {"apt": ""}],
        [CURRENT_PKGS, {"foo": ""}, {"foo": ""}],
        [CURRENT_PKGS, {"bash*": ""}, {"bash": "", "bash-completion": ""}],
    ],
)
def test_match_wildcard(current_pkgs, pkg_params, expected):
    result = salt.utils.pkg.match_wildcard(current_pkgs, pkg_params)
    assert result == expected
