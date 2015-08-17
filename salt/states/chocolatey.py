# -*- coding: utf-8 -*-

'''
Manage Chocolatey package installs
.. versionadded:: Boron
'''


def __virtual__():
    '''
    Load only if chocolatey is loaded
    '''
    return 'chocolatey' if 'chocolatey.install' in __salt__ else False


def install(name, version=None, source=None, force=False, install_args=None,
            override_args=False, force_x86=False):

    '''
    Installs a package if not already installed

    name
      The name of the package to be installed.

    version
      Install a specific version of the package. Defaults to latest version.

    source
      Chocolatey repository (directory, share or remote URL, feed). Defaults to
      the official Chocolatey feed.

    force
      Reinstall the current version of an existing package. Default is false.

    install_args
      A list of install arguments you want to pass to the installation
      process i.e product key or feature list

    override_args
      Set to true if you want to override the original install arguments (
      for the native installer)in the package and use your own.
      When this is set to False install_args will be appended to the end of
      the default arguments

    force_x86
      Force x86 (32bit) installation on 64 bit systems. Defaults to false.

    .. code-block:: yaml

        Installsomepackage:
          chocolatey.install:
            - name: packagename
            - version: '12.04'
            - source: 'mychocolatey/source'
            - force: True

    '''

    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    # Determine if the package is installed
    if name not in __salt__['cmd.run']('choco list --local-only'):
        ret['changes'] = {'name': '{0} will be installed'.format(name)}
    elif force:
        ret['changes'] = {'name': '{0} is already installed but will reinstall'
            .format(name)}
    else:
        ret['comment'] = 'The Package {0} is already installed'.format(name)
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'The installation was tested'
        return ret

    # Install the package
    ret['changes'] = {name: __salt__['chocolatey.install'](name, version,
                                                             source,
                                                             force,
                                                             install_args,
                                                             override_args,
                                                             force_x86)}

    if 'Running chocolatey failed' not in ret['changes']:
        ret['result'] = True
    else:
        ret['result'] = False

    if not ret['result']:
        ret['comment'] = 'Failed to install the package {0}'.format(name)

    return ret


def uninstall(name, version=None, uninstall_args=None, override_args=False):
    '''
    Uninstalls a package

    name
      The name of the package to be uninstalled

    version
      Uninstalls a specific version of the package. Defaults to latest
      version installed.

    uninstall_args
      A list of uninstall arguments you want to pass to the uninstallation
      process i.e product key or feature list

    override_args
      Set to true if you want to override the original uninstall arguments (
      for the native uninstaller)in the package and use your own.
      When this is set to False uninstall_args will be appended to the end of
      the default arguments

    .. code-block: yaml

      Removemypackage:
        chocolatey.uninstall:
          - name: mypackage
          - version: '21.5'

    '''

    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    # Determine if package is installed
    if name in __salt__['cmd.run']('choco list --local-only'):
        ret['changes'] = {'name': '{0} will be removed'.format(name)}
    else:
        ret['comment'] = 'The package {0} is not installed'.format(name)
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'The uninstall was tested'
        return ret

    # Uninstall the package
    ret['changes'] = {name: __salt__['chocolatey.uninstall'](name,
                                                               version,
                                                               uninstall_args,
                                                               override_args)}

    if 'Running chocolatey failed' not in ret['changes']:
        ret['result'] = True
    else:
        ret['result'] = False

    if not ret['result']:
        ret['comment'] = 'Failed to uninstall the package {0}'.format(name)

    return ret
