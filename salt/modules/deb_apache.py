"""
Support for Apache

Please note: The functions in here are Debian-specific. Placing them in this
separate file will allow them to load only on Debian-based systems, while still
loading under the ``apache`` namespace.
"""

import logging
import os

import salt.utils.decorators.path
import salt.utils.path

log = logging.getLogger(__name__)

__virtualname__ = "apache"

SITE_ENABLED_DIR = "/etc/apache2/sites-enabled"


def __virtual__():
    """
    Only load the module if apache is installed
    """
    cmd = _detect_os()
    if salt.utils.path.which(cmd) and __grains__["os_family"] == "Debian":
        return __virtualname__
    return (False, "apache execution module not loaded: apache not installed.")


def _detect_os():
    """
    Apache commands and paths differ depending on packaging
    """
    # TODO: Add pillar support for the apachectl location
    if __grains__["os_family"] == "RedHat":
        return "apachectl"
    elif __grains__["os_family"] == "Debian":
        return "apache2ctl"
    else:
        return "apachectl"


def check_site_enabled(site):
    """
    Checks to see if the specific site symlink is in /etc/apache2/sites-enabled.

    This will only be functional on Debian-based operating systems (Ubuntu,
    Mint, etc).

    CLI Examples:

    .. code-block:: bash

        salt '*' apache.check_site_enabled example.com
        salt '*' apache.check_site_enabled example.com.conf
    """
    if site.endswith(".conf"):
        site_file = site
    else:
        site_file = f"{site}.conf"
    if os.path.islink(f"{SITE_ENABLED_DIR}/{site_file}"):
        return True
    elif site == "default" and os.path.islink(f"{SITE_ENABLED_DIR}/000-{site_file}"):
        return True
    else:
        return False


def a2ensite(site):
    """
    Runs a2ensite for the given site.

    This will only be functional on Debian-based operating systems (Ubuntu,
    Mint, etc).

    CLI Examples:

    .. code-block:: bash

        salt '*' apache.a2ensite example.com
    """
    ret = {}
    command = ["a2ensite", site]

    try:
        status = __salt__["cmd.retcode"](command, python_shell=False)
    except Exception as e:  # pylint: disable=broad-except
        return e

    ret["Name"] = "Apache2 Enable Site"
    ret["Site"] = site

    if status == 1:
        ret["Status"] = f"Site {site} Not found"
    elif status == 0:
        ret["Status"] = f"Site {site} enabled"
    else:
        ret["Status"] = status

    return ret


def a2dissite(site):
    """
    Runs a2dissite for the given site.

    This will only be functional on Debian-based operating systems (Ubuntu,
    Mint, etc).

    CLI Examples:

    .. code-block:: bash

        salt '*' apache.a2dissite example.com
    """
    ret = {}
    command = ["a2dissite", site]

    try:
        status = __salt__["cmd.retcode"](command, python_shell=False)
    except Exception as e:  # pylint: disable=broad-except
        return e

    ret["Name"] = "Apache2 Disable Site"
    ret["Site"] = site

    if status == 256:
        ret["Status"] = f"Site {site} Not found"
    elif status == 0:
        ret["Status"] = f"Site {site} disabled"
    else:
        ret["Status"] = status

    return ret


def check_mod_enabled(mod):
    """
    Checks to see if the specific mod symlink is in /etc/apache2/mods-enabled.

    This will only be functional on Debian-based operating systems (Ubuntu,
    Mint, etc).

    CLI Examples:

    .. code-block:: bash

        salt '*' apache.check_mod_enabled status
        salt '*' apache.check_mod_enabled status.load
        salt '*' apache.check_mod_enabled status.conf
    """
    if mod.endswith(".load") or mod.endswith(".conf"):
        mod_file = mod
    else:
        mod_file = f"{mod}.load"
    return os.path.islink(f"/etc/apache2/mods-enabled/{mod_file}")


