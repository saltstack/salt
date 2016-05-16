# -*- coding: utf-8 -*-
'''
Installation of Python Packages Using pip
=========================================

These states manage system installed python packages. Note that pip must be
installed for these states to be available, so pip states should include a
requisite to a pkg.installed state for the package which provides pip
(``python-pip`` in most cases). Example:

.. code-block:: yaml

    python-pip:
      pkg.installed

    virtualenvwrapper:
      pip.installed:
        - require:
          - pkg: python-pip
'''

# Import python libs
from __future__ import absolute_import
import re
import logging

# Import salt libs
import salt.utils
from salt.version import SaltStackVersion as _SaltStackVersion
from salt.exceptions import CommandExecutionError, CommandNotFoundError

# Import 3rd-party libs
import salt.ext.six as six
# pylint: disable=import-error
try:
    import pip
    HAS_PIP = True
except ImportError:
    HAS_PIP = False

if HAS_PIP is True:
    try:
        import pip.req
    except ImportError:
        HAS_PIP = False
        # Remove references to the loaded pip module above so reloading works
        import sys
        del pip
        if 'pip' in sys.modules:
            del sys.modules['pip']

    ver = getattr(pip, '__version__', '0.0.0').split('.')
    pip_ver = tuple([int(x) for x in ver if x.isdigit()])
    if pip_ver >= (8, 0, 0):
        from pip.exceptions import InstallationError
    else:
        InstallationError = ValueError

# pylint: enable=import-error

logger = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'pip'


def __virtual__():
    '''
    Only load if the pip module is available in __salt__
    '''
    if 'pip.list' in __salt__:
        return __virtualname__
    return False


def _find_key(prefix, pip_list):
    '''
    Does a case-insensitive match in the pip_list for the desired package.
    '''
    try:
        match = next(
            iter(x for x in pip_list if x.lower() == prefix.lower())
        )
    except StopIteration:
        return None
    else:
        return match


def _fulfills_version_spec(version, version_spec):
    '''
    Check version number against version specification info and return a
    boolean value based on whether or not the version number meets the
    specified version.
    '''
    for oper, spec in version_spec:
        if oper is None:
            continue
        if not salt.utils.compare_versions(ver1=version, oper=oper, ver2=spec):
            return False
    return True


def _check_pkg_version_format(pkg):
    '''
    Takes a package name and version specification (if any) and checks it using
    the pip library.
    '''

    ret = {'result': False, 'comment': None,
           'prefix': None, 'version_spec': None}

    if not HAS_PIP:
        ret['comment'] = (
            'An importable pip module is required but could not be found on '
            'your system. This usually means that the system\'s pip package '
            'is not installed properly.'
        )

        return ret

    from_vcs = False
    try:
        # Get the requirement object from the pip library
        try:
            # With pip < 1.2, the __version__ attribute does not exist and
            # vcs+URL urls are not properly parsed.
            # The next line is meant to trigger an AttributeError and
            # handle lower pip versions
            logger.debug(
                'Installed pip version: {0}'.format(pip.__version__)
            )
            install_req = pip.req.InstallRequirement.from_line(pkg)
        except AttributeError:
            logger.debug('Installed pip version is lower than 1.2')
            supported_vcs = ('git', 'svn', 'hg', 'bzr')
            if pkg.startswith(supported_vcs):
                for vcs in supported_vcs:
                    if pkg.startswith(vcs):
                        from_vcs = True
                        install_req = pip.req.InstallRequirement.from_line(
                            pkg.split('{0}+'.format(vcs))[-1]
                        )
                        break
            else:
                install_req = pip.req.InstallRequirement.from_line(pkg)
    except (ValueError, InstallationError) as exc:
        ret['result'] = False
        if not from_vcs and '=' in pkg and '==' not in pkg:
            ret['comment'] = (
                'Invalid version specification in package {0}. \'=\' is '
                'not supported, use \'==\' instead.'.format(pkg)
            )
            return ret
        ret['comment'] = (
            'pip raised an exception while parsing {0!r}: {1}'.format(
                pkg, exc
            )
        )
        return ret

    if install_req.req is None:
        # This is most likely an url and there's no way to know what will
        # be installed before actually installing it.
        ret['result'] = True
        ret['prefix'] = ''
        ret['version_spec'] = []
    else:
        ret['result'] = True
        ret['prefix'] = re.sub('[^A-Za-z0-9.]+', '-', install_req.name)
        if hasattr(install_req, "specifier"):
            specifier = install_req.specifier
        else:
            specifier = install_req.req.specifier
        ret['version_spec'] = [(spec.operator, spec.version) for spec in specifier]

    return ret


