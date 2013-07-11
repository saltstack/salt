'''
Create virtualenv environments
'''

# Import python libs
import logging
import warnings

# Import salt libs
import salt.utils
import salt.exceptions

log = logging.getLogger(__name__)

__opts__ = {
    'venv_bin': 'virtualenv'
}

__pillar__ = {}


def __virtual__():
    return 'virtualenv'


def create(path,
           venv_bin=None,
           no_site_packages=False,
           system_site_packages=False,
           distribute=False,
           clear=False,
           python=None,
           extra_search_dir=None,
           never_download=False,
           prompt=None,
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
        Passthrough argument given to virtualenv. Deprecated since salt>=0.17.0
        Use ``system_site_packages=False`` instead.
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
    salt.utils.check_or_die(venv_bin)

    if no_site_packages:
        # Show a deprecation warning
        # XXX: Remove deprecation warning message on 0.18.0
        warnings.filterwarnings(
            'once', '', DeprecationWarning, __name__
        )
        warnings.warn(
            '\'no_site_packages\' has been deprecated. Please start using '
            '\'system_site_packages=False\' which means exactly the same '
            'as \'no_site_packages=True\'',
            DeprecationWarning
        )

    if no_site_packages and system_site_packages:
        raise salt.exceptions.CommandExecutionError(
            '\'no_site_packages\' and \'system_site_packages\' are mutually '
            'exclusive options. Please use only one, and prefer '
            '\'system_site_packages\' since \'no_site_packages\' has been '
            'deprecated.'
        )

    cmd = [venv_bin]

    if 'pyvenv' not in venv_bin:
        # Virtualenv package
        try:
            import virtualenv
            VIRTUALENV_VERSION_INFO = tuple(
                [int(i) for i in
                 virtualenv.__version__.split('rc')[0].split('.')]
            )
        except ImportError:
            # Unable to import?? Let's parse the version from the console
            version_cmd = '{0} --version'.format(venv_bin)
            ret = __salt__['cmd.run_all'](version_cmd, runas=runas)
            if ret['retcode'] > 0:
                raise salt.exceptions.CommandExecutionError(
                    'Unable to get the virtualenv version output using {0!r}. '
                    'Returned data: {1!r}'.format(version_cmd, ret)
                )
            VIRTUALENV_VERSION_INFO = tuple(
                [int(i) for i in ret['stdout'].split('rc')[0].split('.')]
            )

        if no_site_packages:
            cmd.append('--no-site-packages')
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
            if isinstance(extra_search_dir, basestring):
                if ',' in extra_search_dir:
                    extra_search_dir = [
                        e.strip() for e in extra_search_dir.split(',')
                    ]
                else:
                    extra_search_dir = [extra_search_dir]
            for entry in extra_search_dir:
                cmd.append('--extra-search-dir={0}'.format(entry))
        if never_download:
            if VIRTUALENV_VERSION_INFO >= (1, 10):
                log.info(
                    'The virtualenv \'--never-download\' option has been '
                    'deprecated in virtualenv(>=1.10), as such, the '
                    '\'never_download\' option to `virtualenv.create()` has '
                    'also been deprecated and it\'s not necessary anymore.'
                )
            else:
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
