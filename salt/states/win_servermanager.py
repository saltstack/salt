# -*- coding: utf-8 -*-
'''
Manage Windows features via the ServerManager powershell module
'''
from __future__ import absolute_import

# Import salt modules
import salt.utils


def __virtual__():
    '''
    Load only if win_servermanager is loaded
    '''
    return 'win_servermanager' if 'win_servermanager.install' in __salt__ else False


def installed(name,
              recurse=False,
              force=False,
              source=None,
              restart=False,
              exclude=None):
    '''
    Install the windows feature

    Args:
        name (str): Short name of the feature (the right column in
            win_servermanager.list_available)
        recurse (Optional[bool]): install all sub-features as well
        force (Optional[bool]): if the feature is installed but one of its
            sub-features are not installed set this to True to force the
            installation of the sub-features
        source (Optional[str]): Path to the source files if missing from the
            target system. None means that the system will use windows update
            services to find the required files. Default is None
        restart (Optional[bool]): Restarts the computer when installation is
            complete, if required by the role/feature installed. Default is
            False
        exclude (Optional[str]): The name of the feature to exclude when
            installing the named feature.

    Note:
        Some features require reboot after un/installation. If so, until the
        server is restarted other features can not be installed!

    Example:
        Run ``salt MinionName win_servermanager.list_available`` to get a list
        of available roles and features. Use the name in the right column. Do
        not use the role or feature names mentioned in the PKGMGR documentation.
        In this example for IIS-WebServerRole the name to be used is Web-Server.

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
    old = __salt__['win_servermanager.list_installed']()
    if name not in old:
        ret['changes']['feature'] = \
            '{0} will be installed recurse={1}'.format(name, recurse)
    elif force and recurse:
        ret['changes']['feature'] = \
            '{0} already installed but might install sub-features'.format(name)
    else:
        ret['comment'] = 'The feature {0} is already installed'.format(name)
        return ret

    if __opts__['test']:
        ret['result'] = None
        return ret

    if ret['changes']['feature']:
        ret['comment'] = ret['changes']['feature']

    ret['changes'] = {}

    # Install the features
    status = __salt__['win_servermanager.install'](
        name, recurse, source, restart, exclude)

    ret['result'] = status['Success']
    if not ret['result']:
        ret['comment'] = 'Failed to install {0}: {1}'\
            .format(name, status['ExitCode'])

    new = __salt__['win_servermanager.list_installed']()
    changes = salt.utils.compare_dicts(old, new)

    if changes:
        ret['comment'] = 'Installed {0}'.format(name)
        ret['changes'] = status
        ret['changes']['feature'] = changes

    return ret


def removed(name, remove_payload=False, restart=False):
    '''
    Remove the windows feature

    Args:
        name (str): Short name of the feature (the right column in
            win_servermanager.list_available)
        remove_payload (Optional[bool]): True will case the feature to be
            removed from the side-by-side store
        restart (Optional[bool]): Restarts the computer when uninstall is
            complete, if required by the role/feature removed. Default is False

    Note:
        Some features require a reboot after uninstallation. If so the feature
        will not be completely uninstalled until the server is restarted.

    Example:
        Run ``salt MinionName win_servermanager.list_installed`` to get a list
        of all features installed. Use the top name listed for each feature, not
        the indented one. Do not use the role or feature names mentioned in the
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
    old = __salt__['win_servermanager.list_installed']()
    if name in old:
        ret['changes']['feature'] = '{0} will be removed'.format(name)
    else:
        ret['comment'] = 'The feature {0} is not installed'.format(name)
        return ret

    if __opts__['test']:
        ret['result'] = None
        return ret

    ret['changes'] = {}

    # Remove the features
    status = __salt__['win_servermanager.remove'](name, remove_payload, restart)

    ret['result'] = status['Success']
    if not ret['result']:
        ret['comment'] = 'Failed to uninstall the feature {0}'\
            .format(status['ExitCode'])

    new = __salt__['win_servermanager.list_installed']()
    changes = salt.utils.compare_dicts(old, new)

    if changes:
        ret['comment'] = 'Removed {0}'.format(name)
        ret['changes'] = status
        ret['changes']['feature'] = changes

    return ret
