'''
State for configuring Windows Firewall
'''


def __virtual__():
    '''
    Load if the module firewall is loaded
    '''

    return 'firewall' if 'firewall.get_fw_config' in __salt__ else False


def fw_disabled(name):
    '''
    Disable all the firewall profiles (Windows only)
    '''
    
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}
    
    # Validate Windows
    if not salt.utils.is_windows():
        ret['result'] = False
        ret['comment'] = 'This state is supported only on Windows'
        return ret
    
    # Determine what to do
    action = False
    current_config = __salt__['firewall.get_fw_config']()
    for key in current_config:
        if current_config[key]:
            action = True
            ret['changes'] = {'fw': 'disabled'}
            break
    
    if __opts__['test']:
        return ret
    
    # Disable it
    if action:
        ret['result'] = __salt__['firewall.disable_fw']()
        if not ret['result']:
            ret['comment'] = 'could not disable the FW'
    else:
        ret['comment'] = 'all the firewall profiles are disabled'
    
    return ret


