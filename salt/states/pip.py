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
import re
import urlparse

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError, CommandNotFoundError


def __virtual__():
    '''
    Only load if the pip module is available in __salt__
    '''
    return 'pip' if 'pip.list' in __salt__ else False


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
    for oper, spec in (version_spec[0:2], version_spec[2:4]):
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
              user=None,
              runas=None,
              no_chown=False,
              cwd=None,
              pre_releases=False,
              __env__='base'):
    '''
    Make sure the package is installed

    name
        The name of the python package to install
    user
        The user under which to run pip
    pip_bin : None
        Deprecated, use bin_env
    env : None
        Deprecated, use bin_env
    bin_env : None
        the pip executable or virtualenv to use

    '''
    if pip_bin and not bin_env:
        bin_env = pip_bin
    elif env and not bin_env:
        bin_env = env

    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    scheme, netloc, path, query, fragment = urlparse.urlsplit(name)
    if scheme and netloc:
        # parse as VCS url
        prefix = path.lstrip('/').split('@', 1)[0]
        if scheme.startswith('git+'):
            prefix = prefix.rstrip('.git')
    else:
        # Split the passed string into the prefix and version
        try:
            version_spec = list(re.match(
                (r'([^=<>]+)(?:(?:([<>]=?|==?)([^<>=,]+))'
                 r'(?:,([<>]=?|==?)([^<>=]+))?)?$'),
                name
            ).groups())
            prefix = version_spec.pop(0)
        except AttributeError:
            ret['result'] = False
            ret['comment'] = 'Invalidly-formatted package {0}'.format(name)
            return ret
        else:
            # Check to see if '=' was used instead of '=='. version_spec will
            # contain two sets of comparison operators and version numbers, so
            # we are checking elements 0 and 2 of this list.
            if any((version_spec[x] == '=' for x in (0, 2))):
                ret['result'] = False
                ret['comment'] = ('Invalid version specification in '
                                  'package {0}. \'=\' is not supported, use '
                                  '\'==\' instead.'.format(name))
                return ret

    if runas is not None:
        # The user is using a deprecated argument, warn!
        msg = (
            'The \'runas\' argument to pip.installed is deprecated, and will '
            'be removed in 0.18.0. Please use \'user\' instead.'
        )
        salt.utils.warn_until((0, 18), msg)
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

    if repo:
        name = repo

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
                comments.append('Requirements file {0} will be '
                                'processed.'.format(requirements))
            if editable:
                comments.append('Package will be installed from VCS checkout '
                                '{0}.'.format(editable))
            ret['comment'] = ' '.join(comments)
            return ret
    else:
        try:
            pip_list = __salt__['pip.list'](prefix, bin_env=bin_env,
                                            user=user, cwd=cwd)
            prefix_realname = _find_key(prefix, pip_list)
        except (CommandNotFoundError, CommandExecutionError) as err:
            ret['result'] = False
            ret['comment'] = 'Error installing \'{0}\': {1}'.format(name, err)
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
        pkgs='"{0}"'.format(name) if name else '',
        requirements=requirements,
        bin_env=bin_env,
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
        user=user,
        no_chown=no_chown,
        cwd=cwd,
        pre_releases=pre_releases,
        __env__=__env__
    )

    if pip_install_call and (pip_install_call['retcode'] == 0):
        ret['result'] = True

        if requirements or editable:
            comments = []
            if requirements:
                comments.append('Successfully processed requirements file '
                                '{0}.'.format(requirements))
                ret['changes']['requirements'] = True
            if editable:
                comments.append('Package successfully installed from VCS '
                                'checkout {0}.'.format(editable))
                ret['changes']['editable'] = True
            ret['comment'] = ' '.join(comments)
        else:
            pkg_list = __salt__['pip.list'](prefix, bin_env,
                                            user=user, cwd=cwd)
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
        error = 'Error: {0} {1}'.format(pip_install_call['stdout'],
                                        pip_install_call['stderr'])

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
            cwd=None,
            __env__='base'):
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
        msg = (
            'The \'runas\' argument to pip.installed is deprecated, and will '
            'be removed in 0.18.0. Please use \'user\' instead.'
        )
        salt.utils.warn_until((0, 18), msg)
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
                                 cwd=cwd,
                                 __env__='base'):
        ret['result'] = True
        ret['changes'][name] = 'Removed'
        ret['comment'] = 'Package was successfully removed.'
    else:
        ret['result'] = False
        ret['comment'] = 'Could not remove package.'
    return ret
