'''
Manage Windows users with the net user command

NOTE: This currently only works with local user accounts, not domain accounts
'''

from salt._compat import string_types


def __virtual__():
    '''
    Set the user module if the kernel is Windows
    '''
    return 'user' if __grains__['kernel'] == 'Windows' else False


def add(name, uid=None, gid=None, groups=None, home=False, shell=None, system=False):
    '''
    Add a user to the minion

    CLI Example::

        salt '*' user.add name password
    '''
    cmd = 'net user {0} /add'.format(name)
    ret = __salt__['cmd.run_all'](cmd)

    return not ret['retcode']


def delete(name):
    '''
    Remove a user from the minion

    CLI Example::

        salt '*' user.delete name
    '''
    cmd = 'net user {0} /delete'.format(name)
    ret = __salt__['cmd.run_all'](cmd)

    return not ret['retcode']


def setpassword(name, password):
    '''
    Set a user's password

    CLI Example::

        salt '*' user.setpassword name password
    '''
    cmd = 'net user {0} {1}'.format(name, password)
    ret = __salt__['cmd.run_all'](cmd)

    return not ret['retcode']


def addgroup(name, group):
    '''
    Add user to a group

    CLI Example::

        salt '*' user.addgroup username groupname
    '''
    user = info(name)
    if not user:
        return False
    if group in user['groups']:
        return True
    cmd = 'net localgroup {0} {1} /add'.format(group, name)
    ret = __salt__['cmd.run_all'](cmd)

    return not ret['retcode']


def removegroup(name, group):
    '''
    Remove user from a group

    CLI Example::

        salt '*' user.removegroup username groupname
    '''
    user = info(name)
    if not user:
        return False
    if group not in user['groups']:
        return True
    cmd = 'net localgroup {0} {1} /delete'.format(group, name)
    ret = __salt__['cmd.run_all'](cmd)

    return not ret['retcode']


def chhome(name, home):
    '''
    Change the home directory of the user

    CLI Example::

        salt '*' user.chhome foo \\\\fileserver\\home\\foo
    '''
    pre_info = info(name)
    if not pre_info:
        return False
    if home == pre_info['home']:
        return True
    cmd = 'net user {0} /homedir:{1}'.format(name, home)
    __salt__['cmd.run'](cmd)
    post_info = info(name)
    if post_info['home'] != pre_info['home']:
        return post_info['home'] == home
    return False


def chprofile(name, profile):
    '''
    Change the profile directory of the user

    CLI Example::

        salt '*' user.chprofile foo \\\\fileserver\\profiles\\foo
    '''
    pre_info = info(name)
    if not pre_info:
        return False
    if profile == pre_info['profile']:
        return True
    cmd = 'net user {0} /profilepath:{1}'.format(name, profile)
    __salt__['cmd.run'](cmd)
    post_info = info(name)
    if post_info['profile'] != pre_info['profile']:
        return post_info['profile'] == profile
    return False


def chgroups(name, groups, append=False):
    '''
    Change the groups this user belongs to, add append to append the specified
    groups

    CLI Example::

        salt '*' user.chgroups foo wheel,root True
    '''
    if isinstance(groups, string_types):
        groups = groups.split(',')
    ugrps = set(list_groups(name))
    if ugrps == set(groups):
        return True
    if not append:
        for group in list_groups(name):
            cmd = 'net localgroup {0} {1} /delete'.format(group, name)
            __salt__['cmd.run'](cmd)
    for group in groups:
        cmd = 'net localgroup {0} {1} /add'.format(group, name)
        __salt__['cmd.run'](cmd)
    agrps = set(list_groups(name))
    return len(ugrps - agrps) == 0


def info(name):
    '''
    Return user information

    CLI Example::

        salt '*' user.info root
    '''
    ret = {}
    items = {}
    cmd = 'net user {0}'.format(name)
    lines = __salt__['cmd.run'](cmd).split('\n')
    for line in lines:
        if 'name could not be found' in line:
            return False
        if 'successfully' not in line:
            comps = line.split('    ', 1)
            if not len(comps) > 1:
                continue
            items[comps[0].strip()] = comps[1].strip()
    grouplist = []
    groups = items['Local Group Memberships'].split(' ')
    for group in groups:
        if not group:
            continue
        grouplist.append(group.strip('*'))

    ret['fullname'] = items['Full Name']
    ret['name'] = items['User name']
    ret['comment'] = items['Comment']
    ret['active'] = items['Account active']
    ret['logonscript'] = items['Logon script']
    ret['profile'] = items['User profile']
    ret['home'] = items['Home directory']
    ret['groups'] = grouplist

    return ret


def list_groups(name):
    '''
    Return a list of groups the named user belongs to

    CLI Example::

        salt '*' user.list_groups foo
    '''
    ugrp = set()
    try:
        user = info(name)['groups']
    except KeyError:
        return False
    for group in user:
        ugrp.add(group)

    return sorted(list(ugrp))


def getent():
    '''
    Return the list of all info for all users

    CLI Example::

        salt '*' user.getent
    '''
    ret = []
    items = {}
    users = []
    startusers = False
    cmd = 'net user'
    lines = __salt__['cmd.run'](cmd).split('\n')
    for line in lines:
        if '----------' in line:
            startusers = True
            continue
        if startusers:
            if 'successfully' not in line:
                comps = line.split()
                users += comps
                ##if not len(comps) > 1:
                    #continue
                #items[comps[0].strip()] = comps[1].strip()
    #return users
    for user in users:
        stuff = {}
        info = __salt__['user.info'](user)
        uid = __salt__['file.user_to_uid'](info['name'])

        stuff['gid'] = ''
        stuff['groups'] = info['groups']
        stuff['home'] = info['home']
        stuff['name'] = info['name']
        stuff['passwd'] = ''
        stuff['shell'] = ''
        stuff['uid'] = uid

        ret.append(stuff)


    return ret