def _check_if_installed(prefix, state_pkg_name, version_spec,
                        ignore_installed, force_reinstall,
                        upgrade, user, cwd, bin_env):

    # result: None means the command failed to run
    # result: True means the package is installed
    # result: False means the package is not installed
    ret = {'result': False, 'comment': None}

    # Check if the requested package is already installed.
    try:
        pip_list = __salt__['pip.list'](prefix, bin_env=bin_env,
                                        user=user, cwd=cwd)
        prefix_realname = _find_key(prefix, pip_list)
    except (CommandNotFoundError, CommandExecutionError) as err:
        ret['result'] = None
        ret['comment'] = 'Error installing {0!r}: {1}'.format(state_pkg_name,
                                                              err)
        return ret

    # If the package was already installed, check
    # the ignore_installed and force_reinstall flags
    if ignore_installed is False and prefix_realname is not None:
        if force_reinstall is False and not upgrade:
            # Check desired version (if any) against currently-installed
            if (
                any(version_spec) and
                _fulfills_version_spec(pip_list[prefix_realname],
                                       version_spec)
            ) or (not any(version_spec)):
                ret['result'] = True
                ret['comment'] = ('Python package {0} was already '
                                  'installed'.format(state_pkg_name))
                return ret

    return ret


def installed(name,
              pkgs=None,
              pip_bin=None,
              requirements=None,
              env=None,
              bin_env=None,
              use_wheel=False,
              no_use_wheel=False,
              log=None,
              proxy=None,
              timeout=None,
              repo=None,
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
              install_options=None,
              global_options=None,
              user=None,
              no_chown=False,
              cwd=None,
              activate=False,
              pre_releases=False,
              cert=None,
              allow_all_external=False,
              allow_external=None,
              allow_unverified=None,
              process_dependency_links=False,
              env_vars=None,
              use_vt=False,
              trusted_host=None,
              no_cache_dir=False):
    '''
    Make sure the package is installed

    name
        The name of the python package to install. You can also specify version
        numbers here using the standard operators ``==, >=, <=``. If
        ``requirements`` is given, this parameter will be ignored.

    Example:

    .. code-block:: yaml

        django:
          pip.installed:
            - name: django >= 1.6, <= 1.7
            - require:
              - pkg: python-pip

    This will install the latest Django version greater than 1.6 but less
    than 1.7.

    requirements
        Path to a pip requirements file. If the path begins with salt://
        the file will be transferred from the master file server.

    user
        The user under which to run pip

    use_wheel : False
        Prefer wheel archives (requires pip>=1.4)

    no_use_wheel : False
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

    no_chown
        When user is given, do not attempt to copy and chown
        a requirements file

    no_cache_dir:
        Disable the cache.

    cwd
        Current working directory to run pip from

    activate
        Activates the virtual environment, if given via bin_env,
        before running install.

        .. deprecated:: 2014.7.2
            If `bin_env` is given, pip will already be sourced from that
            virtualenv, making `activate` effectively a noop.

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

    bin_env : None
        Absolute path to a virtual environment directory or absolute path to
        a pip executable. The example below assumes a virtual environment
        has been created at ``/foo/.virtualenvs/bar``.

    env_vars
        Add or modify environment variables. Useful for tweaking build steps,
        such as specifying INCLUDE or LIBRARY paths in Makefiles, build scripts or
        compiler calls.  This must be in the form of a dictionary or a mapping.

        Example:

        .. code-block:: yaml

            django:
              pip.installed:
                - name: django_app
                - env_vars:
                    CUSTOM_PATH: /opt/django_app
                    VERBOSE: True

    use_vt
        Use VT terminal emulation (see output while installing)

    trusted_host
        Mark this host as trusted, even though it does not have valid or any
        HTTPS.

    Example:

    .. code-block:: yaml

        django:
          pip.installed:
            - name: django >= 1.6, <= 1.7
            - bin_env: /foo/.virtualenvs/bar
            - require:
              - pkg: python-pip

    Or

    Example:

    .. code-block:: yaml

        django:
          pip.installed:
            - name: django >= 1.6, <= 1.7
            - bin_env: /foo/.virtualenvs/bar/bin/pip
            - require:
              - pkg: python-pip

    .. admonition:: Attention

        The following arguments are deprecated, do not use.

    pip_bin : None
        Deprecated, use ``bin_env``

    env : None
        Deprecated, use ``bin_env``

    .. versionchanged:: 0.17.0
        ``use_wheel`` option added.

    install_options

        Extra arguments to be supplied to the setup.py install command.
        If you are using an option with a directory path, be sure to use
        absolute path.

        Example:

        .. code-block:: yaml

            django:
              pip.installed:
                - name: django
                - install_options:
                  - --prefix=/blah
                - require:
                  - pkg: python-pip

    global_options
        Extra global options to be supplied to the setup.py call before the
        install command.

        .. versionadded:: 2014.1.3

    .. admonition:: Attention

        As of Salt 0.17.0 the pip state **needs** an importable pip module.
        This usually means having the system's pip package installed or running
        Salt from an active `virtualenv`_.

        The reason for this requirement is because ``pip`` already does a
        pretty good job parsing its own requirements. It makes no sense for
        Salt to do ``pip`` requirements parsing and validation before passing
        them to the ``pip`` library. It's functionality duplication and it's
        more error prone.


    .. admonition:: Attention

        Please set ``reload_modules: True`` to have the salt minion
        import this module after installation.


    Example:

    .. code-block:: yaml

        pyopenssl:
            pip.installed:
                - name: pyOpenSSL
                - reload_modules: True
                - exists_action: i


    .. _`virtualenv`: http://www.virtualenv.org/en/latest/
    '''

    if pip_bin and not bin_env:
        bin_env = pip_bin
    elif env and not bin_env:
        bin_env = env

    # If pkgs is present, ignore name
    if pkgs:
        if not isinstance(pkgs, list):
            return {'name': name,
                    'result': False,
                    'changes': {},
                    'comment': 'pkgs argument must be formatted as a list'}
    else:
        pkgs = [name]

    # Assumption: If `pkg` is not an `string`, it's a `collections.OrderedDict`
    # prepro = lambda pkg: pkg if type(pkg) == str else \
    #     ' '.join((pkg.items()[0][0], pkg.items()[0][1].replace(',', ';')))
    # pkgs = ','.join([prepro(pkg) for pkg in pkgs])
    prepro = lambda pkg: pkg if isinstance(pkg, str) else \
        ' '.join((six.iteritems(pkg)[0][0], six.iteritems(pkg)[0][1]))
    pkgs = [prepro(pkg) for pkg in pkgs]

    ret = {'name': ';'.join(pkgs), 'result': None,
           'comment': '', 'changes': {}}

    # Check that the pip binary supports the 'use_wheel' option
    if use_wheel:
        min_version = '1.4'
        cur_version = __salt__['pip.version'](bin_env)
        if not salt.utils.compare_versions(ver1=cur_version, oper='>=',
                                           ver2=min_version):
            ret['result'] = False
            ret['comment'] = ('The \'use_wheel\' option is only supported in '
                              'pip {0} and newer. The version of pip detected '
                              'was {1}.').format(min_version, cur_version)
            return ret

    # Check that the pip binary supports the 'no_use_wheel' option
    if no_use_wheel:
        min_version = '1.4'
        cur_version = __salt__['pip.version'](bin_env)
        if not salt.utils.compare_versions(ver1=cur_version, oper='>=',
                                           ver2=min_version):
            ret['result'] = False
            ret['comment'] = ('The \'no_use_wheel\' option is only supported in '
                              'pip {0} and newer. The version of pip detected '
                              'was {1}.').format(min_version, cur_version)
            return ret

    # Deprecation warning for the repo option
    if repo is not None:
        msg = ('The \'repo\' argument to pip.installed is deprecated and will '
               'be removed in Salt {version}. Please use \'name\' instead. '
               'The current value for name, {0!r} will be replaced by the '
               'value of repo, {1!r}'.format(
                   name,
                   repo,
                   version=_SaltStackVersion.from_name('Lithium').formatted_version
               ))
        salt.utils.warn_until('Lithium', msg)
        ret.setdefault('warnings', []).append(msg)
        name = repo

    # Get the packages parsed name and version from the pip library.
    # This only is done when there is no requirements or editable parameter.
    pkgs_details = []
    if pkgs and not (requirements or editable):
        comments = []
        for pkg in iter(pkgs):
            out = _check_pkg_version_format(pkg)
            if out['result'] is False:
                ret['result'] = False
                comments.append(out['comment'])
            elif out['result'] is True:
                pkgs_details.append((out['prefix'], pkg, out['version_spec']))

        if ret['result'] is False:
            ret['comment'] = '\n'.join(comments)
            return ret

    # If a requirements file is specified, only install the contents of the
    # requirements file. Similarly, using the --editable flag with pip should
    # also ignore the "name" and "pkgs" parameters.
    target_pkgs = []
    already_installed_comments = []
    if requirements or editable:
        comments = []
        # Append comments if this is a dry run.
        if __opts__['test']:
            ret['result'] = None
            if requirements:
                # TODO: Check requirements file against currently-installed
                # packages to provide more accurate state output.
                comments.append('Requirements file {0!r} will be '
                                'processed.'.format(requirements))
            if editable:
                comments.append(
                    'Package will be installed in editable mode (i.e. '
                    'setuptools "develop mode") from {0}.'.format(editable)
                )
            ret['comment'] = ' '.join(comments)
            return ret

    # No requirements case.
    # Check pre-existence of the requested packages.
    else:
        for prefix, state_pkg_name, version_spec in pkgs_details:

            if prefix:
                state_pkg_name = state_pkg_name
                version_spec = version_spec
                out = _check_if_installed(prefix, state_pkg_name, version_spec,
                                          ignore_installed, force_reinstall,
                                          upgrade, user, cwd, bin_env)
                # If _check_if_installed result is None, something went wrong with
                # the command running. This way we keep stateful output.
                if out['result'] is None:
                    ret['result'] = False
                    ret['comment'] = out['comment']
                    return ret
            else:
                out = {'result': False, 'comment': None}

            result = out['result']

            # The package is not present. Add it to the pkgs to install.
            if result is False:
                # Replace commas (used for version ranges) with semicolons
                # (which are not supported) in name so it does not treat
                # them as multiple packages.
                target_pkgs.append((prefix, state_pkg_name.replace(',', ';')))

                # Append comments if this is a dry run.
                if __opts__['test']:
                    msg = 'Python package {0} is set to be installed'
                    ret['result'] = None
                    ret['comment'] = msg.format(state_pkg_name)
                    return ret

            # The package is already present and will not be reinstalled.
            elif result is True:
                # Append comment stating its presence
                already_installed_comments.append(out['comment'])

            # The command pip.list failed. Abort.
            elif result is None:
                ret['result'] = None
                ret['comment'] = out['comment']
                return ret

    # Construct the string that will get passed to the install call
    pkgs_str = ','.join([state_name for _, state_name in target_pkgs])

    # Call to install the package. Actual installation takes place here
    pip_install_call = __salt__['pip.install'](
        pkgs='{0}'.format(pkgs_str) if pkgs_str else '',
        requirements=requirements,
        bin_env=bin_env,
        use_wheel=use_wheel,
        no_use_wheel=no_use_wheel,
        log=log,
        proxy=proxy,
        timeout=timeout,
        editable=editable,
        find_links=find_links,
        index_url=index_url,
        extra_index_url=extra_index_url,
        no_index=no_index,
        mirrors=mirrors,
        build=build,
        target=target,
        download=download,
        download_cache=download_cache,
        source=source,
        upgrade=upgrade,
        force_reinstall=force_reinstall,
        ignore_installed=ignore_installed,
        exists_action=exists_action,
        no_deps=no_deps,
        no_install=no_install,
        no_download=no_download,
        install_options=install_options,
        global_options=global_options,
        user=user,
        no_chown=no_chown,
        cwd=cwd,
        activate=activate,
        pre_releases=pre_releases,
        cert=cert,
        allow_all_external=allow_all_external,
        allow_external=allow_external,
        allow_unverified=allow_unverified,
        process_dependency_links=process_dependency_links,
        saltenv=__env__,
        env_vars=env_vars,
        use_vt=use_vt,
        trusted_host=trusted_host,
        no_cache_dir=no_cache_dir
    )

    # Check the retcode for success, but don't fail if using pip1 and the package is
    # already present. Pip1 returns a retcode of 1 (instead of 0 for pip2) if you run
    # "pip install" without any arguments. See issue #21845.
    if pip_install_call and \
            (pip_install_call.get('retcode', 1) == 0 or pip_install_call.get('stdout', '').startswith(
                'You must give at least one requirement to install')):
        ret['result'] = True

        if requirements or editable:
            comments = []
            if requirements:
                for line in pip_install_call.get('stdout', '').split('\n'):
                    if not line.startswith('Requirement already satisfied') \
                            and line != 'Cleaning up...':
                        ret['changes']['requirements'] = True
                if ret['changes'].get('requirements'):
                    comments.append('Successfully processed requirements file '
                                    '{0}.'.format(requirements))
                else:
                    comments.append('Requirements were already installed.')

            if editable:
                comments.append('Package successfully installed from VCS '
                                'checkout {0}.'.format(editable))
                ret['changes']['editable'] = True
            ret['comment'] = ' '.join(comments)
        else:

            # Check that the packages set to be installed were installed.
            # Create comments reporting success and failures
            pkg_404_comms = []

            already_installed_packages = set()
            for line in pip_install_call.get('stdout', '').split('\n'):
                # Output for already installed packages:
                # 'Requirement already up-to-date: jinja2 in /usr/local/lib/python2.7/dist-packages\nCleaning up...'
                if line.startswith('Requirement already up-to-date: '):
                    package = line.split(':', 1)[1].split()[0]
                    already_installed_packages.add(package.lower())

            for prefix, state_name in target_pkgs:

                # Case for packages that are not an URL
                if prefix:
                    pipsearch = __salt__['pip.list'](prefix, bin_env,
                                                     user=user, cwd=cwd)

                    # If we didnt find the package in the system after
                    # installing it report it
                    if not pipsearch:
                        pkg_404_comms.append(
                            'There was no error installing package \'{0}\' '
                            'although it does not show when calling '
                            '\'pip.freeze\'.'.format(pkg)
                        )
                    else:
                        pkg_name = _find_key(prefix, pipsearch)
                        if pkg_name.lower() in already_installed_packages:
                            continue
                        ver = pipsearch[pkg_name]
                        ret['changes']['{0}=={1}'.format(pkg_name,
                                                         ver)] = 'Installed'
                # Case for packages that are an URL
                else:
                    ret['changes']['{0}==???'.format(state_name)] = 'Installed'

            # Set comments
            aicomms = '\n'.join(already_installed_comments)
            succ_comm = 'All packages were successfully installed'\
                        if not pkg_404_comms else '\n'.join(pkg_404_comms)
            ret['comment'] = aicomms + ('\n' if aicomms else '') + succ_comm

            return ret

    elif pip_install_call:
        ret['result'] = False
        if 'stdout' in pip_install_call:
            error = 'Error: {0} {1}'.format(pip_install_call['stdout'],
                                            pip_install_call['stderr'])
        else:
            error = 'Error: {0}'.format(pip_install_call['comment'])

        if requirements or editable:
            comments = []
            if requirements:
                comments.append('Unable to process requirements file '
                                '"{0}".'.format(requirements))
            if editable:
                comments.append('Unable to install from VCS checkout'
                                '{0}.'.format(editable))
            comments.append(error)
            ret['comment'] = ' '.join(comments)
        else:
            pkgs_str = ', '.join([state_name for _, state_name in target_pkgs])
            aicomms = '\n'.join(already_installed_comments)
            error_comm = ('Failed to install packages: {0}. '
                          '{1}'.format(pkgs_str, error))
            ret['comment'] = aicomms + ('\n' if aicomms else '') + error_comm
    else:
        ret['result'] = False
        ret['comment'] = 'Could not install package'

    return ret


