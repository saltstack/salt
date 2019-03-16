# -*- coding: utf-8 -*-
'''
VirtualBox Guest Additions installer state
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging

log = logging.getLogger(__name__)


def additions_installed(name, reboot=False, upgrade_os=False):
    '''
    Ensure that the VirtualBox Guest Additions are installed. Uses the CD,
    connected by VirtualBox.

    name
        The name has no functional value and is only used as a tracking
        reference.
    reboot : False
        Restart OS to complete installation.
    upgrade_os : False
        Upgrade OS (to ensure the latests version of kernel and developer tools
        installed).
    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}
    current_state = __salt__['vbox_guest.additions_version']()
    if current_state:
        ret['result'] = True
        ret['comment'] = 'System already in the correct state'
        return ret
    if __opts__['test']:
        ret['comment'] = ('The state of VirtualBox Guest Additions will be '
                          'changed.')
        ret['changes'] = {
            'old': current_state,
            'new': True,
        }
        ret['result'] = None
        return ret

    new_state = __salt__['vbox_guest.additions_install'](
        reboot=reboot, upgrade_os=upgrade_os)

    ret['comment'] = 'The state of VirtualBox Guest Additions was changed!'
    ret['changes'] = {
        'old': current_state,
        'new': new_state,
    }
    ret['result'] = bool(new_state)
    return ret


def additions_removed(name, force=False):
    '''
    Ensure that the VirtualBox Guest Additions are removed. Uses the CD,
    connected by VirtualBox.

    To connect VirtualBox Guest Additions via VirtualBox graphical interface
    press 'Host+D' ('Host' is usually 'Right Ctrl').

    name
        The name has no functional value and is only used as a tracking
        reference.
    force
        Force VirtualBox Guest Additions removing.
    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}
    current_state = __salt__['vbox_guest.additions_version']()
    if not current_state:
        ret['result'] = True
        ret['comment'] = 'System already in the correct state'
        return ret
    if __opts__['test']:
        ret['comment'] = ('The state of VirtualBox Guest Additions will be '
                          'changed.')
        ret['changes'] = {
            'old': current_state,
            'new': True,
        }
        ret['result'] = None
        return ret

    new_state = __salt__['vbox_guest.additions_remove'](force=force)

    ret['comment'] = 'The state of VirtualBox Guest Additions was changed!'
    ret['changes'] = {
        'old': current_state,
        'new': new_state,
    }
    ret['result'] = bool(new_state)
    return ret


def grant_access_to_shared_folders_to(name, users=None):
    '''
    Grant access to auto-mounted shared folders to the users.

    User is specified by it's name. To grant access for several users use
    argument `users`.

    name
        Name of the user to grant access to auto-mounted shared folders to.
    users
        List of names of users to grant access to auto-mounted shared folders to.
        If specified, `name` will not be taken into account.
    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}
    current_state = __salt__['vbox_guest.list_shared_folders_users']()
    if users is None:
        users = [name]
    if current_state == users:
        ret['result'] = True
        ret['comment'] = 'System already in the correct state'
        return ret
    if __opts__['test']:
        ret['comment'] = ('List of users who have access to auto-mounted '
                          'shared folders will be changed')
        ret['changes'] = {
            'old': current_state,
            'new': users,
        }
        ret['result'] = None
        return ret

    new_state = __salt__['vbox_guest.grant_access_to_shared_folders_to'](
        name=name, users=users)

    ret['comment'] = ('List of users who have access to auto-mounted shared '
                      'folders was changed')
    ret['changes'] = {
        'old': current_state,
        'new': new_state,
    }
    ret['result'] = True
    return ret
