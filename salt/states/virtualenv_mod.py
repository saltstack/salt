# -*- coding: utf-8 -*-
'''
Setup of Python virtualenv sandboxes.

.. versionadded:: 0.17.0
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import os

# Import Salt libs
import salt.version
import salt.utils.functools
import salt.utils.platform
import salt.utils.versions
from salt.exceptions import CommandExecutionError, CommandNotFoundError

# Import 3rd-party libs
from salt.ext import six

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'virtualenv'


def __virtual__():
    return __virtualname__


def managed(name,
            venv_bin=None,
            requirements=None,
            system_site_packages=False,
            distribute=False,
            use_wheel=False,
            clear=False,
            python=None,
            extra_search_dir=None,
            never_download=None,
            prompt=None,
            user=None,
            no_chown=False,
            cwd=None,
            index_url=None,
            extra_index_url=None,
            pre_releases=False,
            no_deps=False,
            pip_download=None,
            pip_download_cache=None,
            pip_exists_action=None,
            pip_ignore_installed=False,
            proxy=None,
            use_vt=False,
            env_vars=None,
            no_use_wheel=False,
            pip_upgrade=False,
            pip_pkgs=None,
            pip_no_cache_dir=False,
            pip_cache_dir=None,
            process_dependency_links=False):
    '''
    Create a virtualenv and optionally manage it with pip

    name
        Path to the virtualenv.

    venv_bin: virtualenv
        The name (and optionally path) of the virtualenv command. This can also
        be set globally in the minion config file as ``virtualenv.venv_bin``.

    requirements: None
        Path to a pip requirements file. If the path begins with ``salt://``
        the file will be transferred from the master file server.

    use_wheel: False
        Prefer wheel archives (requires pip >= 1.4).

    python : None
        Python executable used to build the virtualenv

    user: None
        The user under which to run virtualenv and pip.

    no_chown: False
        When user is given, do not attempt to copy and chown a requirements file
        (needed if the requirements file refers to other files via relative
        paths, as the copy-and-chown procedure does not account for such files)

    cwd: None
        Path to the working directory where `pip install` is executed.

    no_deps: False
        Pass `--no-deps` to `pip install`.

    pip_exists_action: None
        Default action of pip when a path already exists: (s)witch, (i)gnore,
        (w)ipe, (b)ackup.

    proxy: None
        Proxy address which is passed to `pip install`.

    env_vars: None
        Set environment variables that some builds will depend on. For example,
        a Python C-module may have a Makefile that needs INCLUDE_PATH set to
        pick up a header file while compiling.

    no_use_wheel: False
        Force to not use wheel archives (requires pip>=1.4)

    pip_upgrade: False
        Pass `--upgrade` to `pip install`.

    pip_pkgs: None
        As an alternative to `requirements`, pass a list of pip packages that
        should be installed.

    process_dependency_links: False
        Run pip install with the --process_dependency_links flag.

        .. versionadded:: 2017.7.0

    Also accepts any kwargs that the virtualenv module will. However, some
    kwargs, such as the ``pip`` option, require ``- distribute: True``.

    .. code-block:: yaml

        /var/www/myvirtualenv.com:
          virtualenv.managed:
            - system_site_packages: False
            - requirements: salt://REQUIREMENTS.txt
            - env_vars:
                PATH_VAR: '/usr/local/bin/'
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    if 'virtualenv.create' not in __salt__:
        ret['result'] = False
        ret['comment'] = 'Virtualenv was not detected on this system'
        return ret

    if salt.utils.platform.is_windows():
        venv_py = os.path.join(name, 'Scripts', 'python.exe')
    else:
        venv_py = os.path.join(name, 'bin', 'python')
    venv_exists = os.path.exists(venv_py)

    # Bail out early if the specified requirements file can't be found
    if requirements and requirements.startswith('salt://'):
        cached_requirements = __salt__['cp.is_cached'](requirements, __env__)
        if not cached_requirements:
            # It's not cached, let's cache it.
            cached_requirements = __salt__['cp.cache_file'](
                requirements, __env__
            )
        # Check if the master version has changed.
        if cached_requirements and __salt__['cp.hash_file'](requirements, __env__) != \
                __salt__['cp.hash_file'](cached_requirements, __env__):
            cached_requirements = __salt__['cp.cache_file'](
                requirements, __env__
            )
        if not cached_requirements:
            ret.update({
                'result': False,
                'comment': 'pip requirements file \'{0}\' not found'.format(
                    requirements
                )
            })
            return ret
        requirements = cached_requirements

    # If it already exists, grab the version for posterity
    if venv_exists and clear:
        ret['changes']['cleared_packages'] = \
            __salt__['pip.freeze'](bin_env=name)
        ret['changes']['old'] = \
            __salt__['cmd.run_stderr']('{0} -V'.format(venv_py)).strip('\n')

    # Create (or clear) the virtualenv
    if __opts__['test']:
        if venv_exists and clear:
            ret['result'] = None
            ret['comment'] = 'Virtualenv {0} is set to be cleared'.format(name)
            return ret
        if venv_exists and not clear:
            #ret['result'] = None
            ret['comment'] = 'Virtualenv {0} is already created'.format(name)
            return ret
        ret['result'] = None
        ret['comment'] = 'Virtualenv {0} is set to be created'.format(name)
        return ret

    if not venv_exists or (venv_exists and clear):
        try:
            venv_ret = __salt__['virtualenv.create'](
                name,
                venv_bin=venv_bin,
                system_site_packages=system_site_packages,
                distribute=distribute,
                clear=clear,
                python=python,
                extra_search_dir=extra_search_dir,
                never_download=never_download,
                prompt=prompt,
                user=user,
                use_vt=use_vt,
            )
        except CommandNotFoundError as err:
            ret['result'] = False
            ret['comment'] = 'Failed to create virtualenv: {0}'.format(err)
            return ret

        if venv_ret['retcode'] != 0:
            ret['result'] = False
            ret['comment'] = venv_ret['stdout'] + venv_ret['stderr']
            return ret

        ret['result'] = True
        ret['changes']['new'] = __salt__['cmd.run_stderr'](
            '{0} -V'.format(venv_py)).strip('\n')

        if clear:
            ret['comment'] = 'Cleared existing virtualenv'
        else:
            ret['comment'] = 'Created new virtualenv'

    elif venv_exists:
        ret['comment'] = 'virtualenv exists'

    if use_wheel:
        min_version = '1.4'
        cur_version = __salt__['pip.version'](bin_env=name)
        if not salt.utils.versions.compare(ver1=cur_version, oper='>=',
                                           ver2=min_version):
            ret['result'] = False
            ret['comment'] = ('The \'use_wheel\' option is only supported in '
                              'pip {0} and newer. The version of pip detected '
                              'was {1}.').format(min_version, cur_version)
            return ret

    if no_use_wheel:
        min_version = '1.4'
        cur_version = __salt__['pip.version'](bin_env=name)
        if not salt.utils.versions.compare(ver1=cur_version, oper='>=',
                                           ver2=min_version):
            ret['result'] = False
            ret['comment'] = ('The \'no_use_wheel\' option is only supported '
                              'in pip {0} and newer. The version of pip '
                              'detected was {1}.').format(min_version,
                                                          cur_version)
            return ret

    # Populate the venv via a requirements file
    if requirements or pip_pkgs:
        try:
            before = set(__salt__['pip.freeze'](bin_env=name, user=user, use_vt=use_vt))
        except CommandExecutionError as exc:
            ret['result'] = False
            ret['comment'] = exc.strerror
            return ret

        if requirements:

            if isinstance(requirements, six.string_types):
                req_canary = requirements.split(',')[0]
            elif isinstance(requirements, list):
                req_canary = requirements[0]
            else:
                raise TypeError(
                    'pip requirements must be either a string or a list'
                )

            if req_canary != os.path.abspath(req_canary):
                cwd = os.path.dirname(os.path.abspath(req_canary))

        pip_ret = __salt__['pip.install'](
            pkgs=pip_pkgs,
            requirements=requirements,
            process_dependency_links=process_dependency_links,
            bin_env=name,
            use_wheel=use_wheel,
            no_use_wheel=no_use_wheel,
            user=user,
            cwd=cwd,
            index_url=index_url,
            extra_index_url=extra_index_url,
            download=pip_download,
            download_cache=pip_download_cache,
            no_chown=no_chown,
            pre_releases=pre_releases,
            exists_action=pip_exists_action,
            ignore_installed=pip_ignore_installed,
            upgrade=pip_upgrade,
            no_deps=no_deps,
            proxy=proxy,
            use_vt=use_vt,
            env_vars=env_vars,
            no_cache_dir=pip_no_cache_dir,
            cache_dir=pip_cache_dir
        )
        ret['result'] &= pip_ret['retcode'] == 0
        if pip_ret['retcode'] > 0:
            ret['comment'] = '{0}\n{1}\n{2}'.format(ret['comment'],
                                                    pip_ret['stdout'],
                                                    pip_ret['stderr'])

        after = set(__salt__['pip.freeze'](bin_env=name))

        new = list(after - before)
        old = list(before - after)

        if new or old:
            ret['changes']['packages'] = {
                'new': new if new else '',
                'old': old if old else ''}
    return ret

manage = salt.utils.functools.alias_function(managed, 'manage')
