'''
Install Python packages with pip to either the system or a virtualenv
'''
__opts__ = {
    'pip_bin': 'pip',
}

import os

def _get_pip_bin(pip, env):
    '''
    Return the pip command to call, either from a virtualenv, an argument
    passed in, or from the global modules options
    '''
    if env:
        return os.path.join(env, 'bin', 'pip')
    else:
        return pip if pip else __opts__['pip_bin']

def install(env='', requirements='', pkgs='', pip_bin=''):
    '''
    Install packages with pip

    Install packages individually or from a pip requirements file. Install
    packages globally or to a virtualenv.

    env : None
        The path to a virtualenv that pip should install to. This option takes
        precendence over the ``pip_bin`` argument.
    requirements : None
        The path to a pip requirements file to install from
    pkgs : None
        A list of space-separated packages to install
    pip_bin : 'pip'
        The name (and optionally path) of the pip command to call. This option
        will be ignored if the ``env`` argument is given since it will default
        to the pip that is installed in the virtualenv. This option can also be
        set in the minion config file as ``pip.pip_bin``.

    CLI Example::

        salt '*' pip.install /var/www/myvirtualenv.com \\
                /path/to/requirements.txt
    '''
    cmd = '{pip_bin} install {env} {reqs} {pkgs}'.format(
        pip_bin=_get_pip_bin(pip_bin, env),
        env='-E {0}'.format(env if env else ''),
        reqs='-r {0}'.format(requirements if requirements else ''),
        pkgs=pkgs)

    return __salt__['cmd.run'](cmd)

def freeze(env='', pip_bin=''):
    '''
    Return a list of installed packages either globally or in the specified
    virtualenv

    env : None
        The path to a virtualenv that pip should install to. This option takes
        precendence over the ``pip_bin`` argument.
    pip_bin : 'pip'
        The name (and optionally path) of the pip command to call. This option
        will be ignored if the ``env`` argument is given since it will default
        to the pip that is installed in the virtualenv. This option can also be
        set in the minion config file as ``pip.pip_bin``.
    '''
    # Using freeze with -E seems to be twitchy on older pips so call the pip
    # inside the venv if using a venv
    cmd = '{0} freeze'.format(_get_pip_bin(pip_bin, env))

    return __salt__['cmd.run'](cmd).split('\n')
