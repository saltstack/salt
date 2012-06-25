"""
Manage ruby installations and gemsets with RVM, the Ruby Version Manager.
"""

__opts__ = {
    "rvm.runas": None,
}

import re


def _rvm(command, arguments="", runas=None):
    if not is_installed():
        return False

    ret = __salt__["cmd.run_all"](
        "/usr/local/rvm/bin/rvm {command} {arguments}".
        format(command=command, arguments=arguments),
        runas=runas or __opts__["rvm.runas"])
    if ret["retcode"] == 0:
        return ret["stdout"]
    else:
        return False


def _rvm_do(ruby, command, runas=None):
    return _rvm("{ruby} do {command}".
                format(ruby=ruby or "default", command=command),
                runas=runas)


def is_installed():
    """
    Check if RVM is installed.
    """
    return __salt__["cmd.has_exec"]("/usr/local/rvm/bin/rvm")


def install():
    """
    Install RVM system wide.
    """
    # RVM dependencies on Ubuntu 10.04:
    #   bash coreutils gzip bzip2 gawk sed curl git-core subversion sudo
    installer = "https://raw.github.com/wayneeseguin/rvm/master/binscripts/rvm-installer"
    return 0 == __salt__["cmd.retcode"](
        # the RVM installer only does a multi-user install when it is invoked under sudo
        "curl -s {installer} | sudo bash -s stable".format(installer=installer))


def install_ruby(ruby, runas=None):
    """
    Install a ruby implementation.

    ruby
        The version of ruby to install.
    runas : None
        The user to run rvm as.
    """
    # MRI/RBX/REE dependencies for Ubuntu 10.04:
    #   build-essential openssl libreadline6 libreadline6-dev curl
    #   git-core zlib1g zlib1g-dev libssl-dev libyaml-dev libsqlite3-0
    #   libsqlite3-dev sqlite3 libxml2-dev libxslt1-dev autoconf libc6-dev
    #   libncurses5-dev automake libtool bison subversion ruby
    return _rvm("install", ruby, runas=runas)


def reinstall_ruby(ruby, runas=None):
    """
    Reinstall a ruby implementation.

    ruby
        The version of ruby to reinstall.
    runas : None
        The user to run rvm as.
    """
    return _rvm("reinstall", ruby, runas=runas)


def list(runas=None):
    """
    List all rvm installed rubies.

    runas : None
        The user to run rvm as.
    """
    rubies = []

    for line in _rvm("list", "", runas=runas).splitlines():
        m = re.match("^[= ]([*> ]) ([^- ]+)-([^ ]+) \[ (.*) \]", line)
        if m:
            rubies.append([m.group(2), m.group(3), m.group(1) == "*"])
    return rubies


def set_default(ruby, runas=None):
    """
    Set the default ruby.

    ruby
        The version of ruby to make the default.
    runas : None
        The user to run rvm as.
    """
    return _rvm("alias", "create default {ruby}".format(ruby=ruby), runas=runas)


def get(version="stable", runas=None):
    """
    Update RVM.

    version : stable
        Which version of RVM to install, e.g. stable or head.
    ruby
        The version of ruby to reinstall.
    """
    return _rvm("get", version, runas=runas)


def wrapper(ruby_string, wrapper_prefix, runas=None, *binaries):
    """
    Install RVM wrapper scripts.

    ruby_string
        Ruby/gemset to install wrappers for.
    wrapper_prefix
        What to prepend to the name of the generated wrapper binaries.
    runas : None
        The user to run rvm as.
    binaries : None
        The names of the binaries to create wrappers for. When nothing is given, wrappers for ruby, gem, rake, irb, rdoc, ri and testrb are generated.
    """
    return _rvm("wrapper", "{ruby_string} {wrapper_prefix} {binaries}".
                format(ruby_string=ruby_string,
                       wrapper_prefix=wrapper_prefix,
                       binaries=" ".join(binaries)), runas=runas)


def rubygems(ruby, version, runas=None):
    """
    Installs a specific rubygems version in the given ruby.

    ruby
        The ruby to install rubygems for.
    version
        The version of rubygems to install or 'remove' to use the version that ships with 1.9
    runas : None
        The user to run rvm as.
    """
    return _rvm_do(ruby, "rubygems", version, runas=runas)


def gemset_create(ruby, gemset, runas=None):
    """
    Creates a gemset.

    ruby
        The ruby version to create the gemset for.
    gemset
        The name of the gemset to create.
    runas : None
        The user to run rvm as.
    """
    return _rvm_do(ruby, "rvm gemset create {gemset}".format(gemset=gemset), runas=runas)


def gemset_list(ruby="default", runas=None):
    """
    List all gemsets for the given ruby.

    ruby : default
        The ruby version to list the gemsets for
    runas : None
        The user to run rvm as.
    """
    gemsets = []
    for line in _rvm_do(ruby, "rvm gemset list", runas=runas).splitlines():
        m = re.match("^   ([^ ]+)", line)
        if m:
            gemsets.append(m.group(1))
    return gemsets


def gemset_delete(ruby, gemset, runas=None):
    """
    Deletes a gemset.

    ruby
        The ruby version the gemset belongs to.
    gemset
        The gemset to delete.
    runas : None
        The user to run rvm as.
    """
    return _rvm_do(ruby, "rvm --force gemset delete {gemset}".format(gemset=gemset), runas=runas)


def gemset_empty(ruby, gemset, runas=None):
    """
    Remove all gems from a gemset.

    ruby
        The ruby version the gemset belongs to.
    gemset
        The gemset to empty.
    runas : None
        The user to run rvm as.
    """
    return _rvm_do(ruby, "rvm --force gemset empty", gemset, runas=runas)


def gemset_copy(source, destination, runas=None):
    """
    Copy all gems from one gemset to another.

    source
        The name of the gemset to copy, complete with ruby version.
    destination
        The destination gemset.
    runas : None
        The user to run rvm as.
    """
    return _rvm("gemset copy", source, destination, runas=runas)


def gemset_list_all(runas=None):
    """
    List all gemsets for all installed rubies.

    Note that you must have set a default ruby before this can work.

    runas : None
        The user to run rvm as.
    """
    gemsets = {}
    current_ruby = None
    for line in _rvm_do("default", "rvm gemset list_all", runas=runas).splitlines():
        m = re.match("^gemsets for ([^ ]+)", line)
        if m:
            current_ruby = m.group(1)
            gemsets[current_ruby] = []
        m = re.match("^   ([^ ]+)", line)
        if m:
            gemsets[current_ruby].append(m.group(1))
    return gemsets


def do(ruby, command, runas=None):
    """
    Execute a command in an RVM controlled environment.

    ruby:
        The ruby to use.
    command:
        The command to execute.
    runas : None
        The user to run rvm as.
    """
    return _rvm_do(ruby, command, runas=runas)
