'''
Create virtualenv environments
'''

# Import python libs
from salt import utils

# Import 3rd party libs
try:
    import virtualenv
    HAS_VIRTUALENV = True
    VIRTUALENV_VERSION_INFO = tuple(
        [int(i) for i in virtualenv.__version__.split('rc')[0].split('.')]
    )
except ImportError:
    HAS_VIRTUALENV = False

__opts__ = {
    'venv_bin': 'virtualenv'
}

__pillar__ = {}


def __virtual__():
    if HAS_VIRTUALENV is False:
        return False
    return 'virtualenv'


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
           symlinks=False,
           upgrade=False,
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
        Passthrough argument given to virtualenv or pyvenv
    distribute : False
        Passthrough argument given to virtualenv
    clear : False
        Passthrough argument given to virtualenv or pyvenv
    python : (default)
        Passthrough argument given to virtualenv
    extra_search_dir : (default)
        Passthrough argument given to virtualenv
    never_download : (default)
        Passthrough argument given to virtualenv
    prompt : (default)
        Passthrough argument given to virtualenv
    symlinks : False
        Passthrough argument given to pyvenv
    upgrade : False
        Passthrough argument given to pyvenv
    runas : None
        Set ownership for the virtualenv

    CLI Example::

        salt '*' virtualenv.create /path/to/new/virtualenv
    '''
    if venv_bin is None:
        venv_bin = __opts__.get('venv_bin') or __pillar__.get('venv_bin')
    # raise CommandNotFoundError if venv_bin is missing
    utils.check_or_die(venv_bin)

    cmd = [venv_bin]

    if 'pyvenv' not in venv_bin:
        # Virtualenv package
        if no_site_packages:
            cmd.append('--no-site-packages')
        if system_site_packages:
            cmd.append('--system-site-packages')
        if distribute:
            if VIRTUALENV_VERSION_INFO >= (1, 10):
                log.info(
                    'The virtualenv \'--distribute\' option has been '
                    'deprecated in virtualenv(>=1.10), as such, the '
                    '\'distribute\' option to `virtualenv.create()` has '
                    'also been deprecated and it\'s not necessary anymore.'
                )
            else:
                cmd.append('--distribute')
        if python:
            cmd.append('--python={0}'.format(python))
        if extra_search_dir:
            cmd.append('--extra-search-dir={0}'.format(extra_search_dir))
        if never_download:
            cmd.append('--never-download')
        if prompt:
            cmd.append('--prompt={0}'.format(prompt))
    else:
        # venv module from the Python >= 3.3 standard library
        if upgrade:
            cmd.append('--upgrade')
        if symlinks:
            cmd.append('--symlinks')

    # Common options
    if clear:
        cmd.append('--clear')
    if system_site_packages:
        cmd.append('--system-site-packages')

    # Finally the virtualenv path
    cmd.append(path)

    return __salt__['cmd.run_all'](' '.join(cmd), runas=runas)
