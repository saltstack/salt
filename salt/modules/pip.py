# -*- coding: utf-8 -*-
'''
Install Python packages with pip to either the system or a virtualenv
'''

# Import python libs
import os
import re
import logging
import shutil

# Import salt libs
import salt.utils
from salt._compat import string_types
from salt.exceptions import CommandExecutionError, CommandNotFoundError

# It would be cool if we could use __virtual__() in this module, though, since
# pip can be installed on a virtualenv anywhere on the filesystem, there's no
# definite way to tell if pip is installed on not.

logger = logging.getLogger(__name__)  # pylint: disable=C0103

# Don't shadow built-in's.
__func_alias__ = {
    'list_': 'list'
}

VALID_PROTOS = ['http', 'https', 'ftp', 'file']


def _get_pip_bin(bin_env):
    '''
    Return the pip command to call, either from a virtualenv, an argument
    passed in, or from the global modules options
    '''
    if not bin_env:
        which_result = __salt__['cmd.which_bin'](['pip2', 'pip', 'pip-python'])
        if which_result is None:
            raise CommandNotFoundError('Could not find a `pip` binary')
        return which_result

    # try to get pip bin from env
    if os.path.isdir(bin_env):
        if salt.utils.is_windows():
            pip_bin = os.path.join(bin_env, 'Scripts', 'pip.exe')
        else:
            pip_bin = os.path.join(bin_env, 'bin', 'pip')
        if os.path.isfile(pip_bin):
            return pip_bin
        raise CommandNotFoundError('Could not find a `pip` binary')

    return bin_env


def _get_cached_requirements(requirements, saltenv):
    '''Get the location of a cached requirements file; caching if necessary.'''
    cached_requirements = __salt__['cp.is_cached'](
        requirements, saltenv
    )
    if not cached_requirements:
        # It's not cached, let's cache it.
        cached_requirements = __salt__['cp.cache_file'](
            requirements, saltenv
        )
    # Check if the master version has changed.
    if __salt__['cp.hash_file'](requirements, saltenv) != \
            __salt__['cp.hash_file'](cached_requirements, saltenv):
        cached_requirements = __salt__['cp.cache_file'](
            requirements, saltenv
        )

    return cached_requirements


def _get_env_activate(bin_env):
    '''
    Return the path to the activate binary
    '''
    if not bin_env:
        raise CommandNotFoundError('Could not find a `activate` binary')

    if os.path.isdir(bin_env):
        if salt.utils.is_windows():
            activate_bin = os.path.join(bin_env, 'Scripts', 'activate.bat')
        else:
            activate_bin = os.path.join(bin_env, 'bin', 'activate')
        if os.path.isfile(activate_bin):
            return activate_bin
    raise CommandNotFoundError('Could not find a `activate` binary')


