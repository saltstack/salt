# -*- coding: utf-8 -*-
r'''
Install Python packages with pip to either the system or a virtualenv

Windows Support
===============

.. versionadded:: 2014.7.4

Salt now uses a portable python. As a result the entire pip module is now
functional on the salt installation itself. You can pip install dependencies
for your custom modules. You can even upgrade salt itself using pip. For this
to work properly, you must specify the Current Working Directory (``cwd``) and
the Pip Binary (``bin_env``) salt should use.  The variable ``pip_bin`` can be
either a virtualenv path or the path to the pip binary itself.

For example, the following command will list all software installed using pip
to your current salt environment:

.. code-block:: bat

   salt <minion> pip.list cwd='C:\salt\bin\Scripts' bin_env='C:\salt\bin\Scripts\pip.exe'

Specifying the ``cwd`` and ``bin_env`` options ensures you're modifying the
salt environment. If these are omitted, it will default to the local
installation of python. If python is not installed locally it will fail saying
it couldn't find pip.

State File Support
------------------

This functionality works in states as well. If you need to pip install colorama
with a state, for example, the following will work:

.. code-block:: yaml

   install_colorama:
     pip.installed:
       - name: colorama
       - cwd: 'C:\salt\bin\scripts'
       - bin_env: 'C:\salt\bin\scripts\pip.exe'
       - upgrade: True

Upgrading Salt using Pip
------------------------

You can now update salt using pip to any version from the 2014.7 branch
forward. Previous version require recompiling some of the dependencies which is
painful in windows.

To do this you just use pip with git to update to the version you want and then
restart the service. Here is a sample state file that upgrades salt to the head
of the 2015.5 branch:

.. code-block:: yaml

   install_salt:
     pip.installed:
       - cwd: 'C:\salt\bin\scripts'
       - bin_env: 'C:\salt\bin\scripts\pip.exe'
       - editable: git+https://github.com/saltstack/salt@2015.5#egg=salt
       - upgrade: True

   restart_service:
     service.running:
       - name: salt-minion
       - enable: True
       - watch:
         - pip: install_salt

.. note::
   If you're having problems, you might try doubling the back slashes. For
   example, cwd: 'C:\\salt\\bin\\scripts'. Sometimes python thinks the single
   back slash is an escape character.

'''
from __future__ import absolute_import

# Import python libs
import os
import re
import shutil
import logging

# Import salt libs
import salt.utils
import tempfile
import salt.utils.locales
import salt.utils.url
from salt.ext.six import string_types, iteritems
from salt.exceptions import CommandExecutionError, CommandNotFoundError


logger = logging.getLogger(__name__)  # pylint: disable=C0103

# Don't shadow built-in's.
__func_alias__ = {
    'list_': 'list'
}

VALID_PROTOS = ['http', 'https', 'ftp', 'file']

rex_pip_chain_read = re.compile(r'-r\s(.*)\n?', re.MULTILINE)


def __virtual__():
    '''
    There is no way to verify that pip is installed without inspecting the
    entire filesystem.  If it's not installed in a conventional location, the
    user is required to provide the location of pip each time it is used.
    '''
    return 'pip'


def _get_pip_bin(bin_env):
    '''
    Locate the pip binary, either from `bin_env` as a virtualenv, as the
    executable itself, or from searching conventional filesystem locations
    '''
    if not bin_env:
        which_result = __salt__['cmd.which_bin'](['pip', 'pip2', 'pip3', 'pip-python'])
        if which_result is None:
            raise CommandNotFoundError('Could not find a `pip` binary')
        if salt.utils.is_windows():
            return which_result.encode('string-escape')
        return which_result

    # try to get pip bin from virtualenv, bin_env
    if os.path.isdir(bin_env):
        if salt.utils.is_windows():
            pip_bin = os.path.join(
                bin_env, 'Scripts', 'pip.exe').encode('string-escape')
        else:
            pip_bin = os.path.join(bin_env, 'bin', 'pip')
        if os.path.isfile(pip_bin):
            return pip_bin
        msg = 'Could not find a `pip` binary in virtualenv {0}'.format(bin_env)
        raise CommandNotFoundError(msg)
    # bin_env is the pip binary
    elif os.access(bin_env, os.X_OK):
        if os.path.isfile(bin_env) or os.path.islink(bin_env):
            return bin_env
    else:
        raise CommandNotFoundError('Could not find a `pip` binary')


