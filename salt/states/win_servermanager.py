# -*- coding: utf-8 -*-
'''
Manage Windows features via the ServerManager powershell module. Can install and
remove roles/features.

:maintainer:    Shane Lee <slee@saltstack.com>
:platform:      Windows Server 2008R2 or greater
:depends:       win_servermanager.install
:depends:       win_servermanager.remove
'''
from __future__ import absolute_import, unicode_literals, print_function

# Import salt modules
import salt.utils.data
import salt.utils.versions


def __virtual__():
    '''
    Load only if win_servermanager is loaded
    '''
    return 'win_servermanager' if 'win_servermanager.install' in __salt__ else False


def installed(name,
              features=None,
              recurse=False,
              restart=False,
              source=None,
              exclude=None,
              **kwargs):
    '''
    Install the windows feature. To install a single feature, use the ``name``
    parameter. To install multiple features, use the ``features`` parameter.

    .. note::
        Some features require reboot after un/installation. If so, until the
        server is restarted other features can not be installed!

    Args:

        name (str):
            Short name of the feature (the right column in
            win_servermanager.list_available). This can be a single feature or a
            string of features in a comma delimited list (no spaces)

            .. note::
                A list is not allowed in the name parameter of any state. Use
                the ``features`` parameter if you want to pass the features as a
                list

        features (Optional[list]):
            A list of features to install. If this is passed it will be used
            instead of the ``name`` parameter.

            .. versionadded:: 2018.3.0

        recurse (Optional[bool]):
            Install all sub-features as well. If the feature is installed but
            one of its sub-features are not installed set this will install
            additional sub-features

        source (Optional[str]):
            Path to the source files if missing from the target system. None
            means that the system will use windows update services to find the
            required files. Default is None

        restart (Optional[bool]):
            Restarts the computer when installation is complete, if required by
            the role/feature installed. Default is False

        exclude (Optional[str]):
            The name of the feature to exclude when installing the named
            feature. This can be a single feature, a string of features in a
            comma-delimited list (no spaces), or a list of features.

            .. warning::
                As there is no exclude option for the ``Add-WindowsFeature``
                or ``Install-WindowsFeature`` PowerShell commands the features
                named in ``exclude`` will be installed with other sub-features
                and will then be removed. **If the feature named in ``exclude``
                is not a sub-feature of one of the installed items it will still
                be removed.**

    Example:

        Do not use the role or feature names mentioned in the PKGMGR
        documentation. To get a list of available roles and features run the
        following command:

        .. code-block:: bash

            salt <minion_name> win_servermanager.list_available

        Use the name in the right column of the results.

    .. code-block:: yaml

        # Installs the IIS Web Server Role (Web-Server)
        IIS-WebServerRole:
          win_servermanager.installed:
            - recurse: True
            - name: Web-Server

        # Install multiple features, exclude the Web-Service
        install_multiple_features:
          win_servermanager.installed:
            - recurse: True
            - features:
              - RemoteAccess
              - XPS-Viewer
              - SNMP-Service
            - exclude:
              - Web-Service
    '''
    if 'force' in kwargs:
        salt.utils.versions.warn_until(
            'Flourine',
            'Parameter \'force\' has been detected in the argument list. This'
            'parameter is no longer used and has been replaced by \'recurse\''
            'as of Salt 2018.3.0. This warning will be removed in Salt Flourine.'
        )
        kwargs.pop('force')

    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    # Check if features is not passed, use name. Split commas
    if features is None:
        features = name.split(',')

    # Make sure features is a list, split commas
    if not isinstance(features, list):
        features = features.split(',')

    # Determine if the feature is installed
    old = __salt__['win_servermanager.list_installed']()

    cur_feat = []
    for feature in features:

        if feature not in old:
            ret['changes'][feature] = \
                'Will be installed recurse={0}'.format(recurse)
        elif recurse:
            ret['changes'][feature] = \
                'Already installed but might install sub-features'
        else:
            cur_feat.append(feature)

    if cur_feat:
        cur_feat.insert(0, 'The following features are already installed:')
        ret['comment'] = '\n- '.join(cur_feat)

    if not ret['changes']:
        return ret

    if __opts__['test']:
        ret['result'] = None
        return ret

    # Install the features
    status = __salt__['win_servermanager.install'](
        features, recurse=recurse, restart=restart, source=source,
        exclude=exclude)

    ret['result'] = status['Success']

    # Show items failed to install
    fail_feat = []
    new_feat = []
    rem_feat = []
    for feature in status['Features']:
        # Features that failed to install or be removed
        if not status['Features'][feature].get('Success', True):
            fail_feat.append('- {0}'.format(feature))
        # Features that installed
        elif '(exclude)' not in status['Features'][feature]['Message']:
            new_feat.append('- {0}'.format(feature))
        # Show items that were removed because they were part of `exclude`
        elif '(exclude)' in status['Features'][feature]['Message']:
            rem_feat.append('- {0}'.format(feature))

    if fail_feat:
        fail_feat.insert(0, 'Failed to install the following:')
    if new_feat:
        new_feat.insert(0, 'Installed the following:')
    if rem_feat:
        rem_feat.insert(0, 'Removed the following (exclude):')

    ret['comment'] = '\n'.join(fail_feat + new_feat + rem_feat)

    # Get the changes
    new = __salt__['win_servermanager.list_installed']()
    ret['changes'] = salt.utils.data.compare_dicts(old, new)

    return ret