def install(pkgs=None,  # pylint: disable=R0912,R0913,R0914
            requirements=None,
            env=None,
            bin_env=None,
            use_wheel=False,
            no_use_wheel=False,
            log=None,
            proxy=None,
            timeout=None,
            editable=None,
            find_links=None,
            index_url=None,
            extra_index_url=None,
            no_index=False,
            mirrors=None,
            build=None,
            target=None,
            download=None,
            download_cache=None,
            source=None,
            upgrade=False,
            force_reinstall=False,
            ignore_installed=False,
            exists_action=None,
            no_deps=False,
            no_install=False,
            no_download=False,
            global_options=None,
            install_options=None,
            user=None,
            runas=None,
            no_chown=False,
            cwd=None,
            activate=False,
            pre_releases=False,
            cert=None,
            allow_all_external=False,
            allow_external=None,
            allow_unverified=None,
            process_dependency_links=False,
            __env__=None,
            saltenv='base'):
    '''
    Install packages with pip

    Install packages individually or from a pip requirements file. Install
    packages globally or to a virtualenv.

    pkgs
        Comma separated list of packages to install
    requirements
        Path to requirements
    bin_env
        Path to pip bin or path to virtualenv. If doing a system install,
        and want to use a specific pip bin (pip-2.7, pip-2.6, etc..) just
        specify the pip bin you want.
        If installing into a virtualenv, just use the path to the virtualenv
        (/home/code/path/to/virtualenv/)
    env
        Deprecated, use bin_env now
    use_wheel
        Prefer wheel archives (requires pip>=1.4)
    no_use_wheel
        Force to not use wheel archives (requires pip>=1.4)
    log
        Log file where a complete (maximum verbosity) record will be kept
    proxy
        Specify a proxy in the form
        user:passwd@proxy.server:port. Note that the
        user:password@ is optional and required only if you
        are behind an authenticated proxy.  If you provide
        user@proxy.server:port then you will be prompted for a
        password.
    timeout
        Set the socket timeout (default 15 seconds)
    editable
        install something editable (i.e.
        git+https://github.com/worldcompany/djangoembed.git#egg=djangoembed)
    find_links
        URL to look for packages at
    index_url
        Base URL of Python Package Index
    extra_index_url
        Extra URLs of package indexes to use in addition to ``index_url``
    no_index
        Ignore package index
    mirrors
        Specific mirror URL(s) to query (automatically adds --use-mirrors)
    build
        Unpack packages into ``build`` dir
    target
        Install packages into ``target`` dir
    download
        Download packages into ``download`` instead of installing them
    download_cache
        Cache downloaded packages in ``download_cache`` dir
    source
        Check out ``editable`` packages into ``source`` dir
    upgrade
        Upgrade all packages to the newest available version
    force_reinstall
        When upgrading, reinstall all packages even if they are already
        up-to-date.
    ignore_installed
        Ignore the installed packages (reinstalling instead)
    exists_action
        Default action when a path already exists: (s)witch, (i)gnore, (w)ipe,
        (b)ackup
    no_deps
        Ignore package dependencies
    no_install
        Download and unpack all packages, but don't actually install them
    no_download
        Don't download any packages, just install the ones
        already downloaded (completes an install run with
        --no-install)
    install_options
        Extra arguments to be supplied to the setup.py install
        command (use like --install-option="--install-
        scripts=/usr/local/bin").  Use multiple --install-
        option options to pass multiple options to setup.py
        install.  If you are using an option with a directory
        path, be sure to use absolute path.
    global_options
        Extra global options to be supplied to the setup.py call before the
        install command.
    user
        The user under which to run pip

    .. note::
        The ``runas`` argument is deprecated as of 0.16.2. ``user`` should be
        used instead.

    no_chown
        When user is given, do not attempt to copy and chown
        a requirements file
    cwd
        Current working directory to run pip from
    activate
        Activates the virtual environment, if given via bin_env,
        before running install.
    pre_releases
        Include pre-releases in the available versions
    cert
        Provide a path to an alternate CA bundle
    allow_all_external
        Allow the installation of all externally hosted files
    allow_external
        Allow the installation of externally hosted files (comma separated list)
    allow_unverified
        Allow the installation of insecure and unverifiable files (comma separated list)
    process_dependency_links
        Enable the processing of dependency links

    CLI Example:

    .. code-block:: bash

        salt '*' pip.install <package name>,<package2 name>
        salt '*' pip.install requirements=/path/to/requirements.txt
        salt '*' pip.install <package name> bin_env=/path/to/virtualenv
        salt '*' pip.install <package name> bin_env=/path/to/pip_bin

    Complicated CLI example::

        salt '*' pip.install markdown,django \
                editable=git+https://github.com/worldcompany/djangoembed.git#egg=djangoembed upgrade=True no_deps=True

    '''
    # Switching from using `pip_bin` and `env` to just `bin_env`
    # cause using an env and a pip bin that's not in the env could
    # be problematic.
    # Still using the `env` variable, for backwards compatibility's sake
    # but going fwd you should specify either a pip bin or an env with
    # the `bin_env` argument and we'll take care of the rest.
    if env and not bin_env:
        salt.utils.warn_until(
                'Boron',
                'Passing \'env\' to the pip module is deprecated. Use bin_env instead. '
                'This functionality will be removed in Salt Boron.'
        )
        bin_env = env

    if isinstance(__env__, string_types):
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'__env__\'. This functionality will be removed in Salt '
            'Boron.'
        )
        # Backwards compatibility
        saltenv = __env__

    if runas is not None:
        # The user is using a deprecated argument, warn!
        salt.utils.warn_until(
            'Lithium',
            'The \'runas\' argument to pip.install is deprecated, and will be '
            'removed in Salt {version}. Please use \'user\' instead.'
        )

    # "There can only be one"
    if runas is not None and user:
        raise CommandExecutionError(
            'The \'runas\' and \'user\' arguments are mutually exclusive. '
            'Please use \'user\' as \'runas\' is being deprecated.'
        )

    # Support deprecated 'runas' arg
    elif runas is not None and not user:
        user = str(runas)

    cmd = [_get_pip_bin(bin_env), 'install']

    if activate and bin_env:
        if not salt.utils.is_windows():
            cmd = ['.', _get_env_activate(bin_env), '&&'] + cmd

    cleanup_requirements = []
    if requirements is not None:
        if isinstance(requirements, string_types):
            requirements = [r.strip() for r in requirements.split(',')]

        for requirement in requirements:
            treq = None
            if requirement.startswith('salt://'):
                cached_requirements = _get_cached_requirements(
                    requirement, saltenv
                )
                if not cached_requirements:
                    return {
                        'result': False,
                        'comment': (
                            'pip requirements file {0!r} not found'.format(
                                requirement
                            )
                        )
                    }
                requirement = cached_requirements

            if user and not no_chown:
                # Need to make a temporary copy since the user will, most
                # likely, not have the right permissions to read the file
                treq = salt.utils.mkstemp()
                shutil.copyfile(requirement, treq)
                logger.debug(
                    'Changing ownership of requirements file {0!r} to '
                    'user {1!r}'.format(treq, user)
                )
                __salt__['file.chown'](treq, user, None)
                cleanup_requirements.append(treq)
            cmd.append('--requirement={0!r}'.format(treq or requirement))

    if use_wheel:
        min_version = '1.4'
        cur_version = __salt__['pip.version'](bin_env)
        if not salt.utils.compare_versions(ver1=cur_version, oper='>=',
                                           ver2=min_version):
            log.error(
                ('The --use-wheel option is only supported in pip {0} and '
                 'newer. The version of pip detected is {1}. This option '
                 'will be ignored.'.format(min_version, cur_version))
            )
        else:
            cmd.append('--use-wheel')

    if no_use_wheel:
        min_version = '1.4'
        cur_version = __salt__['pip.version'](bin_env)
        if not salt.utils.compare_versions(ver1=cur_version, oper='>=',
                                           ver2=min_version):
            log.error(
                ('The --no-use-wheel option is only supported in pip {0} and '
                 'newer. The version of pip detected is {1}. This option '
                 'will be ignored.'.format(min_version, cur_version))
            )
        else:
            cmd.append('--no-use-wheel')

    if log:
        try:
            # TODO make this check if writeable
            os.path.exists(log)
        except IOError:
            raise IOError('{0!r} is not writeable'.format(log))

        cmd.append('--log={0}'.format(log))

    if proxy:
        cmd.append('--proxy={0!r}'.format(proxy))

    if timeout:
        try:
            int(timeout)
        except ValueError:
            raise ValueError(
                '{0!r} is not a valid integer base 10.'.format(timeout)
            )
        cmd.append('--timeout={0}'.format(timeout))

    if find_links:
        if isinstance(find_links, string_types):
            find_links = [l.strip() for l in find_links.split(',')]

        for link in find_links:
            if not (salt.utils.valid_url(link, VALID_PROTOS) or os.path.exists(link)):
                raise CommandExecutionError(
                    '{0!r} must be a valid URL or path'.format(link)
                )
            cmd.append('--find-links={0}'.format(link))

    if no_index and (index_url or extra_index_url):
        raise CommandExecutionError(
            '\'no_index\' and (\'index_url\' or \'extra_index_url\') are '
            'mutually exclusive.'
        )

    if index_url:
        if not salt.utils.valid_url(index_url, VALID_PROTOS):
            raise CommandExecutionError(
                '{0!r} must be a valid URL'.format(index_url)
            )
        cmd.append('--index-url={0!r}'.format(index_url))

    if extra_index_url:
        if not salt.utils.valid_url(extra_index_url, VALID_PROTOS):
            raise CommandExecutionError(
                '{0!r} must be a valid URL'.format(extra_index_url)
            )
        cmd.append('--extra-index-url={0!r}'.format(extra_index_url))

    if no_index:
        cmd.append('--no-index')

    if mirrors:
        if isinstance(mirrors, string_types):
            mirrors = [m.strip() for m in mirrors.split(',')]

        cmd.append('--use-mirrors')
        for mirror in mirrors:
            if not mirror.startswith('http://'):
                raise CommandExecutionError(
                    '{0!r} must be a valid URL'.format(mirror)
                )
            cmd.append('--mirrors={0}'.format(mirror))

    if build:
        cmd.append('--build={0}'.format(build))

    if target:
        cmd.append('--target={0}'.format(target))

    if download:
        cmd.append('--download={0}'.format(download))

    if download_cache:
        cmd.append('--download-cache={0}'.format(download_cache))

    if source:
        cmd.append('--source={0}'.format(source))

    if upgrade:
        cmd.append('--upgrade')

    if force_reinstall:
        cmd.append('--force-reinstall')

    if ignore_installed:
        cmd.append('--ignore-installed')

    if exists_action:
        if exists_action.lower() not in ('s', 'i', 'w', 'b'):
            raise CommandExecutionError(
                'The `exists_action`(`--exists-action`) pip option only '
                'allows one of (s, i, w, b) to be passed. The {0!r} value '
                'is not valid.'.format(exists_action)
            )
        cmd.append('--exists-action={0}'.format(exists_action))

    if no_deps:
        cmd.append('--no-deps')

    if no_install:
        cmd.append('--no-install')

    if no_download:
        cmd.append('--no-download')

    if pre_releases:
        # Check the locally installed pip version
        pip_version_cmd = '{0} --version'.format(_get_pip_bin(bin_env))
        output = __salt__['cmd.run_all'](pip_version_cmd).get('stdout', '')
        pip_version = output.split()[1]

        # From pip v1.4 the --pre flag is available
        if salt.utils.compare_versions(ver1=pip_version, oper='>=', ver2='1.4'):
            cmd.append('--pre')

    if cert:
        cmd.append('--cert={0}'.format(cert))

    if global_options:
        if isinstance(global_options, string_types):
            global_options = [go.strip() for go in global_options.split(',')]

        for opt in global_options:
            cmd.append('--global-option={0!r}'.format(opt))

    if install_options:
        if isinstance(install_options, string_types):
            install_options = [io.strip() for io in install_options.split(',')]

        for opt in install_options:
            cmd.append('--install-option={0!r}'.format(opt))

    if pkgs:
        if isinstance(pkgs, string_types):
            pkgs = [p.strip() for p in pkgs.split(',')]

        # It's possible we replaced version-range commas with semicolons so
        # they would survive the previous line (in the pip.installed state).
        # Put the commas back in while making sure the names are contained in
        # quotes, this allows for proper version spec passing salt>=0.17.0
        cmd.extend(
            ['{0!r}'.format(p.replace(';', ',')) for p in pkgs]
        )

    if editable:
        egg_match = re.compile(r'(?:#|#.*?&)egg=([^&]*)')
        if isinstance(editable, string_types):
            editable = [e.strip() for e in editable.split(',')]

        for entry in editable:
            # Is the editable local?
            if not (entry == '.' or entry.startswith(('file://', '/'))):
                match = egg_match.search(entry)

                if not match or not match.group(1):
                    # Missing #egg=theEggName
                    raise CommandExecutionError(
                        'You must specify an egg for this editable'
                    )
            cmd.append('--editable={0}'.format(entry))

    if allow_all_external:
        cmd.append('--allow-all-external')

    if allow_external:
        if isinstance(allow_external, string_types):
            allow_external = [p.strip() for p in allow_external.split(',')]

        for pkg in allow_external:
            cmd.append('--allow-external {0}'.format(pkg))

    if allow_unverified:
        if isinstance(allow_unverified, string_types):
            allow_unverified = [p.strip() for p in allow_unverified.split(',')]

        for pkg in allow_unverified:
            cmd.append('--allow-unverified {0}'.format(pkg))

    if process_dependency_links:
        cmd.append('--process-dependency-links')

    try:
        cmd_kwargs = dict(runas=user, cwd=cwd, saltenv=saltenv)
        if bin_env and os.path.isdir(bin_env):
            cmd_kwargs['env'] = {'VIRTUAL_ENV': bin_env}
        return __salt__['cmd.run_all'](' '.join(cmd), **cmd_kwargs)
    finally:
        for requirement in cleanup_requirements:
            try:
                os.remove(requirement)
            except OSError:
                pass


