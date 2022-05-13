"""
Manage ruby gems.
"""

import logging
import re

import salt.utils.itertools
import salt.utils.platform
from salt.exceptions import CommandExecutionError

__func_alias__ = {"list_": "list"}

log = logging.getLogger(__name__)  # pylint: disable=C0103


def _gem(command, ruby=None, runas=None, gem_bin=None):
    """
    Run the actual gem command. If rvm or rbenv is installed, run the command
    using the corresponding module. rbenv is not available on windows, so don't
    try.

    :param command: string
    Command to run
    :param ruby: string : None
    If RVM or rbenv are installed, the ruby version and gemset to use.
    Ignored if ``gem_bin`` is specified.
    :param runas: string : None
    The user to run gem as.
    :param gem_bin: string : None
    Full path to the ``gem`` binary

    :return:
    Returns the full standard out including success codes or False if it fails
    """
    cmdline = [gem_bin or "gem"] + command

    # If a custom gem is given, use that and don't check for rvm/rbenv. User
    # knows best!
    if gem_bin is None:
        if __salt__["rvm.is_installed"](runas=runas):
            return __salt__["rvm.do"](ruby, cmdline, runas=runas)

        if not salt.utils.platform.is_windows() and __salt__["rbenv.is_installed"](
            runas=runas
        ):
            if ruby is None:
                return __salt__["rbenv.do"](cmdline, runas=runas)
            else:
                return __salt__["rbenv.do_with_ruby"](ruby, cmdline, runas=runas)

    ret = __salt__["cmd.run_all"](cmdline, runas=runas, python_shell=False)

    if ret["retcode"] == 0:
        return ret["stdout"]
    else:
        raise CommandExecutionError(ret["stderr"])


def install(
    gems,  # pylint: disable=C0103
    ruby=None,
    gem_bin=None,
    runas=None,
    version=None,
    rdoc=False,
    ri=False,
    pre_releases=False,
    proxy=None,
    source=None,
):  # pylint: disable=C0103
    """
    Installs one or several gems.

    :param gems: string
        The gems to install
    :param gem_bin: string : None
        Full path to ``gem`` binary to use.
    :param ruby: string : None
        If RVM or rbenv are installed, the ruby version and gemset to use.
        Ignored if ``gem_bin`` is specified.
    :param runas: string : None
        The user to run gem as.
    :param version: string : None
        Specify the version to install for the gem.
        Doesn't play nice with multiple gems at once
    :param rdoc: boolean : False
        Generate RDoc documentation for the gem(s).
        For rubygems > 3 this is interpreted as the --no-document arg and the
        ri option will then be ignored
    :param ri: boolean : False
        Generate RI documentation for the gem(s).
        For rubygems > 3 this is interpreted as the --no-document arg and the
        rdoc option will then be ignored
    :param pre_releases: boolean : False
        Include pre-releases in the available versions
    :param proxy: string : None
        Use the specified HTTP proxy server for all outgoing traffic.
        Format: http://hostname[:port]

    source : None
        Use the specified HTTP gem source server to download gem.
        Format: http://hostname[:port]

    CLI Example:

    .. code-block:: bash

        salt '*' gem.install vagrant

        salt '*' gem.install redphone gem_bin=/opt/sensu/embedded/bin/gem
    """
    try:
        gems = gems.split()
    except AttributeError:
        pass

    options = []
    if version:
        options.extend(["--version", version])
    if _has_rubygems_3(ruby=ruby, runas=runas, gem_bin=gem_bin):
        if not rdoc or not ri:
            options.append("--no-document")
        if pre_releases:
            options.append("--prerelease")
    else:
        if not rdoc:
            options.append("--no-rdoc")
        if not ri:
            options.append("--no-ri")
        if pre_releases:
            options.append("--pre")
    if proxy:
        options.extend(["-p", proxy])
    if source:
        options.extend(["--source", source])

    return _gem(["install"] + gems + options, ruby, gem_bin=gem_bin, runas=runas)


def uninstall(gems, ruby=None, runas=None, gem_bin=None):
    """
    Uninstall one or several gems.

    :param gems: string
        The gems to uninstall.
    :param gem_bin: string : None
        Full path to ``gem`` binary to use.
    :param ruby: string : None
        If RVM or rbenv are installed, the ruby version and gemset to use.
        Ignored if ``gem_bin`` is specified.
    :param runas: string : None
        The user to run gem as.

    CLI Example:

    .. code-block:: bash

        salt '*' gem.uninstall vagrant
    """
    try:
        gems = gems.split()
    except AttributeError:
        pass

    return _gem(["uninstall"] + gems + ["-a", "-x"], ruby, gem_bin=gem_bin, runas=runas)


def update(gems, ruby=None, runas=None, gem_bin=None):
    """
    Update one or several gems.

    :param gems: string
        The gems to update.
    :param gem_bin: string : None
        Full path to ``gem`` binary to use.
    :param ruby: string : None
        If RVM or rbenv are installed, the ruby version and gemset to use.
        Ignored if ``gem_bin`` is specified.
    :param runas: string : None
        The user to run gem as.

    CLI Example:

    .. code-block:: bash

        salt '*' gem.update vagrant
    """
    try:
        gems = gems.split()
    except AttributeError:
        pass

    return _gem(["update"] + gems, ruby, gem_bin=gem_bin, runas=runas)


