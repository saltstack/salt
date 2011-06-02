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
        ret['changes'] = 'Already Present'
        ret['result'] = True
        return ret
    if __salt__['hosts.add_host'](ip, name):
        ret['changes'] = {'host': name}
        ret['result'] = True
        ret['comment'] = 'Added host ' + name
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
        ret['changes'] = 'Already Absent'
        ret['result'] = True
        return ret
    if __salt__['hosts.rm_host'](ip, name):
        ret['changes'] = {'host': name}
        ret['result'] = True
        ret['comment'] = 'Removed host ' + name
        return ret
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to remove host'
        return ret

