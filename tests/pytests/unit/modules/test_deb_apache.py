"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""


import pytest

import salt.modules.deb_apache as deb_apache
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {deb_apache: {}}


# 'check_site_enabled' function tests: 3


def test_check_site_enabled():
    """
    Test if the specific Site symlink is enabled.
    """
    with patch("os.path.islink", MagicMock(return_value=True)):
        assert deb_apache.check_site_enabled("saltstack.com")


def test_check_site_enabled_default():
    """
    Test if the specific Site symlink is enabled.
    """
    with patch("os.path.islink", MagicMock(side_effect=[False, True])):
        assert deb_apache.check_site_enabled("default")


def test_check_site_enabled_false():
    """
    Test if the specific Site symlink is enabled.
    """
    with patch("os.path.islink", MagicMock(return_value=False)):
        assert not deb_apache.check_site_enabled("saltstack.com")


# 'a2ensite' function tests: 4


def test_a2ensite_notfound():
    """
    Test if it runs a2ensite for the given site.
    """
    mock = MagicMock(return_value=1)
    with patch.dict(deb_apache.__salt__, {"cmd.retcode": mock}):
        assert deb_apache.a2ensite("saltstack.com") == {
            "Name": "Apache2 Enable Site",
            "Site": "saltstack.com",
            "Status": "Site saltstack.com Not found",
        }


def test_a2ensite_enabled():
    """
    Test if it runs a2ensite for the given site.
    """
    mock = MagicMock(return_value=0)
    with patch.dict(deb_apache.__salt__, {"cmd.retcode": mock}):
        assert deb_apache.a2ensite("saltstack.com") == {
            "Name": "Apache2 Enable Site",
            "Site": "saltstack.com",
            "Status": "Site saltstack.com enabled",
        }


def test_a2ensite():
    """
    Test if it runs a2ensite for the given site.
    """
    mock = MagicMock(return_value=2)
    with patch.dict(deb_apache.__salt__, {"cmd.retcode": mock}):
        assert deb_apache.a2ensite("saltstack.com") == {
            "Name": "Apache2 Enable Site",
            "Site": "saltstack.com",
            "Status": 2,
        }


def test_a2ensite_exception():
    """
    Test if it runs a2ensite for the given site.
    """
    mock = MagicMock(side_effect=Exception("error"))
    with patch.dict(deb_apache.__salt__, {"cmd.retcode": mock}):
        assert str(deb_apache.a2ensite("saltstack.com")) == "error"


# 'a2dissite' function tests: 4


def test_a2dissite_notfound():
    """
    Test if it runs a2dissite for the given site.
    """
    mock = MagicMock(return_value=256)
    with patch.dict(deb_apache.__salt__, {"cmd.retcode": mock}):
        assert deb_apache.a2dissite("saltstack.com") == {
            "Name": "Apache2 Disable Site",
            "Site": "saltstack.com",
            "Status": "Site saltstack.com Not found",
        }


def test_a2dissite_disabled():
    """
    Test if it runs a2dissite for the given site.
    """
    mock = MagicMock(return_value=0)
    with patch.dict(deb_apache.__salt__, {"cmd.retcode": mock}):
        assert deb_apache.a2dissite("saltstack.com") == {
            "Name": "Apache2 Disable Site",
            "Site": "saltstack.com",
            "Status": "Site saltstack.com disabled",
        }


def test_a2dissite():
    """
    Test if it runs a2dissite for the given site.
    """
    mock = MagicMock(return_value=2)
    with patch.dict(deb_apache.__salt__, {"cmd.retcode": mock}):
        assert deb_apache.a2dissite("saltstack.com") == {
            "Name": "Apache2 Disable Site",
            "Site": "saltstack.com",
            "Status": 2,
        }


def test_a2dissite_exception():
    """
    Test if it runs a2dissite for the given site.
    """
    mock = MagicMock(side_effect=Exception("error"))
    with patch.dict(deb_apache.__salt__, {"cmd.retcode": mock}):
        assert str(deb_apache.a2dissite("saltstack.com")) == "error"


