# -*- coding: utf-8 -*-
'''
Manage Windows features via the ServerManager powershell module
'''


def __virtual__():
    '''
    Load only if win_servermanager is loaded
    '''
    return 'win_servermanager' if 'win_servermanager.install' in __salt__ else False


def installed(name, recurse=False, force=False, restart=False):
    '''
    Install the windows feature

    name:
        short name of the feature (the right column in win_servermanager.list_available)

    recurse:
        install all sub-features as well

    force:
        if the feature is installed but on of its sub-features are not installed set this to True to force
        the installation of the sub-features

    restart:
        Restarts the computer when installation is complete, if restarting is required by the role feature installed.

    Note:
    Some features require reboot after un/installation. If so, until the server is restarted
    other features can not be installed!

    Example:

    Run ``salt MinionName win_servermanager.list_available`` to get a list of available roles and features. Use
    the name in the right column. Do not use the role or feature names mentioned in the PKGMGR documentation. In
    this example for IIS-WebServerRole the name to be used is Web-Server.

    .. code-block:: yaml

        ISWebserverRole:
          win_servermanager.installed:
            - force: True
            - recurse: True
            - name: Web-Server
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    # Determine if the feature is installed
    if name not in __salt__['win_servermanager.list_installed']():
        ret['changes'] = {'feature': '{0} will be installed recurse={1}'.format(name, recurse)}
    elif force and recurse:
        ret['changes'] = {'feature': '{0} already installed but might install sub-features'.format(name)}
    else:
        ret['comment'] = 'The feature {0} is already installed'.format(name)
        return ret

    if __opts__['test']:
        ret['result'] = None
        return ret

    # Install the features
    ret['changes'] = {'feature': __salt__['win_servermanager.install'](name, recurse, restart)}

    if 'Success' in ret['changes']['feature']:
        ret['result'] = ret['changes']['feature']['Success']
        if not ret['result']:
            ret['comment'] = 'Failed to install {0}: {1}'.format(name, ret['changes']['feature']['ExitCode'])
        else:
            ret['comment'] = 'Installed {0}'.format(name)
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to install {0}.\nError Message:\n{1}'.format(name, ret['changes']['feature'])
        ret['changes'] = {}

    return ret


def removed(name):
    '''
    Remove the windows feature

    name:
        short name of the feature (the right column in win_servermanager.list_available)

    .. note::

        Some features require a reboot after uninstallation. If so the feature will not be completely uninstalled until
        the server is restarted.

    Example:

    Run ``salt MinionName win_servermanager.list_installed`` to get a list of all features installed. Use the top
    name listed for each feature, not the indented one. Do not use the role or feature names mentioned in the
    PKGMGR documentation.

    .. code-block:: yaml

        ISWebserverRole:
          win_servermanager.removed:
            - name: Web-Server
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}
    # Determine if the feature is installed
    if name in __salt__['win_servermanager.list_installed']():
        ret['changes'] = {'feature': '{0} will be removed'.format(name)}
    else:
        ret['comment'] = 'The feature {0} is not installed'.format(name)
        return ret

    if __opts__['test']:
        ret['result'] = None
        return ret

    # Remove the features
    ret['changes'] = {'feature': __salt__['win_servermanager.remove'](name)}
    ret['result'] = ret['changes']['feature']['Success']
    if not ret['result']:
        ret['comment'] = 'Failed to uninstall the feature {0}'.format(ret['changes']['feature']['ExitCode'])

    return ret
