# -*- coding: utf-8 -*-
'''
Create virtualenv environments.

.. versionadded:: 0.17.0
'''
from __future__ import absolute_import

# Import python libs
import glob
import shutil
import logging
import os
import os.path

# Import salt libs
import salt.utils
import salt.exceptions
from salt.ext.six import string_types

KNOWN_BINARY_NAMES = frozenset(
    ['virtualenv',
     'virtualenv2',
     'virtualenv-2.6',
     'virtualenv-2.7'
     ]
)

log = logging.getLogger(__name__)

__opts__ = {
    'venv_bin': salt.utils.which_bin(KNOWN_BINARY_NAMES) or 'virtualenv'
}

__pillar__ = {}

# Define the module's virtual name
__virtualname__ = 'virtualenv'


def __virtual__():
    return __virtualname__


def create(path,
           venv_bin=None,
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
           user=None,
           use_vt=False,
           saltenv='base'):
    '''
    Create a virtualenv

    path
        The path to create the virtualenv
    venv_bin : None (default 'virtualenv')
        The name (and optionally path) of the virtualenv command. This can also
        be set globally in the minion config file as ``virtualenv.venv_bin``.
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
    user : None
        Set ownership for the virtualenv
    runas : None
        Set ownership for the virtualenv

    use_vt : False
        Use VT terminal emulation (see output while installing)

        .. versionadded:: 2015.5.0

    saltenv : 'base'
        Specify a different environment. The default environment is ``base``.

        .. versionadded:: 2014.1.0

    .. note::
        The ``runas`` argument is deprecated as of 2014.1.0. ``user`` should be
        used instead.

    CLI Example:

    .. code-block:: bash

        salt '*' virtualenv.create /path/to/new/virtualenv
    '''
    if venv_bin is None:
        venv_bin = __opts__.get('venv_bin') or __pillar__.get('venv_bin')
    # raise CommandNotFoundError if venv_bin is missing
    salt.utils.check_or_die(venv_bin)

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
            ret = __salt__['cmd.run_all'](
                    version_cmd, runas=user, python_shell=False
                )
            if ret['retcode'] > 0 or not ret['stdout'].strip():
                raise salt.exceptions.CommandExecutionError(
                    'Unable to get the virtualenv version output using {0!r}. '
                    'Returned data: {1!r}'.format(version_cmd, ret)
                )
            virtualenv_version_info = tuple(
                [int(i) for i in
                 ret['stdout'].strip().split('rc')[0].split('.')]
            )

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
            if not salt.utils.which(python):
                raise salt.exceptions.CommandExecutionError(
                    'Cannot find requested python ({0}).'.format(python)
                )
            cmd.append('--python={0}'.format(python))
        if extra_search_dir is not None:
            if isinstance(extra_search_dir, string_types) and \
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
        if python is not None and python.strip() != '':
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
    ret = __salt__['cmd.run_all'](cmd, runas=user, python_shell=False)
    if ret['retcode'] != 0:
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
            path, venv_python, user, saltenv=saltenv, use_vt=use_vt
        )

        # clear up the distribute archive which gets downloaded
        for fpath in glob.glob(os.path.join(path, 'distribute-*.tar.gz*')):
            os.unlink(fpath)

    if ret['retcode'] != 0:
        # Something went wrong. Let's bail out now!
        return ret

    # Install pip
    if pip and not os.path.exists(venv_pip):
        _ret = _install_script(
            'https://raw.githubusercontent.com/pypa/pip/master/contrib/get-pip.py',
            path, venv_python, user, saltenv=saltenv, use_vt=use_vt
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

    venv
        Path to the virtualenv.

    CLI Example:

    .. code-block:: bash

        salt '*' virtualenv.get_site_packages /path/to/my/venv
    '''
    bin_path = os.path.join(venv, 'bin/python')

    if not os.path.exists(bin_path):
        raise salt.exceptions.CommandExecutionError(
            "Path does not appear to be a virtualenv: '{0}'".format(bin_path))

    ret = __salt__['cmd.exec_code_all'](bin_path, 'from distutils import sysconfig; print sysconfig.get_python_lib()')

    if ret['retcode'] != 0:
        raise salt.exceptions.CommandExecutionError('{stdout}\n{stderr}'.format(**ret))

    return ret['stdout']


def get_resource_path(venv, package_or_requirement, resource_name):
    '''
    Returns the path to a resource of a package or a distribution inside a virtualenv

    .. versionadded:: 2015.5.0

    venv
        Path to the virtualenv.
    package_or_requirement
        Name of the package where the resource resides in.
    resource_name
        Name of the resource of which the path is to be returned.

    CLI Example:

    .. code-block:: bash

        salt '*' virtualenv.get_resource_path /path/to/my/venv my_package my/resource.xml
    '''
    if not salt.utils.verify.safe_py_code(package_or_requirement):
        raise salt.exceptions.CommandExecutionError
    if not salt.utils.verify.safe_py_code(resource_name):
        raise salt.exceptions.CommandExecutionError
    bin_path = os.path.join(venv, 'bin/python')

    if not os.path.exists(bin_path):
        raise salt.exceptions.CommandExecutionError("Path does not appear to be a virtualenv: '{0}'".format(bin_path))

    ret = __salt__['cmd.exec_code_all'](bin_path, "import pkg_resources; print pkg_resources.resource_filename('{0}', '{1}')".format(package_or_requirement, resource_name))

    if ret['retcode'] != 0:
        raise salt.exceptions.CommandExecutionError('{stdout}\n{stderr}'.format(**ret))

    return ret['stdout']


def get_resource_content(venv, package_or_requirement, resource_name):
    '''
    Returns the content of a resource of a package or a distribution inside a virtualenv

    .. versionadded:: 2015.5.0

    venv
        Path to the virtualenv.
    package_or_requirement
        Name of the package where the resource resides in.
    resource_name
        Name of the resource of which the content is to be returned.


    CLI Example:

    .. code-block:: bash

        salt '*' virtualenv.get_resource_content /path/to/my/venv my_package my/resource.xml
    '''
    if not salt.utils.verify.safe_py_code(package_or_requirement):
        raise salt.exceptions.CommandExecutionError
    if not salt.utils.verify.safe_py_code(resource_name):
        raise salt.exceptions.CommandExecutionError
    bin_path = os.path.join(venv, 'bin/python')

    if not os.path.exists(bin_path):
        raise salt.exceptions.CommandExecutionError("Path does not appear to be a virtualenv: '{0}'".format(bin_path))

    ret = __salt__['cmd.exec_code_all'](bin_path, "import pkg_resources; print pkg_resources.resource_string('{0}', '{1}')".format(package_or_requirement, resource_name))

    if ret['retcode'] != 0:
        raise salt.exceptions.CommandExecutionError('{stdout}\n{stderr}'.format(**ret))

    return ret['stdout']


def _install_script(source, cwd, python, user, saltenv='base', use_vt=False):
    if not salt.utils.is_windows():
        tmppath = salt.utils.mkstemp(dir=cwd)
    else:
        tmppath = __salt__['cp.cache_file'](source, saltenv)

    if not salt.utils.is_windows():
        fn_ = __salt__['cp.cache_file'](source, saltenv)
        shutil.copyfile(fn_, tmppath)
        os.chmod(tmppath, 0o500)
        os.chown(tmppath, __salt__['file.user_to_uid'](user), -1)
    try:
        return __salt__['cmd.run_all'](
            '{0} {1}'.format(python, tmppath),
            runas=user,
            cwd=cwd,
            env={'VIRTUAL_ENV': cwd},
            use_vt=use_vt,
            python_shell=False,
        )
    finally:
        os.remove(tmppath)
