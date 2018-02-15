# -*- coding: utf-8 -*-
'''
Installation of Windows Updates using the Windows Update Agent

.. versionadded:: 2017.7.0

Salt can manage Windows updates via the "wua" state module. Updates can be
installed and removed. Update management declarations are as follows:

For installation:

.. code-block:: yaml

    # Install a single update using the KB
    KB3194343:
      wua.installed

    # Install a single update using the name parameter
    install_update:
      wua.installed:
        - name: KB3194343

    # Install multiple updates using the updates parameter and a combination of
    # KB number and GUID
    install_updates:
      wua.installed:
       - updates:
         - KB3194343
         - bb1dbb26-3fb6-45fd-bb05-e3c8e379195c

For removal:

.. code-block:: yaml

    # Remove a single update using the KB
    KB3194343:
      wua.removed

    # Remove a single update using the name parameter
    remove_update:
      wua.removed:
        - name: KB3194343

    # Remove multiple updates using the updates parameter and a combination of
    # KB number and GUID
    remove_updates:
      wua.removed:
       - updates:
         - KB3194343
         - bb1dbb26-3fb6-45fd-bb05-e3c8e379195c
'''
# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function
import logging

# Import Salt libs
from salt.ext import six
import salt.utils.data
import salt.utils.platform
import salt.utils.win_update

log = logging.getLogger(__name__)

__virtualname__ = 'wua'


def __virtual__():
    '''
    Only valid on Windows machines
    '''
    if not salt.utils.platform.is_windows():
        return False, 'WUA: Only available on Window systems'

    if not salt.utils.win_update.HAS_PYWIN32:
        return False, 'WUA: Requires PyWin32 libraries'

    return __virtualname__


def installed(name, updates=None):
    '''
    Ensure Microsoft Updates are installed. Updates will be downloaded if
    needed.

    Args:

        name (str):
            The identifier of a single update to install.

        updates (list):
            A list of identifiers for updates to be installed. Overrides
            ``name``. Default is None.

    .. note:: Identifiers can be the GUID, the KB number, or any part of the
       Title of the Microsoft update. GUIDs and KBs are the preferred method
       to ensure you're installing the correct update.

    .. warning:: Using a partial KB number or a partial Title could result in
       more than one update being installed.

    Returns:
        dict: A dictionary containing the results of the update

    CLI Example:

    .. code-block:: yaml

        # using a GUID
        install_update:
          wua.installed:
            - name: 28cf1b09-2b1a-458c-9bd1-971d1b26b211

        # using a KB
        install_update:
          wua.installed:
            - name: KB3194343

        # using the full Title
        install_update:
          wua.installed:
            - name: Security Update for Adobe Flash Player for Windows 10 Version 1607 (for x64-based Systems) (KB3194343)

        # Install multiple updates
        install_updates:
          wua.installed:
            - updates:
              - KB3194343
              - 28cf1b09-2b1a-458c-9bd1-971d1b26b211
    '''
    if isinstance(updates, six.string_types):
        updates = [updates]

    if not updates:
        updates = name

    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    wua = salt.utils.win_update.WindowsUpdateAgent()

    # Search for updates
    install_list = wua.search(updates)

    # No updates found
    if install_list.count() == 0:
        ret['comment'] = 'No updates found'
        return ret

    # List of updates to download
    download = salt.utils.win_update.Updates()
    for item in install_list.updates:
        if not salt.utils.data.is_true(item.IsDownloaded):
            download.updates.Add(item)

    # List of updates to install
    install = salt.utils.win_update.Updates()
    installed_updates = []
    for item in install_list.updates:
        if not salt.utils.data.is_true(item.IsInstalled):
            install.updates.Add(item)
        else:
            installed_updates.extend('KB' + kb for kb in item.KBArticleIDs)

    if install.count() == 0:
        ret['comment'] = 'Updates already installed: '
        ret['comment'] += '\n - '.join(installed_updates)
        return ret

    # Return comment of changes if test.
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Updates will be installed:'
        for update in install.updates:
            ret['comment'] += '\n'
            ret['comment'] += ': '.join(
                [update.Identity.UpdateID, update.Title])
        return ret

    # Download updates
    wua.download(download)

    # Install updates
    wua.install(install)

    # Refresh windows update info
    wua.refresh()
    post_info = wua.updates().list()

    # Verify the installation
    for item in install.list():
        if not salt.utils.data.is_true(post_info[item]['Installed']):
            ret['changes']['failed'] = {
                item: {'Title': post_info[item]['Title'][:40] + '...',
                       'KBs': post_info[item]['KBs']}
            }
            ret['result'] = False
        else:
            ret['changes']['installed'] = {
                item: {'Title': post_info[item]['Title'][:40] + '...',
                       'NeedsReboot': post_info[item]['NeedsReboot'],
                       'KBs': post_info[item]['KBs']}
            }

    if ret['changes'].get('failed', False):
        ret['comment'] = 'Updates failed'
    else:
        ret['comment'] = 'Updates installed successfully'

    return ret