def uninstall(pkgs=None,
              requirements=None,
              bin_env=None,
              log=None,
              proxy=None,
              timeout=None,
              user=None,
              runas=None,
              no_chown=False,
              cwd=None,
              __env__=None,
              saltenv='base'):
    '''
    Uninstall packages with pip

    Uninstall packages individually or from a pip requirements file. Uninstall
    packages globally or from a virtualenv.

    pkgs
        comma separated list of packages to install
    requirements
        path to requirements.
    bin_env
        path to pip bin or path to virtualenv. If doing an uninstall from
        the system python and want to use a specific pip bin (pip-2.7,
        pip-2.6, etc..) just specify the pip bin you want.
        If uninstalling from a virtualenv, just use the path to the virtualenv
        (/home/code/path/to/virtualenv/)
    log
        Log file where a complete (maximum verbosity) record will be kept
    proxy
        Specify a proxy in the form
        user:passwd@proxy.server:port. Note that the
        user:password@ is optional and required only if you
        are behind an authenticated proxy.  If you provide
        user@proxy.server:port then you will be prompted for a
        password.
    timeout
        Set the socket timeout (default 15 seconds)
    user
        The user under which to run pip

    .. note::
        The ``runas`` argument is deprecated as of 0.16.2. ``user`` should be
        used instead.

    no_chown
        When user is given, do not attempt to copy and chown
        a requirements file
    cwd
        Current working directory to run pip from

    CLI Example:

    .. code-block:: bash

        salt '*' pip.uninstall <package name>,<package2 name>
        salt '*' pip.uninstall requirements=/path/to/requirements.txt
        salt '*' pip.uninstall <package name> bin_env=/path/to/virtualenv
        salt '*' pip.uninstall <package name> bin_env=/path/to/pip_bin

    '''
    cmd = [_get_pip_bin(bin_env), 'uninstall', '-y']

    if isinstance(__env__, string_types):
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'__env__\'. This functionality will be removed in Salt '
            'Boron.'
        )
        # Backwards compatibility
        saltenv = __env__

    if runas is not None:
        # The user is using a deprecated argument, warn!
        salt.utils.warn_until(
            'Lithium',
            'The \'runas\' argument to pip.install is deprecated, and will be '
            'removed in Salt {version}. Please use \'user\' instead.'
        )

    # "There can only be one"
    if runas is not None and user:
        raise CommandExecutionError(
            'The \'runas\' and \'user\' arguments are mutually exclusive. '
            'Please use \'user\' as \'runas\' is being deprecated.'
        )

    # Support deprecated 'runas' arg
    elif runas is not None and not user:
        user = str(runas)

    cleanup_requirements = []
    if requirements is not None:
        if isinstance(requirements, string_types):
            requirements = [r.strip() for r in requirements.split(',')]

        for requirement in requirements:
            treq = None
            if requirement.startswith('salt://'):
                cached_requirements = _get_cached_requirements(
                    requirement, saltenv
                )
                if not cached_requirements:
                    return {
                        'result': False,
                        'comment': (
                            'pip requirements file {0!r} not found'.format(
                                requirement
                            )
                        )
                    }
                requirement = cached_requirements

            if user and not no_chown:
                # Need to make a temporary copy since the user will, most
                # likely, not have the right permissions to read the file
                treq = salt.utils.mkstemp()
                shutil.copyfile(requirement, treq)
                logger.debug(
                    'Changing ownership of requirements file {0!r} to '
                    'user {1!r}'.format(treq, user)
                )
                __salt__['file.chown'](treq, user, None)
                cleanup_requirements.append(treq)
            cmd.append('--requirement={0!r}'.format(treq or requirement))

    if log:
        try:
            # TODO make this check if writeable
            os.path.exists(log)
        except IOError:
            raise IOError('{0!r} is not writeable'.format(log))

        cmd.append('--log={0}'.format(log))

    if proxy:
        cmd.append('--proxy={0!r}'.format(proxy))

    if timeout:
        try:
            int(timeout)
        except ValueError:
            raise ValueError(
                '{0!r} is not a valid integer base 10.'.format(timeout)
            )
        cmd.append('--timeout={0}'.format(timeout))

    if pkgs:
        if isinstance(pkgs, string_types):
            pkgs = [p.strip() for p in pkgs.split(',')]
        if requirements:
            with salt.utils.fopen(requirement) as rq_:
                for req in rq_:
                    try:
                        req_pkg, _ = req.split('==')
                        if req_pkg in pkgs:
                            pkgs.remove(req_pkg)
                    except ValueError:
                        pass
        cmd.extend(pkgs)

    cmd_kwargs = dict(runas=user, cwd=cwd, saltenv=saltenv)
    if bin_env and os.path.isdir(bin_env):
        cmd_kwargs['env'] = {'VIRTUAL_ENV': bin_env}

    try:
        return __salt__['cmd.run_all'](' '.join(cmd), **cmd_kwargs)
    finally:
        for requirement in cleanup_requirements:
            try:
                os.remove(requirement)
            except OSError:
                pass