def removed(name,
            requirements=None,
            bin_env=None,
            log=None,
            proxy=None,
            timeout=None,
            user=None,
            cwd=None,
            use_vt=False):
    '''
    Make sure that a package is not installed.

    name
        The name of the package to uninstall
    user
        The user under which to run pip
    bin_env : None
        the pip executable or virtualenenv to use
    use_vt
        Use VT terminal emulation (see output while installing)
    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    try:
        pip_list = __salt__['pip.list'](bin_env=bin_env, user=user, cwd=cwd)
    except (CommandExecutionError, CommandNotFoundError) as err:
        ret['result'] = False
        ret['comment'] = 'Error uninstalling \'{0}\': {1}'.format(name, err)
        return ret

    if name not in pip_list:
        ret['result'] = True
        ret['comment'] = 'Package is not installed.'
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Package {0} is set to be removed'.format(name)
        return ret

    if __salt__['pip.uninstall'](pkgs=name,
                                 requirements=requirements,
                                 bin_env=bin_env,
                                 log=log,
                                 proxy=proxy,
                                 timeout=timeout,
                                 user=user,
                                 cwd=cwd,
                                 use_vt=use_vt):
        ret['result'] = True
        ret['changes'][name] = 'Removed'
        ret['comment'] = 'Package was successfully removed.'
    else:
        ret['result'] = False
        ret['comment'] = 'Could not remove package.'
    return ret


def uptodate(name,
             bin_env=None,
             user=None,
             cwd=None,
             use_vt=False):
    '''
    .. versionadded:: 2015.5.0

    Verify that the system is completely up to date.

    name
        The name has no functional value and is only used as a tracking
        reference
    user
        The user under which to run pip
    bin_env
        the pip executable or virtualenenv to use
    use_vt
        Use VT terminal emulation (see output while installing)
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': 'Failed to update.'}

    try:
        packages = __salt__['pip.list_upgrades'](bin_env=bin_env, user=user, cwd=cwd)
    except Exception as e:
        ret['comment'] = str(e)
        return ret

    if not packages:
        ret['comment'] = 'System is already up-to-date.'
        ret['result'] = True
        return ret
    elif __opts__['test']:
        ret['comment'] = 'System update will be performed'
        ret['result'] = None
        return ret

    updated = __salt__['pip.upgrade'](bin_env=bin_env, user=user, cwd=cwd, use_vt=use_vt)

    if updated.get('result') is False:
        ret.update(updated)
    elif updated:
        ret['changes'] = updated
        ret['comment'] = 'Upgrade successful.'
        ret['result'] = True
    else:
        ret['comment'] = 'Upgrade failed.'

    return ret