def removed(name, updates=None):
    '''
    Ensure Microsoft Updates are uninstalled.

    Args:

        name (str):
            The identifier of a single update to uninstall.

        updates (list):
            A list of identifiers for updates to be removed. Overrides ``name``.
            Default is None.

    .. note:: Identifiers can be the GUID, the KB number, or any part of the
       Title of the Microsoft update. GUIDs and KBs are the preferred method
       to ensure you're uninstalling the correct update.

    .. warning:: Using a partial KB number or a partial Title could result in
       more than one update being removed.

    Returns:
        dict: A dictionary containing the results of the removal

    CLI Example:

    .. code-block:: yaml

        # using a GUID
        uninstall_update:
          wua.removed:
            - name: 28cf1b09-2b1a-458c-9bd1-971d1b26b211

        # using a KB
        uninstall_update:
          wua.removed:
            - name: KB3194343

        # using the full Title
        uninstall_update:
          wua.removed:
            - name: Security Update for Adobe Flash Player for Windows 10 Version 1607 (for x64-based Systems) (KB3194343)

        # Install multiple updates
        uninstall_updates:
          wua.removed:
            - updates:
              - KB3194343
              - 28cf1b09-2b1a-458c-9bd1-971d1b26b211
    '''
    if isinstance(updates, six.string_types):
        updates = [updates]

    if not updates:
        updates = name

    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    wua = salt.utils.win_update.WindowsUpdateAgent()

    # Search for updates
    updates = wua.search(updates)

    # No updates found
    if updates.count() == 0:
        ret['comment'] = 'No updates found'
        return ret

    # List of updates to uninstall
    uninstall = salt.utils.win_update.Updates()
    removed_updates = []
    for item in updates.updates:
        if salt.utils.data.is_true(item.IsInstalled):
            uninstall.updates.Add(item)
        else:
            removed_updates.extend('KB' + kb for kb in item.KBArticleIDs)

    if uninstall.count() == 0:
        ret['comment'] = 'Updates already removed: '
        ret['comment'] += '\n - '.join(removed_updates)
        return ret

    # Return comment of changes if test.
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Updates will be removed:'
        for update in uninstall.updates:
            ret['comment'] += '\n'
            ret['comment'] += ': '.join(
                [update.Identity.UpdateID, update.Title])
        return ret

    # Install updates
    wua.uninstall(uninstall)

    # Refresh windows update info
    wua.refresh()
    post_info = wua.updates().list()

    # Verify the installation
    for item in uninstall.list():
        if salt.utils.data.is_true(post_info[item]['Installed']):
            ret['changes']['failed'] = {
                item: {'Title': post_info[item]['Title'][:40] + '...',
                       'KBs': post_info[item]['KBs']}
            }
            ret['result'] = False
        else:
            ret['changes']['removed'] = {
                item: {'Title': post_info[item]['Title'][:40] + '...',
                       'NeedsReboot': post_info[item]['NeedsReboot'],
                       'KBs': post_info[item]['KBs']}
            }

    if ret['changes'].get('failed', False):
        ret['comment'] = 'Updates failed'
    else:
        ret['comment'] = 'Updates removed successfully'

    return ret


