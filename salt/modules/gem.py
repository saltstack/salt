# -*- coding: utf-8 -*-
'''
Manage ruby gems.
'''

# Import python libs
import re

__func_alias__ = {
    'list_': 'list'
}


def _gem(command, ruby=None, runas=None):
    cmdline = 'gem {command}'.format(command=command)
    if __salt__['rvm.is_installed'](runas=runas):
        return __salt__['rvm.do'](ruby, cmdline, runas=runas)

    ret = __salt__['cmd.run_all'](
        cmdline,
        runas=runas
        )

    if ret['retcode'] == 0:
        return ret['stdout']
    else:
        return False


def install(gems,           # pylint: disable=C0103
            ruby=None,
            runas=None,
            version=None,
            rdoc=False,
            ri=False):      # pylint: disable=C0103
    '''
    Installs one or several gems.

    gems
        The gems to install
    ruby : None
        If RVM is installed, the ruby version and gemset to use.
    runas : None
        The user to run gem as.
    version : None
        Specify the version to install for the gem.
        Doesn't play nice with multiple gems at once
    rdoc : False
        Generate RDoc documentation for the gem(s).
    ri : False
        Generate RI documentation for the gem(s).

    CLI Example:

    .. code-block:: bash

        salt '*' gem.install vagrant
    '''
    options = ''
    if version:
        options += ' --version {0}'.format(version)
    if not rdoc:
        options += ' --no-rdoc'
    if not ri:
        options += ' --no-ri'

    return _gem('install {gems} {options}'.format(gems=gems, options=options),
                ruby,
                runas=runas)


def uninstall(gems, ruby=None, runas=None):
    '''
    Uninstall one or several gems.

    gems
        The gems to uninstall.
    ruby : None
        If RVM is installed, the ruby version and gemset to use.
    runas : None
        The user to run gem as.

    CLI Example:

    .. code-block:: bash

        salt '*' gem.uninstall vagrant
    '''
    return _gem('uninstall {gems}'.format(gems=gems), ruby, runas=runas)


def update(gems, ruby=None, runas=None):
    '''
    Update one or several gems.

    gems
        The gems to update.
    ruby : None
        If RVM is installed, the ruby version and gemset to use.
    runas : None
        The user to run gem as.

    CLI Example:

    .. code-block:: bash

        salt '*' gem.update vagrant
    '''
    return _gem('update {gems}'.format(gems=gems), ruby, runas=runas)


def update_system(version='', ruby=None, runas=None):
    '''
    Update rubygems.

    version : (newest)
        The version of rubygems to install.
    ruby : None
        If RVM is installed, the ruby version and gemset to use.
    runas : None
        The user to run gem as.

    CLI Example:

    .. code-block:: bash

        salt '*' gem.update_system
    '''
    return _gem('update --system {version}'.
                format(version=version), ruby, runas=runas)


def list_(prefix='', ruby=None, runas=None):
    '''
    List locally installed gems.

    prefix :
        Only list gems when the name matches this prefix.
    ruby : None
        If RVM is installed, the ruby version and gemset to use.
    runas : None
        The user to run gem as.

    CLI Example:

    .. code-block:: bash

        salt '*' gem.list
    '''
    gems = {}
    stdout = _gem('list {prefix}'.format(prefix=prefix),
                     ruby, runas=runas)
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


def sources_add(source_uri, ruby=None, runas=None):
    '''
    Add a gem source.

    source_uri
        The source URI to add.
    ruby : None
        If RVM is installed, the ruby version and gemset to use.
    runas : None
        The user to run gem as.

    CLI Example:

    .. code-block:: bash

        salt '*' gem.sources_add http://rubygems.org/
    '''
    return _gem('sources --add {source_uri}'.
                format(source_uri=source_uri), ruby, runas=runas)


def sources_remove(source_uri, ruby=None, runas=None):
    '''
    Remove a gem source.

    source_uri
        The source URI to remove.
    ruby : None
        If RVM is installed, the ruby version and gemset to use.
    runas : None
        The user to run gem as.

    CLI Example:

    .. code-block:: bash

        salt '*' gem.sources_remove http://rubygems.org/
    '''
    return _gem('sources --remove {source_uri}'.
                format(source_uri=source_uri), ruby, runas=runas)


def sources_list(ruby=None, runas=None):
    '''
    List the configured gem sources.

    ruby : None
        If RVM is installed, the ruby version and gemset to use.
    runas : None
        The user to run gem as.

    CLI Example:

    .. code-block:: bash

        salt '*' gem.sources_list
    '''
    ret = _gem('sources', ruby, runas=runas)
    return [] if ret is False else ret.splitlines()[2:]
