'''
Create virtualenv environments
'''
from salt.exceptions import CommandNotFoundError


__opts__ = {
    'venv_bin': 'virtualenv',
}


def create(path,
        venv_bin=__opts__['venv_bin'],
        no_site_packages=True,
        system_site_packages=False,
        clear=False,
        python='',
        extra_search_dir='',
        never_download=False,
        prompt='',
        runas=None):
    '''
    Create a virtualenv

    path
        The path to create the virtualenv
    venv_bin : 'virtualenv'
        The name (and optionally path) of the virtualenv command. This can also
        be set globally in the minion config file as ``virtualenv.venv_bin``.
    no_site_packages : True
        Passthrough argument given to virtualenv
    system_site_packages : False
        Passthrough argument given to virtualenv
    clear : False
        Passthrough argument given to virtualenv
    python : (default)
        Passthrough argument given to virtualenv
    extra_search_dir : (default)
        Passthrough argument given to virtualenv
    never_download : (default)
        Passthrough argument given to virtualenv
    prompt : (default)
        Passthrough argument given to virtualenv
    runas : None
        Set ownership for the virtualenv

    CLI Example::

        salt '*' pip.virtualenv /path/to/new/virtualenv
    '''
    if not __salt__['cmd.has_exec'](venv_bin):
        raise CommandNotFoundError(
            "Please install {venv_bin}".format(venv_bin=venv_bin))

    cmd = '{venv_bin} {args} {path}'.format(
            venv_bin=venv_bin,
            args=''.join([
                ' --no-site-packages' if no_site_packages else '',
                ' --system-site-packages' if system_site_packages else '',
                ' --clear' if clear else '',
                ' --python {0}'.format(python) if python else '',
                ' --extra-search-dir {0}'.format(extra_search_dir
                    ) if extra_search_dir else '',
                ' --never-download' if never_download else '',
                ' --prompt {0}'.format(prompt) if prompt else '']),
            path=path)

    return __salt__['cmd.run'](cmd, runas=runas)
