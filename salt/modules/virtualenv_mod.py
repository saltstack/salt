# -*- coding: utf-8 -*-
'''
Create virtualenv environments
'''

# Import python libs
import glob
import shutil
import logging
import os
import os.path

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
           no_site_packages=None,
           system_site_packages=False,
           distribute=False,
           clear=False,
           python=None,
           extra_search_dir=None,
           never_download=None,
           prompt=None,
           pip=False,
           symlinks=None,
           upgrade=None,
           runas=None):
    '''
    Create a virtualenv

    path
        The path to create the virtualenv
    venv_bin : None (default 'virtualenv')
        The name (and optionally path) of the virtualenv command. This can also
        be set globally in the minion config file as ``virtualenv.venv_bin``.
    no_site_packages : None
        Passthrough argument given to virtualenv if True. Deprecated since
        ``salt>=0.17.0``. Use ``system_site_packages=False`` instead.
    system_site_packages : False
        Passthrough argument given to virtualenv or pyvenv
    distribute : False
        Passthrough argument given to virtualenv
    pip : False
        Install pip after creating a virtual environment,
        implies distribute=True
    clear : False
        Passthrough argument given to virtualenv or pyvenv
    python : None (default)
        Passthrough argument given to virtualenv
    extra_search_dir : None (default)
        Passthrough argument given to virtualenv
    never_download : None (default)
        Passthrough argument given to virtualenv if True
    prompt : None (default)
        Passthrough argument given to virtualenv if not None
    symlinks : None
        Passthrough argument given to pyvenv if True
    upgrade : None
        Passthrough argument given to pyvenv if True
    runas : None
        Set ownership for the virtualenv

    CLI Example:

    .. code-block:: bash

        salt '*' virtualenv.create /path/to/new/virtualenv
    '''
    if venv_bin is None:
        venv_bin = __opts__.get('venv_bin') or __pillar__.get('venv_bin')
    # raise CommandNotFoundError if venv_bin is missing
    salt.utils.check_or_die(venv_bin)

    if no_site_packages is not None:
        # Show a deprecation warning
        salt.utils.warn_until(
            (0, 19),
            '\'no_site_packages\' has been deprecated. Please start using '
            '\'system_site_packages=False\' which means exactly the same '
            'as \'no_site_packages=True\''
        )

    if no_site_packages is True and system_site_packages is True:
        raise salt.exceptions.CommandExecutionError(
            '\'no_site_packages\' and \'system_site_packages\' are mutually '
            'exclusive options. Please use only one, and prefer '
            '\'system_site_packages\' since \'no_site_packages\' has been '
            'deprecated.'
        )

    cmd = [venv_bin]

    if 'pyvenv' not in venv_bin:
        # ----- Stop the user if pyvenv only options are used --------------->
        # If any of the following values are not None, it means that the user
        # is actually passing a True or False value. Stop Him!
        if upgrade is not None:
            raise salt.exceptions.CommandExecutionError(
                'The `upgrade`(`--upgrade`) option is not supported '
                'by {0!r}'.format(venv_bin)
            )
        elif symlinks is not None:
            raise salt.exceptions.CommandExecutionError(
                'The `symlinks`(`--symlinks`) option is not supported '
                'by {0!r}'.format(venv_bin)
            )
        # <---- Stop the user if pyvenv only options are used ----------------

        # Virtualenv package
        try:
            import virtualenv
            version = getattr(virtualenv, '__version__',
                              virtualenv.virtualenv_version)
            virtualenv_version_info = tuple(
                [int(i) for i in version.split('rc')[0].split('.')]
            )
        except ImportError:
            # Unable to import?? Let's parse the version from the console
            version_cmd = '{0} --version'.format(venv_bin)
            ret = __salt__['cmd.run_all'](version_cmd, runas=runas)
            if ret['retcode'] > 0 or not ret['stdout'].strip():
                raise salt.exceptions.CommandExecutionError(
                    'Unable to get the virtualenv version output using {0!r}. '
                    'Returned data: {1!r}'.format(version_cmd, ret)
                )
            virtualenv_version_info = tuple(
                [int(i) for i in
                 ret['stdout'].strip().split('rc')[0].split('.')]
            )

        if no_site_packages is True:
            cmd.append('--no-site-packages')
        if distribute:
            if virtualenv_version_info >= (1, 10):
                log.info(
                    'The virtualenv \'--distribute\' option has been '
                    'deprecated in virtualenv(>=1.10), as such, the '
                    '\'distribute\' option to `virtualenv.create()` has '
                    'also been deprecated and it\'s not necessary anymore.'
                )
            else:
                cmd.append('--distribute')
        if python is not None and python.strip() != '':
            cmd.append('--python={0}'.format(python))
        if extra_search_dir is not None:
            if isinstance(extra_search_dir, basestring) and \
                    extra_search_dir.strip() != '':
                extra_search_dir = [
                    e.strip() for e in extra_search_dir.split(',')
                ]
            for entry in extra_search_dir:
                cmd.append('--extra-search-dir={0}'.format(entry))
        if never_download is True:
            if virtualenv_version_info >= (1, 10):
                log.info(
                    'The virtualenv \'--never-download\' option has been '
                    'deprecated in virtualenv(>=1.10), as such, the '
                    '\'never_download\' option to `virtualenv.create()` has '
                    'also been deprecated and it\'s not necessary anymore.'
                )
            else:
                cmd.append('--never-download')
        if prompt is not None and prompt.strip() != '':
            cmd.append('--prompt={0!r}'.format(prompt))
    else:
        # venv module from the Python >= 3.3 standard library

        # ----- Stop the user if virtualenv only options are being used ----->
        # If any of the following values are not None, it means that the user
        # is actually passing a True or False value. Stop Him!
        if no_site_packages is not None:
            raise salt.exceptions.CommandExecutionError(
                'The `no_site_packages`(`--no-site-packages`) option is not '
                'supported by {0!r}'.format(venv_bin)
            )
        elif python is not None and python.strip() != '':
            raise salt.exceptions.CommandExecutionError(
                'The `python`(`--python`) option is not supported '
                'by {0!r}'.format(venv_bin)
            )
        elif extra_search_dir is not None and extra_search_dir.strip() != '':
            raise salt.exceptions.CommandExecutionError(
                'The `extra_search_dir`(`--extra-search-dir`) option is not '
                'supported by {0!r}'.format(venv_bin)
            )
        elif never_download is not None:
            raise salt.exceptions.CommandExecutionError(
                'The `never_download`(`--never-download`) option is not '
                'supported by {0!r}'.format(venv_bin)
            )
        elif prompt is not None and prompt.strip() != '':
            raise salt.exceptions.CommandExecutionError(
                'The `prompt`(`--prompt`) option is not supported '
                'by {0!r}'.format(venv_bin)
            )
        # <---- Stop the user if virtualenv only options are being used ------

        if upgrade is True:
            cmd.append('--upgrade')
        if symlinks is True:
            cmd.append('--symlinks')

    # Common options to virtualenv and pyvenv
    if clear is True:
        cmd.append('--clear')
    if system_site_packages is True:
        cmd.append('--system-site-packages')

    # Finally the virtualenv path
    cmd.append(path)

    # Let's create the virtualenv
    ret = __salt__['cmd.run_all'](' '.join(cmd), runas=runas)
    if ret['retcode'] > 0:
        # Something went wrong. Let's bail out now!
        return ret

    # Check if distribute and pip are already installed
    if salt.utils.is_windows():
        venv_python = os.path.join(path, 'Scripts', 'python.exe')
        venv_pip = os.path.join(path, 'Scripts', 'pip.exe')
        venv_setuptools = os.path.join(path, 'Scripts', 'easy_install.exe')
    else:
        venv_python = os.path.join(path, 'bin', 'python')
        venv_pip = os.path.join(path, 'bin', 'pip')
        venv_setuptools = os.path.join(path, 'bin', 'easy_install')

    # Install setuptools
    if (pip or distribute) and not os.path.exists(venv_setuptools):
        _install_script(
            'https://bitbucket.org/pypa/setuptools/raw/default/ez_setup.py',
            path, venv_python, runas
        )

        # clear up the distribute archive which gets downloaded
        for fpath in glob.glob(os.path.join(path, 'distribute-*.tar.gz*')):
            os.unlink(fpath)

    if ret['retcode'] > 0:
        # Something went wrong. Let's bail out now!
        return ret

    # Install pip
    if pip and not os.path.exists(venv_pip):
        _ret = _install_script(
            'https://raw.github.com/pypa/pip/master/contrib/get-pip.py',
            path, venv_python, runas
        )
        # Let's update the return dictionary with the details from the pip
        # installation
        ret.update(
            retcode=_ret['retcode'],
            stdout='{0}\n{1}'.format(ret['stdout'], _ret['stdout']).strip(),
            stderr='{0}\n{1}'.format(ret['stderr'], _ret['stderr']).strip(),
        )

    return ret


