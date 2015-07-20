# -*- coding: utf-8 -*-
'''
Manage ruby gems.
'''
from __future__ import absolute_import

try:
    from shlex import quote as _cmd_quote  # pylint: disable=E0611
except ImportError:
    from pipes import quote as _cmd_quote

# Import python libs
import re

# Import salt libs
import salt.utils

__func_alias__ = {
    'list_': 'list'
}


def _gem(command, ruby=None, runas=None, gem_bin=None):
    '''
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
    '''
    cmdline = '{gem} {command}'.format(gem=gem_bin or 'gem', command=command)

    # If a custom gem is given, use that and don't check for rvm/rbenv. User
    # knows best!
    if gem_bin is None:
        if __salt__['rvm.is_installed'](runas=runas):
            return __salt__['rvm.do'](ruby, cmdline, runas=runas)

        if not salt.utils.is_windows() and __salt__['rbenv.is_installed'](runas=runas):
            if ruby is None:
                return __salt__['rbenv.do'](cmdline, runas=runas)
            else:
                return __salt__['rbenv.do_with_ruby'](ruby, cmdline, runas=runas)

    ret = __salt__['cmd.run_all'](
        cmdline,
        runas=runas,
        python_shell=True
        )

    if ret['retcode'] == 0:
        return ret['stdout']
    else:
        return False


def install(gems,           # pylint: disable=C0103
            ruby=None,
            gem_bin=None,
            runas=None,
            version=None,
            rdoc=False,
            ri=False,
            pre_releases=False,
            proxy=None):      # pylint: disable=C0103
    '''
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
    :param ri: boolean : False
        Generate RI documentation for the gem(s).
    :param pre_releases: boolean : False
        Include pre-releases in the available versions
    :param proxy: string : None
        Use the specified HTTP proxy server for all outgoing traffic.
        Format: http://hostname[:port]

    CLI Example:

    .. code-block:: bash

        salt '*' gem.install vagrant

        salt '*' gem.install redphone gem_bin=/opt/sensu/embedded/bin/gem
    '''

    # Check for injection
    if gems:
        gems = ' '.join([_cmd_quote(gem) for gem in gems.split()])
    if ruby:
        ruby = _cmd_quote(ruby)
    if gem_bin:
        gem_bin = _cmd_quote(gem_bin)

    options = []
    if version:
        version = _cmd_quote(version)  # injection check
        options.append('--version {0}'.format(version))
    if not rdoc:
        options.append('--no-rdoc')
    if not ri:
        options.append('--no-ri')
    if pre_releases:
        options.append('--pre')
    if proxy:
        proxy = _cmd_quote(proxy)  # injection check
        options.append('-p {0}'.format(proxy))

    cmdline_args = ' '.join(options)
    return _gem('install {gems} {options}'.format(gems=gems,
                                                  options=cmdline_args),
                ruby,
                gem_bin=gem_bin,
                runas=runas)


def uninstall(gems, ruby=None, runas=None, gem_bin=None):
    '''
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
    '''
    # Check for injection
    if gems:
        gems = ' '.join([_cmd_quote(gem) for gem in gems.split()])
    if ruby:
        ruby = _cmd_quote(ruby)
    if gem_bin:
        gem_bin = _cmd_quote(gem_bin)

    return _gem('uninstall {gems} -a -x'.format(gems=gems),
                ruby,
                gem_bin=gem_bin,
                runas=runas)


def update(gems, ruby=None, runas=None, gem_bin=None):
    '''
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
    '''
    # Check for injection
    if gems:
        gems = ' '.join([_cmd_quote(gem) for gem in gems.split()])
    if ruby:
        ruby = _cmd_quote(ruby)
    if gem_bin:
        gem_bin = _cmd_quote(gem_bin)

    return _gem('update {gems}'.format(gems=gems),
                ruby,
                gem_bin=gem_bin,
                runas=runas)


def update_system(version='', ruby=None, runas=None, gem_bin=None):
    '''
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
    '''
    # Check for injection
    if version:
        version = _cmd_quote(version)
    if ruby:
        ruby = _cmd_quote(ruby)
    if gem_bin:
        gem_bin = _cmd_quote(gem_bin)

    return _gem('update --system {version}'.format(version=version),
                ruby,
                gem_bin=gem_bin,
                runas=runas)


def list_(prefix='', ruby=None, runas=None, gem_bin=None):
    '''
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
    '''
    gems = {}
    # Check for injection
    if prefix:
        prefix = _cmd_quote(prefix)
    if ruby:
        ruby = _cmd_quote(ruby)
    if gem_bin:
        gem_bin = _cmd_quote(gem_bin)

    stdout = _gem('list {prefix}'.format(prefix=prefix),
                  ruby,
                  gem_bin=gem_bin,
                  runas=runas)

    lines = []
    if isinstance(stdout, str):
        lines = stdout.splitlines()
    for line in lines:
        match = re.match(r'^([^ ]+) \((.+)\)', line)
        if match:
            gem = match.group(1)
            versions = match.group(2).split(', ')
            gems[gem] = versions

    return gems


def sources_add(source_uri, ruby=None, runas=None, gem_bin=None):
    '''
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
    '''
    # Check for injection
    if source_uri:
        source_uri = _cmd_quote(source_uri)
    if ruby:
        ruby = _cmd_quote(ruby)
    if gem_bin:
        gem_bin = _cmd_quote(gem_bin)

    return _gem('sources --add {source_uri}'.format(source_uri=source_uri),
                ruby,
                gem_bin=gem_bin,
                runas=runas)


def sources_remove(source_uri, ruby=None, runas=None, gem_bin=None):
    '''
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
    '''
    # Check for injection
    if source_uri:
        source_uri = _cmd_quote(source_uri)
    if ruby:
        ruby = _cmd_quote(ruby)
    if gem_bin:
        gem_bin = _cmd_quote(gem_bin)

    return _gem('sources --remove {source_uri}'.format(source_uri=source_uri),
                ruby,
                gem_bin=gem_bin,
                runas=runas)


def sources_list(ruby=None, runas=None, gem_bin=None):
    '''
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
    '''
    # Check for injection
    if ruby:
        ruby = _cmd_quote(ruby)
    if gem_bin:
        gem_bin = _cmd_quote(gem_bin)

    ret = _gem('sources', ruby, gem_bin=gem_bin, runas=runas)
    return [] if ret is False else ret.splitlines()[2:]