def update_system(version="", ruby=None, runas=None, gem_bin=None):
    """
    Update rubygems.

    :param version: string : (newest)
        The version of rubygems to install.
    :param gem_bin: string : None
        Full path to ``gem`` binary to use.
    :param ruby: string : None
        If RVM or rbenv are installed, the ruby version and gemset to use.
        Ignored if ``gem_bin`` is specified.
    :param runas: string : None
        The user to run gem as.

    CLI Example:

    .. code-block:: bash

        salt '*' gem.update_system
    """
    return _gem(["update", "--system", version], ruby, gem_bin=gem_bin, runas=runas)


def version(ruby=None, runas=None, gem_bin=None):
    """
    Print out the version of gem

    :param gem_bin: string : None
        Full path to ``gem`` binary to use.
    :param ruby: string : None
        If RVM or rbenv are installed, the ruby version and gemset to use.
        Ignored if ``gem_bin`` is specified.
    :param runas: string : None
        The user to run gem as.

    CLI Example:

    .. code-block:: bash

        salt '*' gem.version
    """
    cmd = ["--version"]
    stdout = _gem(cmd, ruby, gem_bin=gem_bin, runas=runas)
    ret = {}
    for line in salt.utils.itertools.split(stdout, "\n"):
        match = re.match(r"[.0-9]+", line)
        if match:
            ret = line
            break
    return ret


def _has_rubygems_3(ruby=None, runas=None, gem_bin=None):
    match = re.match(r"^3\..*", version(ruby=ruby, runas=runas, gem_bin=gem_bin))
    if match:
        return True
    return False


def list_(prefix="", ruby=None, runas=None, gem_bin=None):
    """
    List locally installed gems.

    :param prefix: string :
        Only list gems when the name matches this prefix.
    :param gem_bin: string : None
        Full path to ``gem`` binary to use.
    :param ruby: string : None
        If RVM or rbenv are installed, the ruby version and gemset to use.
        Ignored if ``gem_bin`` is specified.
    :param runas: string : None
        The user to run gem as.

    CLI Example:

    .. code-block:: bash

        salt '*' gem.list
    """
    cmd = ["list"]
    if prefix:
        cmd.append(prefix)
    stdout = _gem(cmd, ruby, gem_bin=gem_bin, runas=runas)
    ret = {}
    for line in salt.utils.itertools.split(stdout, "\n"):
        match = re.match(r"^([^ ]+) \((.+)\)", line)
        if match:
            gem = match.group(1)
            versions = match.group(2).split(", ")
            ret[gem] = versions
    return ret


def list_upgrades(ruby=None, runas=None, gem_bin=None):
    """
    .. versionadded:: 2015.8.0

    Check if an upgrade is available for installed gems

    gem_bin : None
        Full path to ``gem`` binary to use.
    ruby : None
        If RVM or rbenv are installed, the ruby version and gemset to use.
        Ignored if ``gem_bin`` is specified.
    runas : None
        The user to run gem as.

    CLI Example:

    .. code-block:: bash

        salt '*' gem.list_upgrades
    """
    result = _gem(["outdated"], ruby, gem_bin=gem_bin, runas=runas)
    ret = {}
    for line in salt.utils.itertools.split(result, "\n"):
        match = re.search(r"(\S+) \(\S+ < (\S+)\)", line)
        if match:
            name, version = match.groups()
        else:
            log.error("Can't parse line '%s'", line)
            continue
        ret[name] = version
    return ret


def sources_add(source_uri, ruby=None, runas=None, gem_bin=None):
    """
    Add a gem source.

    :param source_uri: string
        The source URI to add.
    :param gem_bin: string : None
        Full path to ``gem`` binary to use.
    :param ruby: string : None
        If RVM or rbenv are installed, the ruby version and gemset to use.
        Ignored if ``gem_bin`` is specified.
    :param runas: string : None
        The user to run gem as.

    CLI Example:

    .. code-block:: bash

        salt '*' gem.sources_add http://rubygems.org/
    """
    return _gem(["sources", "--add", source_uri], ruby, gem_bin=gem_bin, runas=runas)


def sources_remove(source_uri, ruby=None, runas=None, gem_bin=None):
    """
    Remove a gem source.

    :param source_uri: string
        The source URI to remove.
    :param gem_bin: string : None
        Full path to ``gem`` binary to use.
    :param ruby: string : None
        If RVM or rbenv are installed, the ruby version and gemset to use.
        Ignored if ``gem_bin`` is specified.
    :param runas: string : None
        The user to run gem as.

    CLI Example:

    .. code-block:: bash

        salt '*' gem.sources_remove http://rubygems.org/
    """
    return _gem(["sources", "--remove", source_uri], ruby, gem_bin=gem_bin, runas=runas)


def sources_list(ruby=None, runas=None, gem_bin=None):
    """
    List the configured gem sources.

    :param gem_bin: string : None
        Full path to ``gem`` binary to use.
    :param ruby: string : None
        If RVM or rbenv are installed, the ruby version and gemset to use.
        Ignored if ``gem_bin`` is specified.
    :param runas: string : None
        The user to run gem as.

    CLI Example:

    .. code-block:: bash

        salt '*' gem.sources_list
    """
    ret = _gem(["sources"], ruby, gem_bin=gem_bin, runas=runas)
    return [] if ret is False else ret.splitlines()[2:]
