# -*- coding: utf-8 -*-
'''
Manage ruby gems.
'''
from __future__ import absolute_import

# Import python libs
import re
import logging

# Import salt libs
from salt.exceptions import CommandExecutionError

logger = logging.getLogger(__name__)  # pylint: disable=C0103

__func_alias__ = {
    'list_': 'list'
}


def _gem(command, ruby=None, runas=None, gem_bin=None):
    cmdline = '{gem} {command}'.format(gem=gem_bin or 'gem', command=command)

    # If a custom gem is given, use that and don't check for rvm/rbenv. User
    # knows best!
    if gem_bin is None:
        if __salt__['rvm.is_installed'](runas=runas):
            return __salt__['rvm.do'](ruby, cmdline, runas=runas)

        if __salt__['rbenv.is_installed'](runas=runas):
            if ruby is None:
                return __salt__['rbenv.do'](cmdline, runas=runas)
            else:
                return __salt__['rbenv.do_with_ruby'](ruby, cmdline, runas=runas)

    ret = __salt__['cmd.run_all'](
        cmdline,
        runas=runas,
        python_shell=False
        )

    if ret['retcode'] == 0:
        return ret['stdout']
    else:
        logger.error(ret['stderr'])
        raise CommandExecutionError(ret['stderr'])


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

    gems
        The gems to install
    gem_bin : None
        Full path to ``gem`` binary to use.
    ruby : None
        If RVM or rbenv are installed, the ruby version and gemset to use.
        Ignored if ``gem_bin`` is specified.
    runas : None
        The user to run gem as.
    version : None
        Specify the version to install for the gem.
        Doesn't play nice with multiple gems at once
    rdoc : False
        Generate RDoc documentation for the gem(s).
    ri : False
        Generate RI documentation for the gem(s).
    pre_releases
        Include pre-releases in the available versions
    proxy : None
        Use the specified HTTP proxy server for all outgoing traffic.
        Format: http://hostname[:port]

    CLI Example:

    .. code-block:: bash

        salt '*' gem.install vagrant

        salt '*' gem.install redphone gem_bin=/opt/sensu/embedded/bin/gem
    '''
    options = []
    if version:
        options.append('--version {0}'.format(version))
    if not rdoc:
        options.append('--no-rdoc')
    if not ri:
        options.append('--no-ri')
    if pre_releases:
        options.append('--pre')
    if proxy:
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

    gems
        The gems to uninstall.
    gem_bin : None
        Full path to ``gem`` binary to use.
    ruby : None
        If RVM or rbenv are installed, the ruby version and gemset to use.
        Ignored if ``gem_bin`` is specified.
    runas : None
        The user to run gem as.

    CLI Example:

    .. code-block:: bash

        salt '*' gem.uninstall vagrant
    '''
    return _gem('uninstall {gems}'.format(gems=gems),
                ruby,
                gem_bin=gem_bin,
                runas=runas)


def update(gems, ruby=None, runas=None, gem_bin=None):
    '''
    Update one or several gems.

    gems
        The gems to update.
    gem_bin : None
        Full path to ``gem`` binary to use.
    ruby : None
        If RVM or rbenv are installed, the ruby version and gemset to use.
        Ignored if ``gem_bin`` is specified.
    runas : None
        The user to run gem as.

    CLI Example:

    .. code-block:: bash

        salt '*' gem.update vagrant
    '''
    return _gem('update {gems}'.format(gems=gems),
                ruby,
                gem_bin=gem_bin,
                runas=runas)


def update_system(version='', ruby=None, runas=None, gem_bin=None):
    '''
    Update rubygems.

    version : (newest)
        The version of rubygems to install.
    gem_bin : None
        Full path to ``gem`` binary to use.
    ruby : None
        If RVM or rbenv are installed, the ruby version and gemset to use.
        Ignored if ``gem_bin`` is specified.
    runas : None
        The user to run gem as.

    CLI Example:

    .. code-block:: bash

        salt '*' gem.update_system
    '''
    return _gem('update --system {version}'.format(version=version),
                ruby,
                gem_bin=gem_bin,
                runas=runas)


def list_(prefix='', ruby=None, runas=None, gem_bin=None):
    '''
    List locally installed gems.

    prefix :
        Only list gems when the name matches this prefix.
    gem_bin : None
        Full path to ``gem`` binary to use.
    ruby : None
        If RVM or rbenv are installed, the ruby version and gemset to use.
        Ignored if ``gem_bin`` is specified.
    runas : None
        The user to run gem as.

    CLI Example:

    .. code-block:: bash

        salt '*' gem.list
    '''
    gems = {}
    stdout = _gem('list {prefix}'.format(prefix=prefix),
                  ruby,
                  gem_bin=gem_bin,
                  runas=runas)
    lines = stdout.splitlines()
    for line in lines:
        match = re.match(r'^([^ ]+) \((.+)\)', line)
        if match:
            gem = match.group(1)
            versions = match.group(2).split(', ')
            gems[gem] = versions
    return gems


def list_upgrades(ruby=None,
                  runas=None,
                  gem_bin=None):
    '''
    .. versionadded:: Beryllium

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
    '''
    result = _gem('outdated',
                  ruby,
                  gem_bin=gem_bin,
                  runas=runas)
    outdated = {}
    for line in result.splitlines():
        match = re.search(r'(\S+) \(\S+ < (\S+)\)', line)
        if match:
            name, version = match.groups()
        else:
            logger.error('Can\'t parse line {0!r}'.format(line))
            continue
        outdated[name] = version
    return outdated


def sources_add(source_uri, ruby=None, runas=None, gem_bin=None):
    '''
    Add a gem source.

    source_uri
        The source URI to add.
    gem_bin : None
        Full path to ``gem`` binary to use.
    ruby : None
        If RVM or rbenv are installed, the ruby version and gemset to use.
        Ignored if ``gem_bin`` is specified.
    runas : None
        The user to run gem as.

    CLI Example:

    .. code-block:: bash

        salt '*' gem.sources_add http://rubygems.org/
    '''
    return _gem('sources --add {source_uri}'.format(source_uri=source_uri),
                ruby,
                gem_bin=gem_bin,
                runas=runas)


def sources_remove(source_uri, ruby=None, runas=None, gem_bin=None):
    '''
    Remove a gem source.

    source_uri
        The source URI to remove.
    gem_bin : None
        Full path to ``gem`` binary to use.
    ruby : None
        If RVM or rbenv are installed, the ruby version and gemset to use.
        Ignored if ``gem_bin`` is specified.
    runas : None
        The user to run gem as.

    CLI Example:

    .. code-block:: bash

        salt '*' gem.sources_remove http://rubygems.org/
    '''
    return _gem('sources --remove {source_uri}'.format(source_uri=source_uri),
                ruby,
                gem_bin=gem_bin,
                runas=runas)


def sources_list(ruby=None, runas=None, gem_bin=None):
    '''
    List the configured gem sources.

    gem_bin : None
        Full path to ``gem`` binary to use.
    ruby : None
        If RVM or rbenv are installed, the ruby version and gemset to use.
        Ignored if ``gem_bin`` is specified.
    runas : None
        The user to run gem as.

    CLI Example:

    .. code-block:: bash

        salt '*' gem.sources_list
    '''
    ret = _gem('sources', ruby, gem_bin=gem_bin, runas=runas)
    return [] if ret is False else ret.splitlines()[2:]