def removed(name, features=None, remove_payload=False, restart=False):
    '''
    Remove the windows feature To remove a single feature, use the ``name``
    parameter. To remove multiple features, use the ``features`` parameter.

    Args:
        name (str):
            Short name of the feature (the right column in
            win_servermanager.list_available). This can be a single feature or a
            string of features in a comma-delimited list (no spaces)

            .. note::
                A list is not allowed in the name parameter of any state. Use
                the ``features`` parameter if you want to pass the features as a
                list

        features (Optional[list]):
            A list of features to remove. If this is passed it will be used
            instead of the ``name`` parameter.

            .. versionadded:: 2018.3.0

        remove_payload (Optional[bool]):
            True will cause the feature to be removed from the side-by-side
            store. To install the feature in the future you will need to
            specify the ``source``

        restart (Optional[bool]):
            Restarts the computer when uninstall is complete if required by the
            role/feature uninstall. Default is False

    .. note::
        Some features require a reboot after uninstall. If so the feature will
        not be completely uninstalled until the server is restarted.

    Example:

        Do not use the role or feature names mentioned in the PKGMGR
        documentation. To get a list of available roles and features run the
        following command:

        .. code-block:: bash

            salt <minion_name> win_servermanager.list_available

        Use the name in the right column of the results.

    .. code-block:: yaml

        # Uninstall the IIS Web Server Rol (Web-Server)
        IIS-WebserverRole:
          win_servermanager.removed:
            - name: Web-Server

        # Uninstall multiple features, reboot if required
        uninstall_multiple_features:
          win_servermanager.removed:
            - features:
              - RemoteAccess
              - XPX-Viewer
              - SNMP-Service
            - restart: True
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    # Check if features is not passed, use name. Split commas
    if features is None:
        features = name.split(',')

    # Make sure features is a list, split commas
    if not isinstance(features, list):
        features = features.split(',')

    # Determine if the feature is installed
    old = __salt__['win_servermanager.list_installed']()

    rem_feat = []
    for feature in features:

        if feature in old:
            ret['changes'][feature] = 'Will be removed'
        else:
            rem_feat.append(feature)

    if rem_feat:
        rem_feat.insert(0, 'The following features are not installed:')
        ret['comment'] = '\n- '.join(rem_feat)

    if not ret['changes']:
        return ret

    if __opts__['test']:
        ret['result'] = None
        return ret

    # Remove the features
    status = __salt__['win_servermanager.remove'](
        features, remove_payload=remove_payload, restart=restart)

    ret['result'] = status['Success']

    # Some items failed to uninstall
    fail_feat = []
    rem_feat = []
    for feature in status['Features']:
        # Use get because sometimes 'Success' isn't defined such as when the
        # feature is already uninstalled
        if not status['Features'][feature].get('Success', True):
            # Show items that failed to uninstall
            fail_feat.append('- {0}'.format(feature))
        else:
            # Show items that uninstalled
            rem_feat.append('- {0}'.format(feature))

    if fail_feat:
        fail_feat.insert(0, 'Failed to remove the following:')
    if rem_feat:
        rem_feat.insert(0, 'Removed the following:')

    ret['comment'] = '\n'.join(fail_feat + rem_feat)

    # Get the changes
    new = __salt__['win_servermanager.list_installed']()
    ret['changes'] = salt.utils.data.compare_dicts(old, new)

    return ret