# 'check_mod_enabled' function tests: 2


def test_check_mod_enabled():
    """
    Test if the specific mod symlink is enabled.
    """
    with patch("os.path.islink", MagicMock(return_value=True)):
        assert deb_apache.check_mod_enabled("status.conf")


def test_check_mod_enabled_false():
    """
    Test if the specific mod symlink is enabled.
    """
    with patch("os.path.islink", MagicMock(return_value=False)):
        assert not deb_apache.check_mod_enabled("status.conf")


# 'a2enmod' function tests: 4


def test_a2enmod_notfound():
    """
    Test if it runs a2enmod for the given module.
    """
    mock = MagicMock(return_value=1)
    with patch.dict(deb_apache.__salt__, {"cmd.retcode": mock}):
        assert deb_apache.a2enmod("vhost_alias") == {
            "Name": "Apache2 Enable Mod",
            "Mod": "vhost_alias",
            "Status": "Mod vhost_alias Not found",
        }


def test_a2enmod_enabled():
    """
    Test if it runs a2enmod for the given module.
    """
    mock = MagicMock(return_value=0)
    with patch.dict(deb_apache.__salt__, {"cmd.retcode": mock}):
        assert deb_apache.a2enmod("vhost_alias") == {
            "Name": "Apache2 Enable Mod",
            "Mod": "vhost_alias",
            "Status": "Mod vhost_alias enabled",
        }


def test_a2enmod():
    """
    Test if it runs a2enmod for the given module.
    """
    mock = MagicMock(return_value=2)
    with patch.dict(deb_apache.__salt__, {"cmd.retcode": mock}):
        assert deb_apache.a2enmod("vhost_alias") == {
            "Name": "Apache2 Enable Mod",
            "Mod": "vhost_alias",
            "Status": 2,
        }


def test_a2enmod_exception():
    """
    Test if it runs a2enmod for the given module.
    """
    mock = MagicMock(side_effect=Exception("error"))
    with patch.dict(deb_apache.__salt__, {"cmd.retcode": mock}):
        assert str(deb_apache.a2enmod("vhost_alias")) == "error"


# 'a2dismod' function tests: 4


def test_a2dismod_notfound():
    """
    Test if it runs a2dismod for the given module.
    """
    mock = MagicMock(return_value=256)
    with patch.dict(deb_apache.__salt__, {"cmd.retcode": mock}):
        assert deb_apache.a2dismod("vhost_alias") == {
            "Name": "Apache2 Disable Mod",
            "Mod": "vhost_alias",
            "Status": "Mod vhost_alias Not found",
        }


def test_a2dismod_disabled():
    """
    Test if it runs a2dismod for the given module.
    """
    mock = MagicMock(return_value=0)
    with patch.dict(deb_apache.__salt__, {"cmd.retcode": mock}):
        assert deb_apache.a2dismod("vhost_alias") == {
            "Name": "Apache2 Disable Mod",
            "Mod": "vhost_alias",
            "Status": "Mod vhost_alias disabled",
        }


def test_a2dismod():
    """
    Test if it runs a2dismod for the given module.
    """
    mock = MagicMock(return_value=2)
    with patch.dict(deb_apache.__salt__, {"cmd.retcode": mock}):
        assert deb_apache.a2dismod("vhost_alias") == {
            "Name": "Apache2 Disable Mod",
            "Mod": "vhost_alias",
            "Status": 2,
        }


def test_a2dismod_exception():
    """
    Test if it runs a2dismod for the given module.
    """
    mock = MagicMock(side_effect=Exception("error"))
    with patch.dict(deb_apache.__salt__, {"cmd.retcode": mock}):
        assert str(deb_apache.a2dismod("vhost_alias")) == "error"


# 'check_conf_enabled' function tests: 2


def test_check_conf_enabled():
    """
    Test if the specific conf symlink is enabled.
    """
    with patch("os.path.islink", MagicMock(return_value=True)):
        assert deb_apache.check_conf_enabled("security.conf")


