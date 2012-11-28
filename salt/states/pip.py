'''
Installation of Python packages using pip.
==========================================

A state module to manage system installed python packages

.. code-block:: yaml

    virtualenvwrapper:
      pip.installed:
        - version: 3.0.1
'''

# Import Salt libs
from salt.exceptions import CommandExecutionError, CommandNotFoundError


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
              no_deps=False,
              no_install=False,
              no_download=False,
              install_options=None,
              user=None,
              cwd=None):
    '''
    Make sure the package is installed

    name
        The name of the python package to install
    pip_bin :  None
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
    try:
        pip_list = __salt__['pip.list'](name, bin_env, runas=user, cwd=cwd)
    except (CommandNotFoundError, CommandExecutionError) as err:
        ret['result'] = False
        ret['comment'] = 'Error installing \'{0}\': {1}'.format(name, err)
        return ret

    if ignore_installed == False and name.lower() in (p.lower() for p in pip_list):
        if force_reinstall == False and upgrade == False:
            ret['result'] = True
            ret['comment'] = 'Package already installed'
            return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Python package {0} is set to be installed'.format(
                name)
        return ret

    if repo:
        name = repo

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
        no_deps=no_deps,
        no_install=no_install,
        no_download=no_download,
        install_options=install_options,
        runas=user,
        cwd=cwd
    )

    if pip_install_call and (pip_install_call['retcode'] == 0):
        ret['result'] = True

        pkg_list = __salt__['pip.list'](name, bin_env, runas=user, cwd=cwd)
        if not pkg_list:
            ret['comment'] = (
                'There was no error installing package \'{0}\' although '
                'it does not show when calling \'pip.freeze\'.'.format(name)
            )
            ret['changes']["{0}==???".format(name)] = 'Installed'
            return ret

        version = list(pkg_list.values())[0]
        pkg_name = next(iter(pkg_list))
        ret['changes']["{0}=={1}".format(pkg_name, version)] = 'Installed'
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
            packages=None,
            requirements=None,
            bin_env=None,
            log=None,
            proxy=None,
            timeout=None,
            user=None,
            cwd=None):
    """
    Make sure that a package is not installed.

    name
        The name of the package to uninstall
    bin_env : None
        the pip executable or virtualenenv to use
    """

    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    try:
        pip_list = __salt__["pip.list"](bin_env=bin_env, runas=user, cwd=cwd)
    except (CommandExecutionError, CommandNotFoundError) as err:
        ret['result'] = False
        ret['comment'] = 'Error uninstalling \'{0}\': {1}'.format(name, err)
        return ret

    if name not in pip_list:
        ret["result"] = True
        ret["comment"] = "Package is not installed."
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Package {0} is set to be removed'.format(name)
        return ret

    if __salt__["pip.uninstall"](pkgs=name,
                                 requirements=requirements,
                                 bin_env=bin_env,
                                 log=log,
                                 proxy=proxy,
                                 timeout=timeout,
                                 runas=user,
                                 cwd=cwd):
        ret["result"] = True
        ret["changes"][name] = "Removed"
        ret["comment"] = "Package was successfully removed."
    else:
        ret["result"] = False
        ret["comment"] = "Could not remove package."
    return ret
