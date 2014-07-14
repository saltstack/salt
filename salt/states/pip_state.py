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
import logging

# Import salt libs
import salt.utils
from salt.version import SaltStackVersion as _SaltStackVersion
from salt.exceptions import CommandExecutionError, CommandNotFoundError

# Import 3rd-party libs
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

logger = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'pip'


def __virtual__():
    '''
    Only load if the pip module is available in __salt__
    '''
    if HAS_PIP and 'pip.list' in __salt__:
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


def installed(name,
              pip_bin=None,
              requirements=None,
              env=None,
              bin_env=None,
              use_wheel=False,
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
              runas=None,
              no_chown=False,
              cwd=None,
              activate=False,
              pre_releases=False,
              cert=None,
              allow_all_external=False,
              allow_external=None,
              allow_unverified=None,
              process_dependency_links=False):
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

    bin_env : None
        Absolute path to a virtual environment directory or absolute path to
        a pip executable. The example below assumes a virtual environment
        has been created at ``/foo/.virtualenvs/bar``.

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

    .. _`virtualenv`: http://www.virtualenv.org/en/latest/
    '''
    if pip_bin and not bin_env:
        bin_env = pip_bin
    elif env and not bin_env:
        bin_env = env

    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

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

    from_vcs = False

    if name and not requirements:
        try:
            try:
                # With pip < 1.2, the __version__ attribute does not exist and
                # vcs+URL urls are not properly parsed.
                # The next line is meant to trigger an AttributeError and
                # handle lower pip versions
                logger.debug(
                    'Installed pip version: {0}'.format(pip.__version__)
                )
                install_req = pip.req.InstallRequirement.from_line(name)
            except AttributeError:
                logger.debug('Installed pip version is lower than 1.2')
                supported_vcs = ('git', 'svn', 'hg', 'bzr')
                if name.startswith(supported_vcs):
                    for vcs in supported_vcs:
                        if name.startswith(vcs):
                            from_vcs = True
                            install_req = pip.req.InstallRequirement.from_line(
                                name.split('{0}+'.format(vcs))[-1]
                            )
                            break
                else:
                    install_req = pip.req.InstallRequirement.from_line(name)
        except ValueError as exc:
            ret['result'] = False
            if not from_vcs and '=' in name and '==' not in name:
                ret['comment'] = (
                    'Invalid version specification in package {0}. \'=\' is '
                    'not supported, use \'==\' instead.'.format(name)
                )
                return ret
            ret['comment'] = (
                'pip raised an exception while parsing {0!r}: {1}'.format(
                    name, exc
                )
            )
            return ret

        if install_req.req is None:
            # This is most likely an url and there's no way to know what will
            # be installed before actually installing it.
            prefix = ''
            version_spec = []
        else:
            prefix = install_req.req.project_name
            version_spec = install_req.req.specs
    else:
        prefix = ''
        version_spec = []

    if runas is not None:
        # The user is using a deprecated argument, warn!
        msg = ('The \'runas\' argument to pip.installed is deprecated, and '
               'will be removed in Salt {version}. Please use \'user\' '
               'instead.'.format(
                   version=_SaltStackVersion.from_name('Lithium').formatted_version
               ))
        salt.utils.warn_until('Lithium', msg)
        ret.setdefault('warnings', []).append(msg)

        # "There can only be one"
        if user:
            raise CommandExecutionError(
                'The \'runas\' and \'user\' arguments are mutually exclusive. '
                'Please use \'user\' as \'runas\' is being deprecated.'
            )
        # Support deprecated 'runas' arg
        else:
            user = runas

    # Replace commas (used for version ranges) with semicolons (which are not
    # supported) in name so it does not treat them as multiple packages.  Comma
    # will be re-added in pip.install call.
    name = name.replace(',', ';')

    # If a requirements file is specified, only install the contents of the
    # requirements file. Similarly, using the --editable flag with pip should
    # also ignore the "name" parameter.
    if requirements or editable:
        name = ''
        comments = []
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
    else:
        try:
            pip_list = __salt__['pip.list'](prefix, bin_env=bin_env,
                                            user=user, cwd=cwd)
            prefix_realname = _find_key(prefix, pip_list)
        except (CommandNotFoundError, CommandExecutionError) as err:
            ret['result'] = False
            ret['comment'] = 'Error installing {0!r}: {1}'.format(name, err)
            return ret

        if ignore_installed is False and prefix_realname is not None:
            if force_reinstall is False and not upgrade:
                # Check desired version (if any) against currently-installed
                if (
                        any(version_spec) and
                        _fulfills_version_spec(pip_list[prefix_realname],
                                            version_spec)
                        ) or (not any(version_spec)):
                    ret['result'] = True
                    ret['comment'] = ('Python package {0} already '
                                    'installed'.format(name))
                    return ret

        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = \
                'Python package {0} is set to be installed'.format(name)
            return ret

    pip_install_call = __salt__['pip.install'](
        pkgs='{0}'.format(name) if name else '',
        requirements=requirements,
        bin_env=bin_env,
        use_wheel=use_wheel,
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
        saltenv=__env__
    )

    if pip_install_call and (pip_install_call.get('retcode', 1) == 0):
        ret['result'] = True

        if requirements or editable:
            comments = []
            if requirements:
                for eachline in pip_install_call.get('stdout', '').split('\n'):
                    if not eachline.startswith('Requirement already satisfied') and eachline != 'Cleaning up...':
                        ret['changes']['requirements'] = True
                if ret['changes'].get('requirements'):
                    comments.append('Successfully processed requirements file '
                                    '{0}.'.format(requirements))
                else:
                    comments.append('Requirements was successfully installed')
                comments.append('Successfully processed requirements file '
                                '{0}.'.format(requirements))
            if editable:
                comments.append('Package successfully installed from VCS '
                                'checkout {0}.'.format(editable))
                ret['changes']['editable'] = True
            ret['comment'] = ' '.join(comments)
        else:
            if not prefix:
                pkg_list = {}
            else:
                pkg_list = __salt__['pip.list'](
                    prefix, bin_env, user=user, cwd=cwd
                )
            if not pkg_list:
                ret['comment'] = (
                    'There was no error installing package \'{0}\' although '
                    'it does not show when calling '
                    '\'pip.freeze\'.'.format(name)
                )
                ret['changes']['{0}==???'.format(name)] = 'Installed'
                return ret

            version = list(pkg_list.values())[0]
            pkg_name = next(iter(pkg_list))
            ret['changes']['{0}=={1}'.format(pkg_name, version)] = 'Installed'
            ret['comment'] = 'Package was successfully installed'
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
                                '{0}.'.format(requirements))
            if editable:
                comments.append('Unable to install from VCS checkout'
                                '{0}.'.format(editable))
            comments.append(error)
            ret['comment'] = ' '.join(comments)
        else:
            ret['comment'] = ('Failed to install package {0}. '
                              '{1}'.format(name, error))
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
            runas=None,
            cwd=None):
    '''
    Make sure that a package is not installed.

    name
        The name of the package to uninstall
    user
        The user under which to run pip
    bin_env : None
        the pip executable or virtualenenv to use
    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    if runas is not None:
        # The user is using a deprecated argument, warn!
        msg = ('The \'runas\' argument to pip.installed is deprecated, and '
               'will be removed in Salt {version}. Please use \'user\' '
               'instead.'.format(
                   version=_SaltStackVersion.from_name('Lithium').formatted_version
               ))
        salt.utils.warn_until('Lithium', msg)
        ret.setdefault('warnings', []).append(msg)

    # "There can only be one"
    if runas is not None and user:
        raise CommandExecutionError(
            'The \'runas\' and \'user\' arguments are mutually exclusive. '
            'Please use \'user\' as \'runas\' is being deprecated.'
        )
    # Support deprecated 'runas' arg
    elif runas is not None and not user:
        user = runas

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
                                 cwd=cwd):
        ret['result'] = True
        ret['changes'][name] = 'Removed'
        ret['comment'] = 'Package was successfully removed.'
    else:
        ret['result'] = False
        ret['comment'] = 'Could not remove package.'
    return ret
