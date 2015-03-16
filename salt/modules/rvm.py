# -*- coding: utf-8 -*-
'''
Manage ruby installations and gemsets with RVM, the Ruby Version Manager.
'''

# Import python libs
import re
import os
import logging
try:
    from shlex import quote as _cmd_quote  # pylint: disable=E0611
except ImportError:
    from pipes import quote as _cmd_quote

log = logging.getLogger(__name__)

# Don't shadow built-in's.
__func_alias__ = {
    'list_': 'list'
}

__opts__ = {
    'rvm.runas': None,
}


def _get_rvm_location(runas=None):
    if runas:
        runas_home = os.path.expanduser('~{0}'.format(runas))
        rvmpath = '{0}/.rvm/bin/rvm'.format(runas_home)
        if os.path.exists(rvmpath):
            return rvmpath
    return '/usr/local/rvm/bin/rvm'


def _rvm(command, arguments=None, runas=None, cwd=None):
    if runas is None:
        runas = __salt__['config.option']('rvm.runas')
    if not is_installed(runas):
        return False

    cmd = [_get_rvm_location(runas), _cmd_quote(command)]
    if arguments:
        cmd.extend([_cmd_quote(arg) for arg in arguments.split()])

    ret = __salt__['cmd.run_all'](' '.join(cmd), runas=runas, cwd=cwd)

    if ret['retcode'] == 0:
        return ret['stdout']
    return False


def _rvm_do(ruby, command, runas=None, cwd=None):
    return _rvm('{ruby}'.format(ruby=ruby or 'default'),
                arguments='do {command}'.format(command=command),
                runas=runas, cwd=cwd)


def is_installed(runas=None):
    '''
    Check if RVM is installed.

    CLI Example:

    .. code-block:: bash

        salt '*' rvm.is_installed
    '''
    return __salt__['cmd.has_exec'](_get_rvm_location(runas))


def install(runas=None):
    '''
    Install RVM system wide.

    CLI Example:

    .. code-block:: bash

        salt '*' rvm.install
    '''
    # RVM dependencies on Ubuntu 10.04:
    #   bash coreutils gzip bzip2 gawk sed curl git-core subversion
    installer = 'https://raw.githubusercontent.com/wayneeseguin/rvm/master/binscripts/rvm-installer'
    ret = __salt__['cmd.run_all'](
        # the RVM installer automatically does a multi-user install when it is
        # invoked with root privileges
        'curl -Ls {installer} | bash -s stable'.format(installer=installer),
        runas=runas,
        python_shell=True
    )
    if ret['retcode'] > 0:
        log.debug(
            'Error while downloading the RVM installer. Command '
            'returned: {0!r}'.format(ret)
        )
        return False
    return True


def install_ruby(ruby, runas=None):
    '''
    Install a ruby implementation.

    ruby
        The version of ruby to install.
    runas : None
        The user to run rvm as.

    CLI Example:

    .. code-block:: bash

        salt '*' rvm.install_ruby 1.9.3-p385
    '''
    # MRI/RBX/REE dependencies for Ubuntu 10.04:
    #   build-essential openssl libreadline6 libreadline6-dev curl
    #   git-core zlib1g zlib1g-dev libssl-dev libyaml-dev libsqlite3-0
    #   libsqlite3-dev sqlite3 libxml2-dev libxslt1-dev autoconf libc6-dev
    #   libncurses5-dev automake libtool bison subversion ruby
    if runas and runas != 'root':
        _rvm('autolibs', 'disable {ruby}'.format(ruby=ruby), runas=runas)
        return _rvm('install', '--disable-binary {ruby}'.format(ruby=ruby), runas=runas)
    else:
        return _rvm('install', ruby, runas=runas)


def reinstall_ruby(ruby, runas=None):
    '''
    Reinstall a ruby implementation.

    ruby
        The version of ruby to reinstall.
    runas : None
        The user to run rvm as.

    CLI Example:

    .. code-block:: bash

        salt '*' rvm.reinstall_ruby 1.9.3-p385
    '''
    return _rvm('reinstall', ruby, runas=runas)


def list_(runas=None):
    '''
    List all rvm installed rubies.

    runas : None
        The user to run rvm as.

    CLI Example:

    .. code-block:: bash

        salt '*' rvm.list
    '''
    rubies = []
    output = _rvm('list', '', runas=runas)
    if output:
        regex = re.compile(r'^[= ]([*> ]) ([^- ]+)-([^ ]+) \[ (.*) \]')
        for line in output.splitlines():
            match = regex.match(line)
            if match:
                rubies.append([
                    match.group(2), match.group(3), match.group(1) == '*'
                ])
    return rubies


def set_default(ruby, runas=None):
    '''
    Set the default ruby.

    ruby
        The version of ruby to make the default.
    runas : None
        The user to run rvm as.

    CLI Example:

    .. code-block:: bash

        salt '*' rvm.set_default 2.0.0
    '''
    return _rvm('alias',
                'create default {ruby}'.format(ruby=ruby), runas=runas)


def get(version='stable', runas=None):
    '''
    Update RVM.

    version : stable
        Which version of RVM to install, e.g. stable or head.
    ruby
        The version of ruby to reinstall.

    CLI Example:

    .. code-block:: bash

        salt '*' rvm.get
    '''
    return _rvm('get', version, runas=runas)


