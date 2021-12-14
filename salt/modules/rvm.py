"""
Manage ruby installations and gemsets with RVM, the Ruby Version Manager.
"""

import logging
import os
import re

import salt.utils.args
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

# Don't shadow built-in's.
__func_alias__ = {"list_": "list"}

__opts__ = {
    "rvm.runas": None,
}


def _get_rvm_location(runas=None):
    if runas:
        runas_home = os.path.expanduser("~{}".format(runas))
        rvmpath = "{}/.rvm/bin/rvm".format(runas_home)
        if os.path.exists(rvmpath):
            return [rvmpath]
    return ["/usr/local/rvm/bin/rvm"]


def _rvm(command, runas=None, cwd=None, env=None):
    if runas is None:
        runas = __salt__["config.option"]("rvm.runas")
    if not is_installed(runas):
        return False

    cmd = _get_rvm_location(runas) + command

    ret = __salt__["cmd.run_all"](
        cmd, runas=runas, cwd=cwd, python_shell=False, env=env
    )

    if ret["retcode"] == 0:
        return ret["stdout"]
    return False


def _rvm_do(ruby, command, runas=None, cwd=None, env=None):
    return _rvm([ruby or "default", "do"] + command, runas=runas, cwd=cwd, env=env)


def is_installed(runas=None):
    """
    Check if RVM is installed.

    CLI Example:

    .. code-block:: bash

        salt '*' rvm.is_installed
    """
    try:
        return __salt__["cmd.has_exec"](_get_rvm_location(runas)[0])
    except IndexError:
        return False


def install(runas=None):
    """
    Install RVM system-wide

    runas
        The user under which to run the rvm installer script. If not specified,
        then it be run as the user under which Salt is running.

    CLI Example:

    .. code-block:: bash

        salt '*' rvm.install
    """
    # RVM dependencies on Ubuntu 10.04:
    #   bash coreutils gzip bzip2 gawk sed curl git-core subversion
    installer = (
        "https://raw.githubusercontent.com/rvm/rvm/master/binscripts/rvm-installer"
    )
    ret = __salt__["cmd.run_all"](
        # the RVM installer automatically does a multi-user install when it is
        # invoked with root privileges
        "curl -Ls {installer} | bash -s stable".format(installer=installer),
        runas=runas,
        python_shell=True,
    )
    if ret["retcode"] > 0:
        msg = "Error encountered while downloading the RVM installer"
        if ret["stderr"]:
            msg += ". stderr follows:\n\n" + ret["stderr"]
        raise CommandExecutionError(msg)
    return True


def install_ruby(ruby, runas=None, opts=None, env=None):
    """
    Install a ruby implementation.

    ruby
        The version of ruby to install

    runas
        The user under which to run rvm. If not specified, then rvm will be run
        as the user under which Salt is running.

    env
        Environment to set for the install command. Useful for exporting compilation
        flags such as RUBY_CONFIGURE_OPTS

    opts
        List of options to pass to the RVM installer (ie -C, --patch, etc)

    CLI Example:

    .. code-block:: bash

        salt '*' rvm.install_ruby 1.9.3-p385
    """
    # MRI/RBX/REE dependencies for Ubuntu 10.04:
    #   build-essential openssl libreadline6 libreadline6-dev curl
    #   git-core zlib1g zlib1g-dev libssl-dev libyaml-dev libsqlite3-0
    #   libsqlite3-dev sqlite3 libxml2-dev libxslt1-dev autoconf libc6-dev
    #   libncurses5-dev automake libtool bison subversion ruby
    if opts is None:
        opts = []

    if runas and runas != "root":
        _rvm(["autolibs", "disable", ruby] + opts, runas=runas)
        opts.append("--disable-binary")
    return _rvm(["install", ruby] + opts, runas=runas, env=env)


def reinstall_ruby(ruby, runas=None, env=None):
    """
    Reinstall a ruby implementation

    ruby
        The version of ruby to reinstall

    runas
        The user under which to run rvm. If not specified, then rvm will be run
        as the user under which Salt is running.

    CLI Example:

    .. code-block:: bash

        salt '*' rvm.reinstall_ruby 1.9.3-p385
    """
    return _rvm(["reinstall", ruby], runas=runas, env=env)


def list_(runas=None):
    """
    List all rvm-installed rubies

    runas
        The user under which to run rvm. If not specified, then rvm will be run
        as the user under which Salt is running.

    CLI Example:

    .. code-block:: bash

        salt '*' rvm.list
    """
    rubies = []
    output = _rvm(["list"], runas=runas)
    if output:
        regex = re.compile(r"^[= ]([*> ]) ([^- ]+)-([^ ]+) \[ (.*) \]")
        for line in output.splitlines():
            match = regex.match(line)
            if match:
                rubies.append([match.group(2), match.group(3), match.group(1) == "*"])
    return rubies


def set_default(ruby, runas=None):
    """
    Set the default ruby

    ruby
        The version of ruby to make the default

    runas
        The user under which to run rvm. If not specified, then rvm will be run
        as the user under which Salt is running.

    CLI Example:

    .. code-block:: bash

        salt '*' rvm.set_default 2.0.0
    """
    return _rvm(["alias", "create", "default", ruby], runas=runas)


def get(version="stable", runas=None):
    """
    Update RVM

    version : stable
        Which version of RVM to install, (e.g. stable or head)

    CLI Example:

    .. code-block:: bash

        salt '*' rvm.get
    """
    return _rvm(["get", version], runas=runas)