def freeze(bin_env=None,
           user=None,
           runas=None,
           cwd=None):
    '''
    Return a list of installed packages either globally or in the specified
    virtualenv

    bin_env
        path to pip bin or path to virtualenv. If doing an uninstall from
        the system python and want to use a specific pip bin (pip-2.7,
        pip-2.6, etc..) just specify the pip bin you want.
        If uninstalling from a virtualenv, just use the path to the virtualenv
        (/home/code/path/to/virtualenv/)
    user
        The user under which to run pip

    .. note::
        The ``runas`` argument is deprecated as of 0.16.2. ``user`` should be
        used instead.

    cwd
        Current working directory to run pip from

    CLI Example:

    .. code-block:: bash

        salt '*' pip.freeze /home/code/path/to/virtualenv/
    '''
    if runas is not None:
        # The user is using a deprecated argument, warn!
        salt.utils.warn_until(
            'Lithium',
            'The \'runas\' argument to pip.install is deprecated, and will be '
            'removed in Salt {version}. Please use \'user\' instead.'
        )

    # "There can only be one"
    if runas is not None and user:
        raise CommandExecutionError(
            'The \'runas\' and \'user\' arguments are mutually exclusive. '
            'Please use \'user\' as \'runas\' is being deprecated.'
        )

    # Support deprecated 'runas' arg
    elif runas is not None and not user:
        user = str(runas)

    cmd = [_get_pip_bin(bin_env), 'freeze']
    cmd_kwargs = dict(runas=user, cwd=cwd)
    if bin_env and os.path.isdir(bin_env):
        cmd_kwargs['env'] = {'VIRTUAL_ENV': bin_env}
    result = __salt__['cmd.run_all'](' '.join(cmd), **cmd_kwargs)

    if result['retcode'] > 0:
        raise CommandExecutionError(result['stderr'])

    return result['stdout'].splitlines()


