# -*- coding: utf-8 -*-
"""
Module for managing locales on POSIX-like systems.
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging
import os
import re

# Import Salt libs
import salt.utils.locales
import salt.utils.path
import salt.utils.platform
import salt.utils.systemd
from salt.exceptions import CommandExecutionError
from salt.ext import six

try:
    import dbus
except ImportError:
    dbus = None


log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "locale"


def __virtual__():
    """
    Exclude Windows OS.
    """
    if salt.utils.platform.is_windows():
        return False, "Cannot load locale module: windows platforms are unsupported"

    return __virtualname__


def _parse_dbus_locale():
    """
    Get the 'System Locale' parameters from dbus
    """
    bus = dbus.SystemBus()
    localed = bus.get_object("org.freedesktop.locale1", "/org/freedesktop/locale1")
    properties = dbus.Interface(localed, "org.freedesktop.DBus.Properties")
    system_locale = properties.Get("org.freedesktop.locale1", "Locale")

    ret = {}
    for env_var in system_locale:
        env_var = six.text_type(env_var)
        match = re.match(r"^([A-Z_]+)=(.*)$", env_var)
        if match:
            ret[match.group(1)] = match.group(2).replace('"', "")
        else:
            log.error(
                'Odd locale parameter "%s" detected in dbus locale '
                "output. This should not happen. You should "
                "probably investigate what caused this.",
                env_var,
            )

    return ret


def _localectl_status():
    """
    Parse localectl status into a dict.
    :return: dict
    """
    if salt.utils.path.which("localectl") is None:
        raise CommandExecutionError('Unable to find "localectl"')

    ret = {}
    locale_ctl_out = (__salt__["cmd.run"]("localectl status") or "").strip()
    ctl_key = None
    for line in locale_ctl_out.splitlines():
        if ": " in line:  # Keys are separate with ":" and a space (!).
            ctl_key, ctl_data = line.split(": ")
            ctl_key = ctl_key.strip().lower().replace(" ", "_")
        else:
            ctl_data = line.strip()
        if not ctl_data:
            continue
        if ctl_key:
            if "=" in ctl_data:
                loc_set = ctl_data.split("=")
                if len(loc_set) == 2:
                    if ctl_key not in ret:
                        ret[ctl_key] = {}
                    ret[ctl_key][loc_set[0]] = loc_set[1]
            else:
                ret[ctl_key] = {"data": None if ctl_data == "n/a" else ctl_data}
    if not ret:
        log.debug(
            "Unable to find any locale information inside the following data:\n%s",
            locale_ctl_out,
        )
        raise CommandExecutionError('Unable to parse result of "localectl"')

    return ret


def _localectl_set(locale=""):
    """
    Use systemd's localectl command to set the LANG locale parameter, making
    sure not to trample on other params that have been set.
    """
    locale_params = (
        _parse_dbus_locale()
        if dbus is not None
        else _localectl_status().get("system_locale", {})
    )
    locale_params["LANG"] = six.text_type(locale)
    args = " ".join(
        [
            '{0}="{1}"'.format(k, v)
            for k, v in six.iteritems(locale_params)
            if v is not None
        ]
    )
    return not __salt__["cmd.retcode"](
        "localectl set-locale {0}".format(args), python_shell=False
    )


def list_avail():
    """
    Lists available (compiled) locales

    CLI Example:

    .. code-block:: bash

        salt '*' locale.list_avail
    """
    return __salt__["cmd.run"]("locale -a").split("\n")


def get_locale():
    """
    Get the current system locale

    CLI Example:

    .. code-block:: bash

        salt '*' locale.get_locale
    """
    ret = ""
    lc_ctl = salt.utils.systemd.booted(__context__)
    # localectl on SLE12 is installed but the integration is still broken in latest SP3 due to
    # config is rewritten by by many %post installation hooks in the older packages.
    # If you use it -- you will break your config. This is not the case in SLE15 anymore.
    if lc_ctl and not (
        __grains__["os_family"] in ["Suse"] and __grains__["osmajorrelease"] in [12]
    ):
        ret = (
            _parse_dbus_locale()
            if dbus is not None
            else _localectl_status()["system_locale"]
        ).get("LANG", "")
    else:
        if "Suse" in __grains__["os_family"]:
            cmd = 'grep "^RC_LANG" /etc/sysconfig/language'
        elif "RedHat" in __grains__["os_family"]:
            cmd = 'grep "^LANG=" /etc/sysconfig/i18n'
        elif "Debian" in __grains__["os_family"]:
            # this block only applies to Debian without systemd
            cmd = 'grep "^LANG=" /etc/default/locale'
        elif "Gentoo" in __grains__["os_family"]:
            cmd = "eselect --brief locale show"
            return __salt__["cmd.run"](cmd).strip()
        elif "Solaris" in __grains__["os_family"]:
            cmd = 'grep "^LANG=" /etc/default/init'
        else:  # don't waste time on a failing cmd.run
            raise CommandExecutionError(
                'Error: "{0}" is unsupported!'.format(__grains__["oscodename"])
            )

        if cmd:
            try:
                ret = __salt__["cmd.run"](cmd).split("=")[1].replace('"', "")
            except IndexError as err:
                log.error('Error occurred while running "%s": %s', cmd, err)

    return ret


def set_locale(locale):
    """
    Sets the current system locale

    CLI Example:

    .. code-block:: bash

        salt '*' locale.set_locale 'en_US.UTF-8'
    """
    lc_ctl = salt.utils.systemd.booted(__context__)
    # localectl on SLE12 is installed but the integration is broken -- config is rewritten by YaST2
    if lc_ctl and not (
        __grains__["os_family"] in ["Suse"] and __grains__["osmajorrelease"] in [12]
    ):
        return _localectl_set(locale)

    if "Suse" in __grains__["os_family"]:
        # this block applies to all SUSE systems - also with systemd
        if not __salt__["file.file_exists"]("/etc/sysconfig/language"):
            __salt__["file.touch"]("/etc/sysconfig/language")
        __salt__["file.replace"](
            "/etc/sysconfig/language",
            "^RC_LANG=.*",
            'RC_LANG="{0}"'.format(locale),
            append_if_not_found=True,
        )
    elif "RedHat" in __grains__["os_family"]:
        if not __salt__["file.file_exists"]("/etc/sysconfig/i18n"):
            __salt__["file.touch"]("/etc/sysconfig/i18n")
        __salt__["file.replace"](
            "/etc/sysconfig/i18n",
            "^LANG=.*",
            'LANG="{0}"'.format(locale),
            append_if_not_found=True,
        )
    elif "Debian" in __grains__["os_family"]:
        # this block only applies to Debian without systemd
        update_locale = salt.utils.path.which("update-locale")
        if update_locale is None:
            raise CommandExecutionError(
                'Cannot set locale: "update-locale" was not found.'
            )
        __salt__["cmd.run"](update_locale)  # (re)generate /etc/default/locale
        __salt__["file.replace"](
            "/etc/default/locale",
            "^LANG=.*",
            'LANG="{0}"'.format(locale),
            append_if_not_found=True,
        )
    elif "Gentoo" in __grains__["os_family"]:
        cmd = "eselect --brief locale set {0}".format(locale)
        return __salt__["cmd.retcode"](cmd, python_shell=False) == 0
    elif "Solaris" in __grains__["os_family"]:
        if locale not in __salt__["locale.list_avail"]():
            return False
        __salt__["file.replace"](
            "/etc/default/init",
            "^LANG=.*",
            'LANG="{0}"'.format(locale),
            append_if_not_found=True,
        )
    else:
        raise CommandExecutionError("Error: Unsupported platform!")

    return True


def avail(locale):
    """
    Check if a locale is available.

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' locale.avail 'en_US.UTF-8'
    """
    try:
        normalized_locale = salt.utils.locales.normalize_locale(locale)
    except IndexError:
        log.error('Unable to validate locale "%s"', locale)
        return False
    avail_locales = __salt__["locale.list_avail"]()
    locale_exists = next(
        (
            True
            for x in avail_locales
            if salt.utils.locales.normalize_locale(x.strip()) == normalized_locale
        ),
        False,
    )
    return locale_exists


def gen_locale(locale, **kwargs):
    """
    Generate a locale. Options:

    .. versionadded:: 2014.7.0

    :param locale: Any locale listed in /usr/share/i18n/locales or
        /usr/share/i18n/SUPPORTED for Debian and Gentoo based distributions,
        which require the charmap to be specified as part of the locale
        when generating it.

    verbose
        Show extra warnings about errors that are normally ignored.

    CLI Example:

    .. code-block:: bash

        salt '*' locale.gen_locale en_US.UTF-8
        salt '*' locale.gen_locale 'en_IE.UTF-8 UTF-8'    # Debian/Gentoo only
    """
    on_debian = __grains__.get("os") == "Debian"
    on_ubuntu = __grains__.get("os") == "Ubuntu"
    on_gentoo = __grains__.get("os_family") == "Gentoo"
    on_suse = __grains__.get("os_family") == "Suse"
    on_solaris = __grains__.get("os_family") == "Solaris"

    if on_solaris:  # all locales are pre-generated
        return locale in __salt__["locale.list_avail"]()

    locale_info = salt.utils.locales.split_locale(locale)
    locale_search_str = "{0}_{1}".format(
        locale_info["language"], locale_info["territory"]
    )

    # if the charmap has not been supplied, normalize by appening it
    if not locale_info["charmap"] and not on_ubuntu:
        locale_info["charmap"] = locale_info["codeset"]
        locale = salt.utils.locales.join_locale(locale_info)

    if on_debian or on_gentoo:  # file-based search
        search = "/usr/share/i18n/SUPPORTED"
        valid = __salt__["file.search"](
            search, "^{0}$".format(locale), flags=re.MULTILINE
        )
    else:  # directory-based search
        if on_suse:
            search = "/usr/share/locale"
        else:
            search = "/usr/share/i18n/locales"

        try:
            valid = locale_search_str in os.listdir(search)
        except OSError as ex:
            log.error(ex)
            raise CommandExecutionError('Locale "{0}" is not available.'.format(locale))

    if not valid:
        log.error('The provided locale "%s" is not found in %s', locale, search)
        return False

    if os.path.exists("/etc/locale.gen"):
        __salt__["file.replace"](
            "/etc/locale.gen",
            r"^\s*#\s*{0}\s*$".format(locale),
            "{0}\n".format(locale),
            append_if_not_found=True,
        )
    elif on_ubuntu:
        __salt__["file.touch"](
            "/var/lib/locales/supported.d/{0}".format(locale_info["language"])
        )
        __salt__["file.replace"](
            "/var/lib/locales/supported.d/{0}".format(locale_info["language"]),
            locale,
            locale,
            append_if_not_found=True,
        )

    if salt.utils.path.which("locale-gen"):
        cmd = ["locale-gen"]
        if on_gentoo:
            cmd.append("--generate")
        if on_ubuntu:
            cmd.append(salt.utils.locales.normalize_locale(locale))
        else:
            cmd.append(locale)
    elif salt.utils.path.which("localedef"):
        cmd = [
            "localedef",
            "--force",
            "-i",
            locale_search_str,
            "-f",
            locale_info["codeset"],
            "{0}.{1}".format(locale_search_str, locale_info["codeset"]),
            kwargs.get("verbose", False) and "--verbose" or "--quiet",
        ]
    else:
        raise CommandExecutionError(
            'Command "locale-gen" or "localedef" was not found on this system.'
        )

    res = __salt__["cmd.run_all"](cmd)
    if res["retcode"]:
        log.error(res["stderr"])

    if kwargs.get("verbose"):
        return res
    else:
        return res["retcode"] == 0
