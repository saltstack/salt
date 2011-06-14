'''
State enforcement for groups
'''

def present(name, gid=None):
    '''
    Ensure that a group is present
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    for lgrp in __salt__['group.getent']():
        # Scan over the groups
        if lgrp['name'] == name:
            # The group is present, is the gid right?
            if gid:
                if lgrp['gid'] == gid:
                    # All good, return likewise
                    ret['comment'] = 'No change'
                    return ret
                else:
                    ret['result'] = __salt__['group.chgid'](name, gid)
                    if ret['result']:
                        ret['comment'] = 'Changed gid to {0} for group {1}'.format(
                                gid, name
                                )
                        ret['changes'] = {{name: gid}}
                        return ret
                    else:
                        ret['comment'] = 'Failed to change gid to {0} for group {1}'.format(
                                gid, name
                                )
                        return ret
            else:
                ret['comment'] = 'Group {0} is already present'.format(name)
                return ret
    # Group is not present, make it!
    ret['result'] = __salt__['group.add'](name, gid)
    if ret['result']:
        ret['changes'] = __salt__['group.info'](name)
        ret['commant'] = 'Added group {0}'.format(name)
        return ret
    else:
        ret['comment'] = 'Failed to apply group {0}'.format(name)
        return ret