def list_(prefix=None,
          bin_env=None,
          user=None,
          runas=None,
          cwd=None):
    '''
    Filter list of installed apps from ``freeze`` and check to see if
    ``prefix`` exists in the list of packages installed.

    CLI Example:

    .. code-block:: bash

        salt '*' pip.list salt
    '''
    packages = {}

    pip_bin = _get_pip_bin(bin_env)
    pip_version_cmd = [pip_bin, '--version']
    cmd = [pip_bin, 'freeze']

    if runas is not None:
        # The user is using a deprecated argument, warn!
        salt.utils.warn_until(
            'Lithium',
            'The \'runas\' argument to pip.install is deprecated, and will be '
            'removed in Salt {version}. Please use \'user\' instead.'
        )

    # "There can only be one"
    if runas is not None and user:
        raise CommandExecutionError(
            'The \'runas\' and \'user\' arguments are mutually exclusive. '
            'Please use \'user\' as \'runas\' is being deprecated.'
        )

    # Support deprecated 'runas' arg
    elif runas is not None and not user:
        user = str(runas)

    cmd_kwargs = dict(runas=user, cwd=cwd)
    if bin_env and os.path.isdir(bin_env):
        cmd_kwargs['env'] = {'VIRTUAL_ENV': bin_env}

    if not prefix or prefix in ('p', 'pi', 'pip'):
        pip_version_result = __salt__['cmd.run_all'](' '.join(pip_version_cmd),
                                                     **cmd_kwargs)
        if pip_version_result['retcode'] > 0:
            raise CommandExecutionError(pip_version_result['stderr'])
        packages['pip'] = pip_version_result['stdout'].split()[1]

    result = __salt__['cmd.run_all'](' '.join(cmd), **cmd_kwargs)
    if result['retcode'] > 0:
        raise CommandExecutionError(result['stderr'])

    for line in result['stdout'].splitlines():
        if line.startswith('-f') or line.startswith('#'):
            # ignore -f line as it contains --find-links directory
            # ignore comment lines
            continue
        elif line.startswith('-e'):
            line = line.split('-e ')[1]
            version_, name = line.split('#egg=')
        elif len(line.split('==')) >= 2:
            name = line.split('==')[0]
            version_ = line.split('==')[1]
        else:
            logger.error('Can\'t parse line {0!r}'.format(line))
            continue

        if prefix:
            if name.lower().startswith(prefix.lower()):
                packages[name] = version_
        else:
            packages[name] = version_
    return packages


def version(bin_env=None):
    '''
    .. versionadded:: 0.17.0

    Returns the version of pip. Use ``bin_env`` to specify the path to a
    virtualenv and get the version of pip in that virtualenv.

    If unable to detect the pip version, returns ``None``.

    CLI Example:

    .. code-block:: bash

        salt '*' pip.version
    '''
    output = __salt__['cmd.run']('{0} --version'.format(_get_pip_bin(bin_env)))
    try:
        return re.match(r'^pip (\S+)', output).group(1)
    except AttributeError:
        return None