def _get_cached_requirements(requirements, saltenv):
    '''
    Get the location of a cached requirements file; caching if necessary.
    '''

    req_file, senv = salt.utils.url.parse(requirements)
    if senv:
        saltenv = senv

    if req_file not in __salt__['cp.list_master'](saltenv):
        # Requirements file does not exist in the given saltenv.
        return False

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


def _find_req(link):

    logger.info('_find_req -- link = %s', str(link))

    with salt.utils.fopen(link) as fh_link:
        child_links = rex_pip_chain_read.findall(fh_link.read())

    base_path = os.path.dirname(link)
    child_links = [os.path.join(base_path, d) for d in child_links]

    return child_links


def _resolve_requirements_chain(requirements):
    '''
    Return an array of requirements file paths that can be used to complete
    the no_chown==False && user != None conundrum
    '''

    chain = []

    if isinstance(requirements, string_types):
        requirements = [requirements]

    for req_file in requirements:
        chain.append(req_file)
        chain.extend(_resolve_requirements_chain(_find_req(req_file)))

    return chain


def _process_requirements(requirements, cmd, cwd, saltenv, user):
    '''
    Process the requirements argument
    '''
    cleanup_requirements = []

    if requirements is not None:
        if isinstance(requirements, string_types):
            requirements = [r.strip() for r in requirements.split(',')]
        elif not isinstance(requirements, list):
            raise TypeError('requirements must be a string or list')

        treq = None

        for requirement in requirements:
            logger.debug('TREQ IS: %s', str(treq))
            if requirement.startswith('salt://'):
                cached_requirements = _get_cached_requirements(
                    requirement, saltenv
                )
                if not cached_requirements:
                    ret = {'result': False,
                           'comment': 'pip requirements file \'{0}\' not found'
                                      .format(requirement)}
                    return None, ret
                requirement = cached_requirements

            if user:
                # Need to make a temporary copy since the user will, most
                # likely, not have the right permissions to read the file

                if not treq:
                    treq = tempfile.mkdtemp()

                __salt__['file.chown'](treq, user, None)

                current_directory = None

                if not current_directory:
                    current_directory = os.path.abspath(os.curdir)

                logger.info('_process_requirements from directory,' +
                            '%s -- requirement: %s', cwd, requirement
                            )

                if cwd is None:
                    r = requirement
                    c = cwd

                    requirement_abspath = os.path.abspath(requirement)
                    cwd = os.path.dirname(requirement_abspath)
                    requirement = os.path.basename(requirement)

                    logger.debug('\n\tcwd: %s -> %s\n\trequirement: %s -> %s\n',
                                 c, cwd, r, requirement
                                 )

                os.chdir(cwd)

                reqs = _resolve_requirements_chain(requirement)

                os.chdir(current_directory)

                logger.info('request files: {0}'.format(str(reqs)))

                for req_file in reqs:
                    if not os.path.isabs(req_file):
                        req_file = os.path.join(cwd, req_file)

                    logger.debug('TREQ N CWD: %s -- %s -- for %s', str(treq), str(cwd), str(req_file))
                    target_path = os.path.join(treq, os.path.basename(req_file))

                    logger.debug('S: %s', req_file)
                    logger.debug('T: %s', target_path)

                    target_base = os.path.dirname(target_path)

                    if not os.path.exists(target_base):
                        os.makedirs(target_base, mode=0o755)
                        __salt__['file.chown'](target_base, user, None)

                    if not os.path.exists(target_path):
                        logger.debug(
                            'Copying %s to %s', req_file, target_path
                        )
                        __salt__['file.copy'](req_file, target_path)

                    logger.debug(
                        'Changing ownership of requirements file \'{0}\' to '
                        'user \'{1}\''.format(target_path, user)
                    )

                    __salt__['file.chown'](target_path, user, None)

            req_args = os.path.join(treq, requirement) if treq else requirement
            cmd.extend(['--requirement', req_args])

        cleanup_requirements.append(treq)

    logger.debug('CLEANUP_REQUIREMENTS: %s', str(cleanup_requirements))
    return cleanup_requirements, None