def test_check_conf_enabled_false():
    """
    Test if the specific conf symlink is enabled.
    """
    with patch("os.path.islink", MagicMock(return_value=False)):
        assert not deb_apache.check_conf_enabled("security.conf")


# 'a2enconf' function tests: 4


def test_a2enconf_notfound():
    """
    Test if it runs a2enconf for the given conf.
    """
    with patch("salt.utils.path.which", MagicMock(return_value="a2enconf")):
        mock = MagicMock(return_value=1)
        with patch.dict(deb_apache.__salt__, {"cmd.retcode": mock}):
            assert deb_apache.a2enconf("security") == {
                "Name": "Apache2 Enable Conf",
                "Conf": "security",
                "Status": "Conf security Not found",
            }


def test_a2enconf_enabled():
    """
    Test if it runs a2enconf for the given conf.
    """
    with patch("salt.utils.path.which", MagicMock(return_value="a2enconf")):
        mock = MagicMock(return_value=0)
        with patch.dict(deb_apache.__salt__, {"cmd.retcode": mock}):
            assert deb_apache.a2enconf("security") == {
                "Name": "Apache2 Enable Conf",
                "Conf": "security",
                "Status": "Conf security enabled",
            }


def test_a2enconf():
    """
    Test if it runs a2enconf for the given conf.
    """
    with patch("salt.utils.path.which", MagicMock(return_value="a2enconf")):
        mock = MagicMock(return_value=2)
        with patch.dict(deb_apache.__salt__, {"cmd.retcode": mock}):
            assert deb_apache.a2enconf("security") == {
                "Name": "Apache2 Enable Conf",
                "Conf": "security",
                "Status": 2,
            }


def test_a2enconf_exception():
    """
    Test if it runs a2enconf for the given conf.
    """
    with patch("salt.utils.path.which", MagicMock(return_value="a2enconf")):
        mock = MagicMock(side_effect=Exception("error"))
        with patch.dict(deb_apache.__salt__, {"cmd.retcode": mock}):
            assert str(deb_apache.a2enconf("security")) == "error"


# 'a2disconf' function tests: 4


def test_a2disconf_notfound():
    """
    Test if it runs a2disconf for the given conf.
    """
    with patch("salt.utils.path.which", MagicMock(return_value="a2disconf")):
        mock = MagicMock(return_value=256)
        with patch.dict(deb_apache.__salt__, {"cmd.retcode": mock}):
            assert deb_apache.a2disconf("security") == {
                "Name": "Apache2 Disable Conf",
                "Conf": "security",
                "Status": "Conf security Not found",
            }


def test_a2disconf_disabled():
    """
    Test if it runs a2disconf for the given conf.
    """
    with patch("salt.utils.path.which", MagicMock(return_value="a2disconf")):
        mock = MagicMock(return_value=0)
        with patch.dict(deb_apache.__salt__, {"cmd.retcode": mock}):
            assert deb_apache.a2disconf("security") == {
                "Name": "Apache2 Disable Conf",
                "Conf": "security",
                "Status": "Conf security disabled",
            }


def test_a2disconf():
    """
    Test if it runs a2disconf for the given conf.
    """
    with patch("salt.utils.path.which", MagicMock(return_value="a2disconf")):
        mock = MagicMock(return_value=2)
        with patch.dict(deb_apache.__salt__, {"cmd.retcode": mock}):
            assert deb_apache.a2disconf("security") == {
                "Name": "Apache2 Disable Conf",
                "Conf": "security",
                "Status": 2,
            }


def test_a2disconf_exception():
    """
    Test if it runs a2disconf for the given conf.
    """
    with patch("salt.utils.path.which", MagicMock(return_value="a2disconf")):
        mock = MagicMock(side_effect=Exception("error"))
        with patch.dict(deb_apache.__salt__, {"cmd.retcode": mock}):
            assert str(deb_apache.a2disconf("security")) == "error"
