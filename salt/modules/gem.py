'''
Manage ruby gems.
'''

# Import python libs
import re


__opts__ = {}
__pillar__ = {}

def _gem(command, ruby=None, runas=None):
    cmdline = 'gem {command}'.format(command=command)
    if __salt__['rvm.is_installed']():
        return __salt__['rvm.do'](ruby, cmdline, runas=runas)

    ret = __salt__['cmd.run_all'](
        cmdline,
        runas=runas or __opts__.get('rvm.runas') or __pillar__.get('rvm.runas')
        )

    if ret['retcode'] == 0:
        return ret['stdout']
    else:
        return False


def install(gems, ruby=None, runas=None):
    '''
    Installs one or several gems.

    gems
        The gems to install.
    ruby : None
        If RVM is installed, the ruby version and gemset to use.
    runas : None
        The user to run gem as.
    '''
    return _gem('install {gems}'.format(gems=gems), ruby, runas=runas)


def uninstall(gems, ruby=None, runas=None):
    '''
    Uninstall one or several gems.

    gems
        The gems to uninstall.
    ruby : None
        If RVM is installed, the ruby version and gemset to use.
    runas : None
        The user to run gem as.
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
    '''
    return _gem('update --system {version}'.
                format(version=version), ruby, runas=runas)


def list(prefix='', ruby=None, runas=None):
    '''
    List locally installed gems.

    prefix :
        Only list gems when the name matches this prefix.
    ruby : None
        If RVM is installed, the ruby version and gemset to use.
    runas : None
        The user to run gem as.
    '''
    gems = {}
    stdout = _gem('list {prefix}'.format(prefix=prefix),
                     ruby, runas=runas)
    lines = []
    if isinstance(stdout, str):
        lines = stdout.splitlines()
    for line in lines:
        m = re.match('^([^ ]+) \((.+)\)', line)
        if m:
            gem = m.group(1)
            versions = m.group(2).split(', ')
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
    '''
    return _gem('sources', ruby, runas=runas).splitlines()[2:]