def a2enmod(mod):
    """
    Runs a2enmod for the given mod.

    This will only be functional on Debian-based operating systems (Ubuntu,
    Mint, etc).

    CLI Examples:

    .. code-block:: bash

        salt '*' apache.a2enmod vhost_alias
    """
    ret = {}
    command = ["a2enmod", mod]

    try:
        status = __salt__["cmd.retcode"](command, python_shell=False)
    except Exception as e:  # pylint: disable=broad-except
        return e

    ret["Name"] = "Apache2 Enable Mod"
    ret["Mod"] = mod

    if status == 1:
        ret["Status"] = f"Mod {mod} Not found"
    elif status == 0:
        ret["Status"] = f"Mod {mod} enabled"
    else:
        ret["Status"] = status

    return ret


def a2dismod(mod):
    """
    Runs a2dismod for the given mod.

    This will only be functional on Debian-based operating systems (Ubuntu,
    Mint, etc).

    CLI Examples:

    .. code-block:: bash

        salt '*' apache.a2dismod vhost_alias
    """
    ret = {}
    command = ["a2dismod", mod]

    try:
        status = __salt__["cmd.retcode"](command, python_shell=False)
    except Exception as e:  # pylint: disable=broad-except
        return e

    ret["Name"] = "Apache2 Disable Mod"
    ret["Mod"] = mod

    if status == 256:
        ret["Status"] = f"Mod {mod} Not found"
    elif status == 0:
        ret["Status"] = f"Mod {mod} disabled"
    else:
        ret["Status"] = status

    return ret


def check_conf_enabled(conf):
    """
    .. versionadded:: 2016.3.0

    Checks to see if the specific conf symlink is in /etc/apache2/conf-enabled.

    This will only be functional on Debian-based operating systems (Ubuntu,
    Mint, etc).

    CLI Examples:

    .. code-block:: bash

        salt '*' apache.check_conf_enabled security
        salt '*' apache.check_conf_enabled security.conf
    """
    if conf.endswith(".conf"):
        conf_file = conf
    else:
        conf_file = f"{conf}.conf"
    return os.path.islink(f"/etc/apache2/conf-enabled/{conf_file}")


@salt.utils.decorators.path.which("a2enconf")
def a2enconf(conf):
    """
    .. versionadded:: 2016.3.0

    Runs a2enconf for the given conf.

    This will only be functional on Debian-based operating systems (Ubuntu,
    Mint, etc).

    CLI Examples:

    .. code-block:: bash

        salt '*' apache.a2enconf security
    """
    ret = {}
    command = ["a2enconf", conf]

    try:
        status = __salt__["cmd.retcode"](command, python_shell=False)
    except Exception as e:  # pylint: disable=broad-except
        return e

    ret["Name"] = "Apache2 Enable Conf"
    ret["Conf"] = conf

    if status == 1:
        ret["Status"] = f"Conf {conf} Not found"
    elif status == 0:
        ret["Status"] = f"Conf {conf} enabled"
    else:
        ret["Status"] = status

    return ret


@salt.utils.decorators.path.which("a2disconf")
def a2disconf(conf):
    """
    .. versionadded:: 2016.3.0

    Runs a2disconf for the given conf.

    This will only be functional on Debian-based operating systems (Ubuntu,
    Mint, etc).

    CLI Examples:

    .. code-block:: bash

        salt '*' apache.a2disconf security
    """
    ret = {}
    command = ["a2disconf", conf]

    try:
        status = __salt__["cmd.retcode"](command, python_shell=False)
    except Exception as e:  # pylint: disable=broad-except
        return e

    ret["Name"] = "Apache2 Disable Conf"
    ret["Conf"] = conf

    if status == 256:
        ret["Status"] = f"Conf {conf} Not found"
    elif status == 0:
        ret["Status"] = f"Conf {conf} disabled"
    else:
        ret["Status"] = status

    return ret