def install(pkgs=None,  # pylint: disable=R0912,R0913,R0914
            requirements=None,
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
            no_chown=False,
            cwd=None,
            pre_releases=False,
            cert=None,
            allow_all_external=False,
            allow_external=None,
            allow_unverified=None,
            process_dependency_links=False,
            saltenv='base',
            env_vars=None,
            use_vt=False,
            trusted_host=None,
            no_cache_dir=False,
            cache_dir=None):
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

        .. note::
            If installing into a virtualenv, just use the path to the
            virtualenv (e.g. ``/home/code/path/to/virtualenv/``)

    use_wheel
        Prefer wheel archives (requires pip>=1.4)

    no_use_wheel
        Force to not use wheel archives (requires pip>=1.4)

    log
        Log file where a complete (maximum verbosity) record will be kept

    proxy
        Specify a proxy in the form ``user:passwd@proxy.server:port``. Note
        that the ``user:password@`` is optional and required only if you are
        behind an authenticated proxy. If you provide
        ``user@proxy.server:port`` then you will be prompted for a password.

    timeout
        Set the socket timeout (default 15 seconds)

    editable
        install something editable (e.g.
        ``git+https://github.com/worldcompany/djangoembed.git#egg=djangoembed``)

    find_links
        URL to search for packages

    index_url
        Base URL of Python Package Index

    extra_index_url
        Extra URLs of package indexes to use in addition to ``index_url``

    no_index
        Ignore package index

    mirrors
        Specific mirror URL(s) to query (automatically adds --use-mirrors)

        .. warning::

            This option has been deprecated and removed in pip version 7.0.0.
            Please use ``index_url`` and/or ``extra_index_url`` instead.

    build
        Unpack packages into ``build`` dir

    target
        Install packages into ``target`` dir

    download
        Download packages into ``download`` instead of installing them

    download_cache | cache_dir
        Cache downloaded packages in ``download_cache`` or ``cache_dir`` dir

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
        Don't download any packages, just install the ones already downloaded
        (completes an install run with ``--no-install``)

    install_options
        Extra arguments to be supplied to the setup.py install command (e.g.
        like ``--install-option='--install-scripts=/usr/local/bin'``).  Use
        multiple --install-option options to pass multiple options to setup.py
        install. If you are using an option with a directory path, be sure to
        use absolute path.

    global_options
        Extra global options to be supplied to the setup.py call before the
        install command.

    user
        The user under which to run pip

    no_chown
        When user is given, do not attempt to copy and chown a requirements
        file

    cwd
        Current working directory to run pip from

    pre_releases
        Include pre-releases in the available versions

    cert
        Provide a path to an alternate CA bundle

    allow_all_external
        Allow the installation of all externally hosted files

    allow_external
        Allow the installation of externally hosted files (comma separated
        list)

    allow_unverified
        Allow the installation of insecure and unverifiable files (comma
        separated list)

    process_dependency_links
        Enable the processing of dependency links

    env_vars
        Set environment variables that some builds will depend on. For example,
        a Python C-module may have a Makefile that needs INCLUDE_PATH set to
        pick up a header file while compiling.  This must be in the form of a
        dictionary or a mapping.

        Example:

        .. code-block:: bash

            salt '*' pip.install django_app env_vars="{'CUSTOM_PATH': '/opt/django_app'}"

    trusted_host
        Mark this host as trusted, even though it does not have valid or any
        HTTPS.

    use_vt
        Use VT terminal emulation (see output while installing)

    no_cache_dir
        Disable the cache.

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
    pip_bin = _get_pip_bin(bin_env)

    cmd = [pip_bin, 'install']

    cleanup_requirements, error = _process_requirements(
        requirements=requirements,
        cmd=cmd,
        cwd=cwd,
        saltenv=saltenv,
        user=user
    )

    if error:
        return error

    if use_wheel:
        min_version = '1.4'
        cur_version = __salt__['pip.version'](bin_env)
        if not salt.utils.compare_versions(ver1=cur_version, oper='>=',
                                           ver2=min_version):
            logger.error(
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
            logger.error(
                ('The --no-use-wheel option is only supported in pip {0} and '
                 'newer. The version of pip detected is {1}. This option '
                 'will be ignored.'.format(min_version, cur_version))
            )
        else:
            cmd.append('--no-use-wheel')

    if log:
        if os.path.isdir(log):
            raise IOError(
                '\'{0}\' is a directory. Use --log path_to_file'.format(log))
        elif not os.access(log, os.W_OK):
            raise IOError('\'{0}\' is not writeable'.format(log))

        cmd.extend(['--log', log])

    if proxy:
        cmd.extend(['--proxy', proxy])

    if timeout:
        try:
            if isinstance(timeout, float):
                # Catch floating point input, exception will be caught in
                # exception class below.
                raise ValueError('Timeout cannot be a float')
            int(timeout)
        except ValueError:
            raise ValueError(
                '\'{0}\' is not a valid timeout, must be an integer'
                .format(timeout)
            )
        cmd.extend(['--timeout', timeout])

    if find_links:
        if isinstance(find_links, string_types):
            find_links = [l.strip() for l in find_links.split(',')]

        for link in find_links:
            if not (salt.utils.url.validate(link, VALID_PROTOS) or os.path.exists(link)):
                raise CommandExecutionError(
                    '\'{0}\' is not a valid URL or path'.format(link)
                )
            cmd.extend(['--find-links', link])

    if no_index and (index_url or extra_index_url):
        raise CommandExecutionError(
            '\'no_index\' and (\'index_url\' or \'extra_index_url\') are '
            'mutually exclusive.'
        )

    if index_url:
        if not salt.utils.url.validate(index_url, VALID_PROTOS):
            raise CommandExecutionError(
                '\'{0}\' is not a valid URL'.format(index_url)
            )
        cmd.extend(['--index-url', index_url])

    if extra_index_url:
        if not salt.utils.url.validate(extra_index_url, VALID_PROTOS):
            raise CommandExecutionError(
                '\'{0}\' is not a valid URL'.format(extra_index_url)
            )
        cmd.extend(['--extra-index-url', extra_index_url])

    if no_index:
        cmd.append('--no-index')

    if mirrors:
        # https://github.com/pypa/pip/pull/2641/files#diff-3ef137fb9ffdd400f117a565cd94c188L216
        pip_version = version(pip_bin)
        if salt.utils.compare_versions(ver1=pip_version, oper='>=', ver2='7.0.0'):
            raise CommandExecutionError(
                    'pip >= 7.0.0 does not support mirror argument:'
                    ' use index_url and/or extra_index_url instead'
            )

        if isinstance(mirrors, string_types):
            mirrors = [m.strip() for m in mirrors.split(',')]

        cmd.append('--use-mirrors')
        for mirror in mirrors:
            if not mirror.startswith('http://'):
                raise CommandExecutionError(
                    '\'{0}\' is not a valid URL'.format(mirror)
                )
            cmd.extend(['--mirrors', mirror])

    if build:
        cmd.extend(['--build', build])

    if target:
        cmd.extend(['--target', target])

    if download:
        cmd.extend(['--download', download])

    if download_cache or cache_dir:
        cmd.extend(['--cache-dir' if salt.utils.compare_versions(
            ver1=version(bin_env), oper='>=', ver2='6.0.0'
        ) else '--download-cache', download_cache or cache_dir])

    if source:
        cmd.extend(['--source', source])

    if upgrade:
        cmd.append('--upgrade')

    if force_reinstall:
        cmd.append('--force-reinstall')

    if ignore_installed:
        cmd.append('--ignore-installed')

    if exists_action:
        if exists_action.lower() not in ('s', 'i', 'w', 'b'):
            raise CommandExecutionError(
                'The exists_action pip option only supports the values '
                's, i, w, and b. \'{0}\' is not valid.'.format(exists_action)
            )
        cmd.extend(['--exists-action', exists_action])

    if no_deps:
        cmd.append('--no-deps')

    if no_install:
        cmd.append('--no-install')

    if no_download:
        cmd.append('--no-download')

    if no_cache_dir:
        cmd.append('--no-cache-dir')

    if pre_releases:
        # Check the locally installed pip version
        pip_version = version(pip_bin)

        # From pip v1.4 the --pre flag is available
        if salt.utils.compare_versions(ver1=pip_version, oper='>=', ver2='1.4'):
            cmd.append('--pre')

    if cert:
        cmd.extend(['--cert', cert])

    if global_options:
        if isinstance(global_options, string_types):
            global_options = [go.strip() for go in global_options.split(',')]

        for opt in global_options:
            cmd.extend(['--global-option', opt])

    if install_options:
        if isinstance(install_options, string_types):
            install_options = [io.strip() for io in install_options.split(',')]

        for opt in install_options:
            cmd.extend(['--install-option', opt])

    if pkgs:
        if isinstance(pkgs, string_types):
            pkgs = [p.strip() for p in pkgs.split(',')]

        # It's possible we replaced version-range commas with semicolons so
        # they would survive the previous line (in the pip.installed state).
        # Put the commas back in while making sure the names are contained in
        # quotes, this allows for proper version spec passing salt>=0.17.0
        cmd.extend(['{0}'.format(p.replace(';', ',')) for p in pkgs])

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
            cmd.extend(['--editable', entry])

    if allow_all_external:
        cmd.append('--allow-all-external')

    if allow_external:
        if isinstance(allow_external, string_types):
            allow_external = [p.strip() for p in allow_external.split(',')]

        for pkg in allow_external:
            cmd.extend(['--allow-external', pkg])

    if allow_unverified:
        if isinstance(allow_unverified, string_types):
            allow_unverified = \
                [p.strip() for p in allow_unverified.split(',')]

        for pkg in allow_unverified:
            cmd.extend(['--allow-unverified', pkg])

    if process_dependency_links:
        cmd.append('--process-dependency-links')

    if env_vars:
        if isinstance(env_vars, dict):
            for k, v in iteritems(env_vars):
                if not isinstance(v, string_types):
                    env_vars[k] = str(v)
            os.environ.update(env_vars)
        else:
            raise CommandExecutionError(
                'env_vars {0} is not a dictionary'.format(env_vars))

    if trusted_host:
        cmd.extend(['--trusted-host', trusted_host])

    try:
        cmd_kwargs = dict(saltenv=saltenv, use_vt=use_vt, runas=user)

        if cwd:
            cmd_kwargs['cwd'] = cwd

        if bin_env and os.path.isdir(bin_env):
            cmd_kwargs['env'] = {'VIRTUAL_ENV': bin_env}

        logger.debug(
            'TRY BLOCK: end of pip.install -- cmd: %s, cmd_kwargs: %s',
            str(cmd), str(cmd_kwargs)
        )

        return __salt__['cmd.run_all'](cmd,
                                       python_shell=False,
                                       **cmd_kwargs)
    finally:
        for tempdir in [cr for cr in cleanup_requirements if cr is not None]:
            if os.path.isdir(tempdir):
                shutil.rmtree(tempdir)


def uninstall(pkgs=None,
              requirements=None,
              bin_env=None,
              log=None,
              proxy=None,
              timeout=None,
              user=None,
              no_chown=False,
              cwd=None,
              saltenv='base',
              use_vt=False):
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
    no_chown
        When user is given, do not attempt to copy and chown
        a requirements file (needed if the requirements file refers to other
        files via relative paths, as the copy-and-chown procedure does not
        account for such files)
    cwd
        Current working directory to run pip from
    use_vt
        Use VT terminal emulation (see output while installing)

    CLI Example:

    .. code-block:: bash

        salt '*' pip.uninstall <package name>,<package2 name>
        salt '*' pip.uninstall requirements=/path/to/requirements.txt
        salt '*' pip.uninstall <package name> bin_env=/path/to/virtualenv
        salt '*' pip.uninstall <package name> bin_env=/path/to/pip_bin

    '''
    pip_bin = _get_pip_bin(bin_env)

    cmd = [pip_bin, 'uninstall', '-y']

    cleanup_requirements, error = _process_requirements(
        requirements=requirements, cmd=cmd, saltenv=saltenv, user=user,
        cwd=cwd
    )

    if error:
        return error

    if log:
        try:
            # TODO make this check if writeable
            os.path.exists(log)
        except IOError:
            raise IOError('\'{0}\' is not writeable'.format(log))

        cmd.extend(['--log', log])

    if proxy:
        cmd.extend(['--proxy', proxy])

    if timeout:
        try:
            if isinstance(timeout, float):
                # Catch floating point input, exception will be caught in
                # exception class below.
                raise ValueError('Timeout cannot be a float')
            int(timeout)
        except ValueError:
            raise ValueError(
                '\'{0}\' is not a valid timeout, must be an integer'
                .format(timeout)
            )
        cmd.extend(['--timeout', timeout])

    if pkgs:
        if isinstance(pkgs, string_types):
            pkgs = [p.strip() for p in pkgs.split(',')]
        if requirements:
            for requirement in requirements:
                with salt.utils.fopen(requirement) as rq_:
                    for req in rq_:
                        try:
                            req_pkg, _ = req.split('==')
                            if req_pkg in pkgs:
                                pkgs.remove(req_pkg)
                        except ValueError:
                            pass
        cmd.extend(pkgs)

    cmd_kwargs = dict(python_shell=False, runas=user,
                      cwd=cwd, saltenv=saltenv, use_vt=use_vt)
    if bin_env and os.path.isdir(bin_env):
        cmd_kwargs['env'] = {'VIRTUAL_ENV': bin_env}

    try:
        return __salt__['cmd.run_all'](cmd, **cmd_kwargs)
    finally:
        for requirement in cleanup_requirements:
            if requirement:
                try:
                    os.remove(requirement)
                except OSError:
                    pass


def freeze(bin_env=None,
           user=None,
           cwd=None,
           use_vt=False):
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
    cwd
        Current working directory to run pip from

    .. note::

        If the version of pip available is older than 8.0.3, the list will not
        include the packages pip, wheel, setuptools, or distribute even if they
        are installed.

    CLI Example:

    .. code-block:: bash

        salt '*' pip.freeze /home/code/path/to/virtualenv/

    .. versionchanged:: 2016.11.2

        The packages pip, wheel, setuptools, and distribute are included if the
        installed pip is new enough.
    '''
    pip_bin = _get_pip_bin(bin_env)

    cmd = [pip_bin, 'freeze']

    # Include pip, setuptools, distribute, wheel
    min_version = '8.0.3'
    cur_version = version(bin_env)
    if not salt.utils.compare_versions(ver1=cur_version, oper='>=',
                                       ver2=min_version):
        logger.warning(
            ('The version of pip installed is {0}, which is older than {1}. '
             'The packages pip, wheel, setuptools, and distribute will not be '
             'included in the output of pip.freeze').format(cur_version,
                                                            min_version))
    else:
        cmd.append('--all')

    cmd_kwargs = dict(runas=user, cwd=cwd, use_vt=use_vt, python_shell=False)
    if bin_env and os.path.isdir(bin_env):
        cmd_kwargs['env'] = {'VIRTUAL_ENV': bin_env}
    result = __salt__['cmd.run_all'](cmd, **cmd_kwargs)

    if result['retcode'] > 0:
        raise CommandExecutionError(result['stderr'])

    return result['stdout'].splitlines()


def list_(prefix=None,
          bin_env=None,
          user=None,
          cwd=None):
    '''
    Filter list of installed apps from ``freeze`` and check to see if
    ``prefix`` exists in the list of packages installed.

    .. note::

        If the version of pip available is older than 8.0.3, the packages
        wheel, setuptools, and distribute will not be reported by this function
        even if they are installed. Unlike
        :py:func:`pip.freeze <salt.modules.pip.freeze>`, this function always
        reports the version of pip which is installed.

    CLI Example:

    .. code-block:: bash

        salt '*' pip.list salt

    .. versionchanged:: 2016.11.2

        The packages wheel, setuptools, and distribute are included if the
        installed pip is new enough.
    '''
    packages = {}

    if prefix is None or 'pip'.startswith(prefix):
        packages['pip'] = version(bin_env)

    for line in freeze(bin_env=bin_env, user=user, cwd=cwd):
        if line.startswith('-f') or line.startswith('#'):
            # ignore -f line as it contains --find-links directory
            # ignore comment lines
            continue
        elif line.startswith('-e hg+not trust'):
            # ignore hg + not trust problem
            continue
        elif line.startswith('-e'):
            line = line.split('-e ')[1]
            version_, name = line.split('#egg=')
        elif len(line.split('===')) >= 2:
            name = line.split('===')[0]
            version_ = line.split('===')[1]
        elif len(line.split('==')) >= 2:
            name = line.split('==')[0]
            version_ = line.split('==')[1]
        else:
            logger.error('Can\'t parse line \'{0}\''.format(line))
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
    pip_bin = _get_pip_bin(bin_env)

    output = __salt__['cmd.run'](
        '{0} --version'.format(pip_bin), python_shell=False)
    try:
        return re.match(r'^pip (\S+)', output).group(1)
    except AttributeError:
        return None


def list_upgrades(bin_env=None,
                  user=None,
                  cwd=None):
    '''
    Check whether or not an upgrade is available for all packages

    CLI Example:

    .. code-block:: bash

        salt '*' pip.list_upgrades
    '''
    pip_bin = _get_pip_bin(bin_env)

    cmd = [pip_bin, 'list', '--outdated']

    cmd_kwargs = dict(cwd=cwd, runas=user)
    if bin_env and os.path.isdir(bin_env):
        cmd_kwargs['env'] = {'VIRTUAL_ENV': bin_env}

    result = __salt__['cmd.run_all'](cmd, **cmd_kwargs)
    if result['retcode'] > 0:
        logger.error(result['stderr'])
        raise CommandExecutionError(result['stderr'])

    packages = {}
    for line in result['stdout'].splitlines():
        match = re.search(r'(\S*)\s+\(.*Latest:\s+(.*)\)', line)
        if match:
            name, version_ = match.groups()
        else:
            logger.error('Can\'t parse line \'{0}\''.format(line))
            continue
        packages[name] = version_
    return packages


def upgrade_available(pkg,
                      bin_env=None,
                      user=None,
                      cwd=None):
    '''
    .. versionadded:: 2015.5.0

    Check whether or not an upgrade is available for a given package

    CLI Example:

    .. code-block:: bash

        salt '*' pip.upgrade_available <package name>
    '''
    return pkg in list_upgrades(bin_env=bin_env, user=user, cwd=cwd)


def upgrade(bin_env=None,
            user=None,
            cwd=None,
            use_vt=False):
    '''
    .. versionadded:: 2015.5.0

    Upgrades outdated pip packages

    Returns a dict containing the changes.

        {'<package>':  {'old': '<old-version>',
                        'new': '<new-version>'}}


    CLI Example:

    .. code-block:: bash

        salt '*' pip.upgrade
    '''
    ret = {'changes': {},
           'result': True,
           'comment': '',
           }
    pip_bin = _get_pip_bin(bin_env)

    old = list_(bin_env=bin_env, user=user, cwd=cwd)

    cmd = [pip_bin, 'install', '-U']
    cmd_kwargs = dict(cwd=cwd, use_vt=use_vt)
    if bin_env and os.path.isdir(bin_env):
        cmd_kwargs['env'] = {'VIRTUAL_ENV': bin_env}
    errors = False
    for pkg in list_upgrades(bin_env=bin_env, user=user, cwd=cwd):
        result = __salt__['cmd.run_all'](cmd + [pkg], **cmd_kwargs)
        if result['retcode'] != 0:
            errors = True
        if 'stderr' in result:
            ret['comment'] += result['stderr']
    if errors:
        ret['result'] = False

    new = list_(bin_env=bin_env, user=user, cwd=cwd)

    ret['changes'] = salt.utils.compare_dicts(old, new)

    return ret