def get_site_packages(venv):
    '''
    Returns the path to the site-packages directory inside a virtualenv

    CLI Example:

    .. code-block:: bash

        salt '*' virtualenv.get_site_packages /path/to/my/venv
    '''
    bin_path = os.path.join(venv, 'bin/python')

    if not os.path.exists(bin_path):
        raise salt.exceptions.CommandExecutionError(
            "Path does not appear to be a virtualenv: '{0}'".format(bin_path))

    return __salt__['cmd.exec_code'](bin_path,
            'from distutils import sysconfig; print sysconfig.get_python_lib()')


def _install_script(source, cwd, python, runas):
    env = 'base'
    if not salt.utils.is_windows():
        tmppath = salt.utils.mkstemp(dir=cwd)
    else:
        tmppath = __salt__['cp.cache_file'](source, env)

    if not salt.utils.is_windows():
        fn_ = __salt__['cp.cache_file'](source, env)
        shutil.copyfile(fn_, tmppath)
        os.chmod(tmppath, 320)
        os.chown(tmppath, __salt__['file.user_to_uid'](runas), -1)
    try:
        return __salt__['cmd.run_all'](
            '{0} {1}'.format(python, tmppath),
            runas=runas,
            cwd=cwd,
            env={'VIRTUAL_ENV': cwd}
        )
    finally:
        os.remove(tmppath)
