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

import urlparse

# Import salt libs
from salt.exceptions import CommandExecutionError, CommandNotFoundError


def __virtual__():
    '''
    Only load if the pip module is available in __salt__
    '''
    return 'pip' if 'pip.list' in __salt__ else False


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
              no_chown=False,
              cwd=None,
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

    scheme, netloc, path, query, fragment = urlparse.urlsplit(name)
    if scheme and netloc:
        # parse as VCS url
        prefix = path.lstrip('/').split('@', 1)[0]
        if scheme.startswith("git+"):
            prefix = prefix.rstrip(".git")
    else:
        # Pull off any requirements specifiers
        prefix = name.split('=')[0].split('<')[0].split('>')[0].strip()

    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}
    try:
        pip_list = __salt__['pip.list'](prefix, bin_env, user=user, cwd=cwd)
    except (CommandNotFoundError, CommandExecutionError) as err:
        ret['result'] = False
        ret['comment'] = 'Error installing \'{0}\': {1}'.format(name, err)
        return ret

    if ignore_installed is False and prefix.lower() in (p.lower()
                                                        for p in pip_list):
        if force_reinstall is False and upgrade is False:
            ret['result'] = True
            ret['comment'] = 'Package already installed'
            return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Python package {0} is set to be installed'.format(
                name)
        return ret

    # Replace commas (used for version ranges) with semicolons (which are not
    # supported) in name so it does not treat them as multiple packages.  Comma
    # will be re-added in pip.install call.  Wrap in double quotes to allow for
    # version ranges
    name = '"' + name.replace(',', ';') + '"'

    if repo:
        name = repo

    # If a requirements file is specified, only install the contents of the
    # requirements file. Similarly, using the --editable flag with pip should
    # also ignore the "name" parameter.
    if requirements or editable:
        name = ''

    pip_install_call = __salt__['pip.install'](
        pkgs=name,
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
        __env__=__env__
    )

    if pip_install_call and (pip_install_call['retcode'] == 0):
        ret['result'] = True

        pkg_list = __salt__['pip.list'](prefix, bin_env, user=user, cwd=cwd)
        if not pkg_list:
            ret['comment'] = (
                'There was no error installing package \'{0}\' although '
                'it does not show when calling \'pip.freeze\'.'.format(name)
            )
            ret['changes']['{0}==???'.format(name)] = 'Installed'
            return ret

        version = list(pkg_list.values())[0]
        pkg_name = next(iter(pkg_list))
        ret['changes']['{0}=={1}'.format(pkg_name, version)] = 'Installed'
        ret['comment'] = 'Package was successfully installed'
    elif pip_install_call:
        ret['result'] = False
        ret['comment'] = ('Failed to install package {0}. '
                          'Error: {1} {2}').format(name,
                                                   pip_install_call['stdout'],
                                                   pip_install_call['stderr'])
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