def wrapper(ruby_string, wrapper_prefix, runas=None, *binaries):
    """
    Install RVM wrapper scripts

    ruby_string
        Ruby/gemset to install wrappers for

    wrapper_prefix
        What to prepend to the name of the generated wrapper binaries

    runas
        The user under which to run rvm. If not specified, then rvm will be run
        as the user under which Salt is running.

    binaries : None
        The names of the binaries to create wrappers for. When nothing is
        given, wrappers for ruby, gem, rake, irb, rdoc, ri and testrb are
        generated.

    CLI Example:

    .. code-block:: bash

        salt '*' rvm.wrapper <ruby_string> <wrapper_prefix>
    """
    cmd = ["wrapper", ruby_string, wrapper_prefix]
    cmd.extend(binaries)
    return _rvm(cmd, runas=runas)


def rubygems(ruby, version, runas=None):
    """
    Installs a specific rubygems version in the given ruby

    ruby
        The ruby for which to install rubygems

    version
        The version of rubygems to install, or 'remove' to use the version that
        ships with 1.9

    runas
        The user under which to run rvm. If not specified, then rvm will be run
        as the user under which Salt is running.

    CLI Example:

    .. code-block:: bash

        salt '*' rvm.rubygems 2.0.0 1.8.24
    """
    return _rvm_do(ruby, ["rubygems", version], runas=runas)


def gemset_create(ruby, gemset, runas=None):
    """
    Creates a gemset.

    ruby
        The ruby version for which to create the gemset

    gemset
        The name of the gemset to create

    runas
        The user under which to run rvm. If not specified, then rvm will be run
        as the user under which Salt is running.

    CLI Example:

    .. code-block:: bash

        salt '*' rvm.gemset_create 2.0.0 foobar
    """
    return _rvm_do(ruby, ["rvm", "gemset", "create", gemset], runas=runas)


def gemset_list(ruby="default", runas=None):
    """
    List all gemsets for the given ruby.

    ruby : default
        The ruby version for which to list the gemsets

    runas
        The user under which to run rvm. If not specified, then rvm will be run
        as the user under which Salt is running.

    CLI Example:

    .. code-block:: bash

        salt '*' rvm.gemset_list
    """
    gemsets = []
    output = _rvm_do(ruby, ["rvm", "gemset", "list"], runas=runas)
    if output:
        regex = re.compile("^   ([^ ]+)")
        for line in output.splitlines():
            match = regex.match(line)
            if match:
                gemsets.append(match.group(1))
    return gemsets


def gemset_delete(ruby, gemset, runas=None):
    """
    Delete a gemset

    ruby
        The ruby version to which the gemset belongs

    gemset
        The gemset to delete

    runas
        The user under which to run rvm. If not specified, then rvm will be run
        as the user under which Salt is running.

    CLI Example:

    .. code-block:: bash

        salt '*' rvm.gemset_delete 2.0.0 foobar
    """
    return _rvm_do(ruby, ["rvm", "--force", "gemset", "delete", gemset], runas=runas)


def gemset_empty(ruby, gemset, runas=None):
    """
    Remove all gems from a gemset.

    ruby
        The ruby version to which the gemset belongs

    gemset
        The gemset to empty

    runas
        The user under which to run rvm. If not specified, then rvm will be run
        as the user under which Salt is running.

    CLI Example:

    .. code-block:: bash

        salt '*' rvm.gemset_empty 2.0.0 foobar
    """
    return _rvm_do(ruby, ["rvm", "--force", "gemset", "empty", gemset], runas=runas)


def gemset_copy(source, destination, runas=None):
    """
    Copy all gems from one gemset to another.

    source
        The name of the gemset to copy, complete with ruby version

    destination
        The destination gemset

    runas
        The user under which to run rvm. If not specified, then rvm will be run
        as the user under which Salt is running.

    CLI Example:

    .. code-block:: bash

        salt '*' rvm.gemset_copy foobar bazquo
    """
    return _rvm(["gemset", "copy", source, destination], runas=runas)


def gemset_list_all(runas=None):
    """
    List all gemsets for all installed rubies.

    Note that you must have set a default ruby before this can work.

    runas
        The user under which to run rvm. If not specified, then rvm will be run
        as the user under which Salt is running.

    CLI Example:

    .. code-block:: bash

        salt '*' rvm.gemset_list_all
    """
    gemsets = {}
    current_ruby = None
    output = _rvm_do("default", ["rvm", "gemset", "list_all"], runas=runas)
    if output:
        gems_regex = re.compile("^   ([^ ]+)")
        gemset_regex = re.compile("^gemsets for ([^ ]+)")
        for line in output.splitlines():
            match = gemset_regex.match(line)
            if match:
                current_ruby = match.group(1)
                gemsets[current_ruby] = []
            match = gems_regex.match(line)
            if match:
                gemsets[current_ruby].append(match.group(1))
    return gemsets


def do(ruby, command, runas=None, cwd=None, env=None):  # pylint: disable=C0103
    """
    Execute a command in an RVM controlled environment.

    ruby
        Which ruby to use

    command
        The rvm command to execute

    runas
        The user under which to run rvm. If not specified, then rvm will be run
        as the user under which Salt is running.

    cwd
        The directory from which to run the rvm command. Defaults to the user's
        home directory.

    CLI Example:

    .. code-block:: bash

        salt '*' rvm.do 2.0.0 <command>
    """
    try:
        command = salt.utils.args.shlex_split(command)
    except AttributeError:
        command = salt.utils.args.shlex_split(str(command))
    return _rvm_do(ruby, command, runas=runas, cwd=cwd, env=env)
