'''
Manage ruby installations with rbenv.
'''

# Import python libs
import os
import re
import logging

# Set up logger
log = logging.getLogger(__name__)

__func_alias__ = {
    'list_': 'list'
}

__opts__ = {
    'rbenv.root': None,
}


def _rbenv_exec(command, args='', env=None, runas=None, ret=None):
    if not is_installed(runas):
        return False

    binary = _rbenv_bin(runas)
    path = _rbenv_path(runas)

    if env:
        env = ' {0}'.format(env)
    env = env or ''

    binary = 'env RBENV_ROOT={0}{1} {2}'.format(path, env, binary)

    result = __salt__['cmd.run_all'](
        '{0} {1} {2}'.format(binary, command, args),
        runas=runas
    )

    if isinstance(ret, dict):
        ret.update(result)
        return ret

    if result['retcode'] == 0:
        return result['stdout']
    else:
        return False


def _rbenv_bin(runas=None):
    path = _rbenv_path(runas)
    return '{0}/bin/rbenv'.format(path)


def _rbenv_path(runas=None):
    path = None
    if runas in (None, 'root'):
        path = __salt__['config.option']('rbenv.root') or '/usr/local/rbenv'
    else:
        path = __salt__['config.option']('rbenv.root') or '~{0}/.rbenv'.format(runas)

    return os.path.expanduser(path)


def _install_rbenv(path, runas=None):
    if os.path.isdir(path):
        return True

    return 0 == __salt__['cmd.retcode'](
        'git clone https://github.com/sstephenson/rbenv.git {0}'.format(path), runas=runas)


def _install_ruby_build(path, runas=None):
    path = '{0}/plugins/ruby-build'.format(path)
    if os.path.isdir(path):
        return True

    return 0 == __salt__['cmd.retcode'](
        'git clone https://github.com/sstephenson/ruby-build.git {0}'.format(path), runas=runas)


def _update_rbenv(path, runas=None):
    if not os.path.isdir(path):
        return False

    return 0 == __salt__['cmd.retcode'](
        'git pull --git-dir {0}'.format(path), runas=runas)


def _update_ruby_build(path, runas=None):
    path = '{0}/plugins/ruby-build'.format(path)
    if not os.path.isdir(path):
        return False

    return 0 == __salt__['cmd.retcode'](
        'git pull --git-dir {0}'.format(path), runas=runas)


def install(runas=None, path=None):
    '''
    Install Rbenv systemwide

    CLI Example::

        salt '*' rbenv.install
    '''

    path = path or _rbenv_path(runas)
    path = os.path.expanduser(path)
    return (_install_rbenv(path, runas) and _install_ruby_build(path, runas))


def update(runas=None, path=None):
    '''
    Updates the current versions of Rbenv and Ruby-Build

    CLI Example::

        salt '*' rbenv.update
    '''

    path = path or _rbenv_path(runas)
    path = os.path.expanduser(path)

    return (_update_rbenv(path, runas) and _update_ruby_build(path, runas))


def is_installed(runas=None):
    '''
    Check if Rbenv is installed.

    CLI Example::

        salt '*' rbenv.is_installed
    '''
    return __salt__['cmd.has_exec'](_rbenv_bin(runas))


def install_ruby(ruby, runas=None):
    '''
    Install a ruby implementation.

    ruby
        The version of Ruby to install, should match one of the
        versions listed by rbenv.list

    CLI Example::

        salt '*' rbenv.install_ruby 2.0.0-p0
    '''

    ruby = re.sub(r'^ruby-', '', ruby)

    env = None
    if __grains__['os'] in ('FreeBSD', 'NetBSD', 'OpenBSD'):
        env = 'MAKE=gmake'

    ret = {}
    ret = _rbenv_exec('install', ruby, env=env, runas=runas, ret=ret)
    if ret['retcode'] == 0:
        return ret['stderr']
    else:
        # Cleanup the failed installation so it doesn't list as installed
        uninstall_ruby(ruby, runas=runas)
        return False


def uninstall_ruby(ruby, runas=None):
    '''
    Uninstall a ruby implementation.

    ruby
        The version of ruby to uninstall. Should match one of
        the versions listed by rbenv.versions

    CLI Example::

        salt '*' rbenv.uninstall_ruby 2.0.0-p0
    '''

    ruby = re.sub(r'^ruby-', '', ruby)

    args = '--force {0}'.format(ruby)
    _rbenv_exec('uninstall', args, runas=runas)
    return True


def versions(runas=None):
    '''
    List the installed versions of ruby.

    CLI Example::

        salt '*' rbenv.versions
    '''

    ret = _rbenv_exec('versions', '--bare', runas=runas)
    return [] if ret is False else ret.splitlines()


def default(ruby=None, runas=None):
    '''
    Returns or sets the currently defined default ruby.

    ruby=None
        The version to set as the default. Should match one of
        the versions listed by rbenv.versions.
        Leave blank to return the current default.

    CLI Example::

        salt '*' rbenv.default
        # 2.0.0-p0

        salt '*' rbenv.default 2.0.0-p0
    '''

    if ruby:
        _rbenv_exec('global', ruby, runas=runas)
        return True
    else:
        ret = _rbenv_exec('global', runas=runas)
        return '' if ret is False else ret.strip()


def list_(runas=None):
    '''
    List the installable versions of ruby.

    CLI Example::

        salt '*' rbenv.list
    '''

    ret = []
    output = _rbenv_exec('install', '--list', runas=runas)
    if output:
        for line in output.splitlines():
            if line == 'Available versions:':
                continue
            ret.append(line.strip())
    return ret