def wrapper(ruby_string, wrapper_prefix, runas=None, *binaries):
    '''
    Install RVM wrapper scripts.

    ruby_string
        Ruby/gemset to install wrappers for.
    wrapper_prefix
        What to prepend to the name of the generated wrapper binaries.
    runas : None
        The user to run rvm as.
    binaries : None
        The names of the binaries to create wrappers for. When nothing is
        given, wrappers for ruby, gem, rake, irb, rdoc, ri and testrb are
        generated.

    CLI Example:

    .. code-block:: bash

        salt '*' rvm.wrapper <ruby_string> <wrapper_prefix>
    '''
    return _rvm('wrapper',
                '{ruby_string} {wrapper_prefix} {binaries}'.format(
                    ruby_string=ruby_string,
                    wrapper_prefix=wrapper_prefix,
                    binaries=' '.join(binaries)
                ),
                runas=runas)


def rubygems(ruby, version, runas=None):
    '''
    Installs a specific rubygems version in the given ruby.

    ruby
        The ruby to install rubygems for.
    version
        The version of rubygems to install or 'remove' to use the version that
        ships with 1.9
    runas : None
        The user to run rvm as.

    CLI Example:

    .. code-block:: bash

        salt '*' rvm.rubygems 2.0.0 1.8.24
    '''
    return _rvm_do(ruby, 'rubygems {0}'.format(version), runas=runas)


def gemset_create(ruby, gemset, runas=None):
    '''
    Creates a gemset.

    ruby
        The ruby version to create the gemset for.
    gemset
        The name of the gemset to create.
    runas : None
        The user to run rvm as.

    CLI Example:

    .. code-block:: bash

        salt '*' rvm.gemset_create 2.0.0 foobar
    '''
    return _rvm_do(ruby,
                   'rvm gemset create {gemset}'.format(gemset=gemset),
                   runas=runas)


def gemset_list(ruby='default', runas=None):
    '''
    List all gemsets for the given ruby.

    ruby : default
        The ruby version to list the gemsets for
    runas : None
        The user to run rvm as.

    CLI Example:

    .. code-block:: bash

        salt '*' rvm.gemset_list
    '''
    gemsets = []
    output = _rvm_do(ruby, 'rvm gemset list', runas=runas)
    if output:
        regex = re.compile('^   ([^ ]+)')
        for line in output.splitlines():
            match = regex.match(line)
            if match:
                gemsets.append(match.group(1))
    return gemsets


def gemset_delete(ruby, gemset, runas=None):
    '''
    Deletes a gemset.

    ruby
        The ruby version the gemset belongs to.
    gemset
        The gemset to delete.
    runas : None
        The user to run rvm as.

    CLI Example:

    .. code-block:: bash

        salt '*' rvm.gemset_delete 2.0.0 foobar
    '''
    return _rvm_do(ruby,
                   'rvm --force gemset delete {gemset}'.format(gemset=gemset),
                   runas=runas)


def gemset_empty(ruby, gemset, runas=None):
    '''
    Remove all gems from a gemset.

    ruby
        The ruby version the gemset belongs to.
    gemset
        The gemset to empty.
    runas : None
        The user to run rvm as.

    CLI Example:

    .. code-block:: bash

        salt '*' rvm.gemset_empty 2.0.0 foobar
    '''
    return _rvm_do(ruby,
                   'rvm --force gemset empty {gemset}'.format(gemset=gemset),
                   runas=runas)


def gemset_copy(source, destination, runas=None):
    '''
    Copy all gems from one gemset to another.

    source
        The name of the gemset to copy, complete with ruby version.
    destination
        The destination gemset.
    runas : None
        The user to run rvm as.

    CLI Example:

    .. code-block:: bash

        salt '*' rvm.gemset_copy foobar bazquo
    '''
    return _rvm('gemset copy {0} {1}'.format(source, destination), runas=runas)


def gemset_list_all(runas=None):
    '''
    List all gemsets for all installed rubies.

    Note that you must have set a default ruby before this can work.

    runas : None
        The user to run rvm as.

    CLI Example:

    .. code-block:: bash

        salt '*' rvm.gemset_list_all
    '''
    gemsets = {}
    current_ruby = None
    output = _rvm_do('default', 'rvm gemset list_all', runas=runas)
    if output:
        gems_regex = re.compile('^   ([^ ]+)')
        gemset_regex = re.compile('^gemsets for ([^ ]+)')
        for line in output.splitlines():
            match = gemset_regex.match(line)
            if match:
                current_ruby = match.group(1)
                gemsets[current_ruby] = []
            match = gems_regex.match(line)
            if match:
                gemsets[current_ruby].append(match.group(1))
    return gemsets


def do(ruby, command, runas=None, cwd=None):  # pylint: disable=C0103
    '''
    Execute a command in an RVM controlled environment.

    ruby:
        The ruby to use.
    command:
        The command to execute.
    runas : None
        The user to run rvm as.
    cwd : None
        The current working directory.

    CLI Example:

    .. code-block:: bash

        salt '*' rvm.do 2.0.0 <command>
    '''
    return _rvm_do(ruby, command, runas=runas, cwd=cwd)
