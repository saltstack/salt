'''
Create virtualenv environments
'''
# Import python libs
from salt import utils


__opts__ = {}
__pillar__ = {}


def create(path,
        venv_bin=None,
        no_site_packages=False,
        system_site_packages=False,
        distribute=False,
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
    no_site_packages : False
        Passthrough argument given to virtualenv
    system_site_packages : False
        Passthrough argument given to virtualenv
    distribute : False
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

        salt '*' virtualenv.create /path/to/new/virtualenv
    '''
    if venv_bin is None:
        venv_bin = __opts__.get('venv_bin') or __pillar__.get('venv_bin')
    # raise CommandNotFoundError if venv_bin is missing
    utils.check_or_die(venv_bin)

    cmd = '{venv_bin} {args} {path}'.format(
            venv_bin=venv_bin,
            args=''.join([
                ' --no-site-packages' if no_site_packages else '',
                ' --system-site-packages' if system_site_packages else '',
                ' --distribute' if distribute else '',
                ' --clear' if clear else '',
                ' --python {0}'.format(python) if python else '',
                ' --extra-search-dir {0}'.format(extra_search_dir
                    ) if extra_search_dir else '',
                ' --never-download' if never_download else '',
                ' --prompt {0}'.format(prompt) if prompt else '']),
            path=path)

    return __salt__['cmd.run'](cmd, runas=runas)
