# -*- coding: utf-8 -*-
'''
VirtualBox Guest Additions installer state
'''

# Import python libs
import logging

log = logging.getLogger(__name__)


def additions_installed(name, reboot=False, upgrade_os=True):
    '''
    Ensure that the VirtualBox Guest Additions are installed. Uses the CD,
    connected by VirtualBox.

    name
        The name has no functional value and is only used as a tracking reference
    reboot : False
        Restart OS to complete installation
    upgrade_os : True
        Upgrade OS (to ensure the latests version of kernel and developer tools
        installed)
    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}
    current_state = __salt__['vbox_guest.additions_version']()
    if current_state:
        ret['result'] = True
        ret['comment'] = 'System already in the correct state'
        return ret
    if __opts__['test'] == True:
        ret['comment'] = 'The state of VirtualBox Guest Additions will be changed.'
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
    ret['result'] = True
    return ret


def additions_removed(name, force=False):
    '''
    Ensure that the VirtualBox Guest Additions are removed. Uses the CD,
    connected by VirtualBox.

    name
        The name has no functional value and is only used as a tracking reference
    force
        Force VirtualBox Guest Additions removing
    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}
    current_state = __salt__['vbox_guest.additions_version']()
    if not current_state:
        ret['result'] = True
        ret['comment'] = 'System already in the correct state'
        return ret
    if __opts__['test'] == True:
        ret['comment'] = 'The state of VirtualBox Guest Additions will be changed.'
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
    ret['result'] = True
    return ret
