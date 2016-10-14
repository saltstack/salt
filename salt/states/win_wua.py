# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import logging

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)

__virtualname__ = 'wua'


def __virtual__():
    '''
    Only valid on Windows machines
    '''
    if not salt.utils.is_windows():
        return False, 'wua state module failed to load: ' \
                      'Only available on Window systems'

    return __virtualname__


def installed(name):
    '''
    Ensure a single Microsoft Update is installed.

    Args:

        name (str): Can be the GUID, the KB number, or any part of the Title of
            Microsoft update. GUID is the preferred method to ensure you're
            installing the correct update.

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

        # using a KB:
        install_update:
          wua.installed:
            - name: KB3194343

        # using the full Title
        install_update:
          wua.installed:
            - name: Security Update for Adobe Flash Player for Windows 10 Version 1607 (for x64-based Systems) (KB3194343)
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    # Get pre update info
    pre_info = __salt__['win_wua.list_update'](name)

    # No updates found
    if len(pre_info) == 0:
        ret['comment'] = 'No updates found'
        return ret

    # List of updates to install
    install = dict()
    for item in pre_info:
        if not salt.utils.is_true(pre_info[item]['Installed']):
            install[item] = pre_info[item]['Title']

    if not install:
        ret['comment'] = 'Update {0} already installed'.format(name)
        return ret

    # Return comment of changes if test.
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Updates will be installed:'
        for item in install:
            ret['comment'] += '\n'
            ret['comment'] += ': '.join([item, install[item]])
        return ret

    # Install the update
    result = __salt__['win_wua.install_updates'](pre_info.keys())
    print('*' * 68)
    print(result)
    print('*' * 68)

    # Get post update info
    post_info = __salt__['win_wua.list_update'](name)

    # Verify the installation

    for item in install:
        if not salt.utils.is_true(post_info[item]['Installed']):
            ret['changes']['failed'] = {
                item: {'Title': post_info[item]['Title']}
            }
            ret['result'] = False
        else:
            ret['changes']['installed'] = {
                item: {'Title': post_info[item]['Title'],
                       'NeedsReboot': post_info[item]['NeedsReboot']}
            }
            ret['comment'] = 'Update {0} was installed'.format(name)

    return ret
