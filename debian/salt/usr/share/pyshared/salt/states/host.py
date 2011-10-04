'''
Manage the state of the hosts file
'''

def present(name, ip):
    '''
    Ensures that the named host is present with the given ip
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}
    if __salt__['hosts.has_pair'](ip, name):
        ret['result'] = True
        ret['comment'] = 'Host {0} already present'.format(name)
        return ret
    if __salt__['hosts.add_host'](ip, name):
        ret['changes'] = {'host': name}
        ret['result'] = True
        ret['comment'] = 'Added host {0}'.format(name)
        return ret
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to set host'
        return ret

def absent(name, ip):
    '''
    Ensure that the the named host is absent
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}
    if not __salt__['hosts.has_pair'](ip, name):
        ret['result'] = True
        ret['comment'] = 'Host {0} already absent'.format(name)
        return ret
    if __salt__['hosts.rm_host'](ip, name):
        ret['changes'] = {'host': name}
        ret['result'] = True
        ret['comment'] = 'Removed host {0}'.format(name)
        return ret
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to remove host'
        return ret