def uptodate(name,
             software=True,
             drivers=False,
             skip_hidden=False,
             skip_mandatory=False,
             skip_reboot=True,
             categories=None,
             severities=None,):
    '''
    Ensure Microsoft Updates that match the passed criteria are installed.
    Updates will be downloaded if needed.

    This state allows you to update a system without specifying a specific
    update to apply. All matching updates will be installed.

    Args:

        name (str):
            The name has no functional value and is only used as a tracking
            reference

        software (bool):
            Include software updates in the results (default is True)

        drivers (bool):
            Include driver updates in the results (default is False)

        skip_hidden (bool):
            Skip updates that have been hidden. Default is False.

        skip_mandatory (bool):
            Skip mandatory updates. Default is False.

        skip_reboot (bool):
            Skip updates that require a reboot. Default is True.

        categories (list):
            Specify the categories to list. Must be passed as a list. All
            categories returned by default.

            Categories include the following:

            * Critical Updates
            * Definition Updates
            * Drivers (make sure you set drivers=True)
            * Feature Packs
            * Security Updates
            * Update Rollups
            * Updates
            * Update Rollups
            * Windows 7
            * Windows 8.1
            * Windows 8.1 drivers
            * Windows 8.1 and later drivers
            * Windows Defender

        severities (list):
            Specify the severities to include. Must be passed as a list. All
            severities returned by default.

            Severities include the following:

            * Critical
            * Important


    Returns:
        dict: A dictionary containing the results of the update

    CLI Example:

    .. code-block:: yaml

        # Update the system using the state defaults
        update_system:
          wua.up_to_date

        # Update the drivers
        update_drivers:
          wua.up_to_date:
            - software: False
            - drivers: True
            - skip_reboot: False

        # Apply all critical updates
        update_critical:
          wua.up_to_date:
            - severities:
              - Critical
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    wua = salt.utils.win_update.WindowsUpdateAgent()

    available_updates = wua.available(
        skip_hidden=skip_hidden, skip_installed=True,
        skip_mandatory=skip_mandatory, skip_reboot=skip_reboot,
        software=software, drivers=drivers, categories=categories,
        severities=severities)

    # No updates found
    if available_updates.count() == 0:
        ret['comment'] = 'No updates found'
        return ret

    updates = list(available_updates.list().keys())

    # Search for updates
    install_list = wua.search(updates)

    # List of updates to download
    download = salt.utils.win_update.Updates()
    for item in install_list.updates:
        if not salt.utils.data.is_true(item.IsDownloaded):
            download.updates.Add(item)

    # List of updates to install
    install = salt.utils.win_update.Updates()
    for item in install_list.updates:
        if not salt.utils.data.is_true(item.IsInstalled):
            install.updates.Add(item)

    # Return comment of changes if test.
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Updates will be installed:'
        for update in install.updates:
            ret['comment'] += '\n'
            ret['comment'] += ': '.join(
                [update.Identity.UpdateID, update.Title])
        return ret

    # Download updates
    wua.download(download)

    # Install updates
    wua.install(install)

    # Refresh windows update info
    wua.refresh()

    post_info = wua.updates().list()

    # Verify the installation
    for item in install.list():
        if not salt.utils.data.is_true(post_info[item]['Installed']):
            ret['changes']['failed'] = {
                item: {'Title': post_info[item]['Title'][:40] + '...',
                       'KBs': post_info[item]['KBs']}
            }
            ret['result'] = False
        else:
            ret['changes']['installed'] = {
                item: {'Title': post_info[item]['Title'][:40] + '...',
                       'NeedsReboot': post_info[item]['NeedsReboot'],
                       'KBs': post_info[item]['KBs']}
            }

    if ret['changes'].get('failed', False):
        ret['comment'] = 'Updates failed'
    else:
        ret['comment'] = 'Updates installed successfully'

    return ret
