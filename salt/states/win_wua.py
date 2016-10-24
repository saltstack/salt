# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import logging

# Import salt libs
import salt.utils
import salt.utils.win_update
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

__virtualname__ = 'wua'


def __virtual__():
    '''
    Only valid on Windows machines
    '''
    if not salt.utils.is_windows():
        return False, 'WUA: Only available on Window systems'

    if not salt.utils.win_update.HAS_PYWIN32:
        return False, 'WUA: Requires PyWin32 libraries'

    return __virtualname__


def installed(name):
    '''
    Ensure Microsoft Updates are installed.

    Args:

        name (str): Can be the GUID, the KB number, or any part of the
        Title of Microsoft update. GUID is the preferred method to ensure you're
        installing the correct update. Can also be a list of identifiers.

        .. warning:: Using a partial KB number or a partial Title could result
           in more than one update being applied.

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
            - name:
              - KB3194343
              - 28cf1b09-2b1a-458c-9bd1-971d1b26b211
    '''
    if isinstance(name, list) and len(name) == 0:
        return {'name': name,
                'changes': {},
                'result': True,
                'comment': 'No updates provided'}

    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    wua = salt.utils.win_update.WindowsUpdateAgent()

    # Search for updates
    install_list = wua.search(name)

    # No updates found
    if install_list.count() == 0:
        ret['comment'] = 'No updates found'
        return ret

    # List of updates to download
    download = salt.utils.win_update.Updates()
    for item in install_list.updates:
        if not salt.utils.is_true(item.IsDownloaded):
            download.updates.Add(item)

    # List of updates to install
    install = salt.utils.win_update.Updates()
    for item in install_list.updates:
        if not salt.utils.is_true(item.IsInstalled):
            install.updates.Add(item)

    if install.count() == 0:
        ret['comment'] = 'Updates already installed'
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
    wua.download(download.updates)

    # Install updates
    wua.install(install.updates)

    # Refresh windows update info
    wua.refresh()
    post_info = wua.updates().list()

    # Verify the installation
    for item in install.list():
        if not salt.utils.is_true(post_info[item]['Installed']):
            ret['changes']['failed'] = {
                item: {'Title': post_info[item]['Title']}
            }
            ret['result'] = False
            failed.append(item)
        else:
            ret['changes']['installed'] = {
                item: {'Title': post_info[item]['Title'],
                       'NeedsReboot': post_info[item]['NeedsReboot']}
            }
            succeeded.append(item)

    if ret['changes'].get('failed', False):
        ret['comment'] = 'Some updates failed'
    else:
        ret['comment'] = 'Updates completed successfully'

    return ret
