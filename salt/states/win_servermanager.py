# -*- coding: utf-8 -*-
'''
Manage Windows features via the ServerManager powershell module
'''


def __virtual__():
    '''
    Load only if win_servermanager is loaded
    '''
    return 'win_servermanager' if 'win_servermanager.install' in __salt__ else False


def installed(name, recurse=False, force=False):
    '''
    Install the windows feature

    name:
        short name of the feature (the right column in win_servermanager.list_available)

    recurse:
        install all sub-features as well

    force:
        if the feature is installed but on of its sub-features are not installed set this to True to force
        the installation of the sub-features

    Note:
    Some features requires reboot after un/installation, if so until the server is restarted
    Other features can not be installed !
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    # Determine if the feature is installed
    if name not in __salt__['win_servermanager.list_installed']():
        ret['changes'] = {'feature': '{0} will be installed recurse={1}'.format(name, recurse)}
    elif force and recurse:
        ret['changes'] = {'feature': 'already installed but might install sub-features'.format(name)}
    else:
        ret['comment'] = 'The feature {0} is already installed'.format(name)
        return ret

    if __opts__['test']:
        ret['result'] = None
        return ret

    # Install the features
    ret['changes'] = {'feature': __salt__['win_servermanager.install'](name, recurse)}
    ret['result'] = ret['changes']['feature']['Success'] == 'True'
    if not ret['result']:
        ret['comment'] = 'failed to install the feature: {0}'.format(ret['changes']['feature']['ExitCode'])

    return ret
