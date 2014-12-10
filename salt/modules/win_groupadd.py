# -*- coding: utf-8 -*-
'''
Manage groups on Windows
'''

from __future__ import absolute_import

import salt.utils
from salt.ext.six import string_types

try:
    import win32com.client
    import win32security
    import pythoncom
    import pywintypes
    import wmi
    HAS_DEPENDENCIES = True
except ImportError:
    HAS_DEPENDENCIES = False

# Define the module's virtual name
__virtualname__ = 'group'


def __virtual__():
    '''
    Set the group module if the kernel is Windows
    '''
    if salt.utils.is_windows() and HAS_DEPENDENCIES:
        return __virtualname__
    else:
        return False


def add(name, gid=None, system=False):
    '''
    Add the specified group

    CLI Example:

    .. code-block:: bash

        salt '*' group.add foo
    '''
    ret = {'name': name,
           'result': True,
           'changes': [],
           'comment': ''}

    if not info(name):
        pythoncom.CoInitialize()
        nt = win32com.client.Dispatch('AdsNameSpaces')
        try:
            ldapProvider = False
            if "dc=" in name.lower():
                compObj = nt.GetObject('', 'LDAP://' + name[(name.find(',') + 1):len(name)])
                addGroupName = name[0:(name.find(','))]
                ldapProvider = True
            else:
                compObj = nt.GetObject('', 'WinNT://.,computer')
                addGroupName = name
            newGroup = compObj.Create('group', addGroupName)
            if ldapProvider:
                newGroup.sAMAccountName = addGroupName.replace('cn=', '').replace('CN=', '')
            newGroup.SetInfo()
            ret['changes'].append((
                    'Successfully created group {0}'
                    ).format(name))
        except pywintypes.com_error as com_err:
            friendly_error = ''
            if len(com_err.excepinfo) >= 2:
                if com_err.excepinfo[2]:
                    friendly_error = com_err.excepinfo[2].rstrip('\r\n')
            ret['comment'] = (
                    'Failed to create group {0}.  {1}'
                    ).format(name, friendly_error)
            ret['result'] = False
    else:
        ret['result'] = None
        ret['comment'] = (
                'The group {0} already exists.'
                ).format(name)

    return ret


def delete(name):
    '''
    Remove the named group

    CLI Example:

    .. code-block:: bash

        salt '*' group.delete foo
    '''
    ret = {'name': name,
           'result': True,
           'changes': [],
           'comment': ''}

    if info(name):
        pythoncom.CoInitialize()
        nt = win32com.client.Dispatch('AdsNameSpaces')
        try:
            if "dc=" in name.lower():
                compObj = nt.GetObject('', 'LDAP://' + name[(name.find(',') + 1):len(name)])
                delGroupName = name[0:(name.find(','))]
            else:
                compObj = nt.GetObject('', 'WinNT://.,computer')
                delGroupName = name
            compObj.Delete('group', delGroupName)
            ret['changes'].append(('Successfully removed group {0}').format(name))
        except pywintypes.com_error as com_err:
            friendly_error = ''
            if len(com_err.excepinfo) >= 2:
                if com_err.excepinfo[2]:
                    friendly_error = com_err.excepinfo[2].rstrip('\r\n')
            ret['comment'] = (
                    'Failed to remove group {0}.  {1}'
                    ).format(name, friendly_error)
            ret['result'] = False
    else:
        ret['result'] = None
        ret['comment'] = (
                'The group {0} does not exists.'
                ).format(name)

    return ret


def info(name):
    '''
    Return information about a group

    CLI Example:

    .. code-block:: bash

        salt '*' group.info foo
    '''
    pythoncom.CoInitialize()
    nt = win32com.client.Dispatch('AdsNameSpaces')

    try:
        if "dc=" in name.lower():
            groupObj = nt.GetObject('', 'LDAP://' + name)
            gr_name = groupObj.cn
            gr_mem = []
            for member in groupObj.members():
                gr_mem.append(member.distinguishedName)
        else:
            name = name[(name.find('\\') + 1):]
            groupObj = nt.GetObject('', 'WinNT://./' + name + ',group')
            gr_name = groupObj.Name
            gr_mem = []
            for member in groupObj.members():
                gr_mem.append(
                        _getnetbiosusernamefromsid(member.AdsPath))
        gid = win32security.ConvertSidToStringSid(pywintypes.SID(groupObj.objectSID))
    except pywintypes.com_error:
        return False

    if not gr_name:
        return False

    return {'name': gr_name,
            'passwd': None,
            'gid': gid,
            'members': gr_mem}


def getent(refresh=False):
    '''
    Return info on all groups

    CLI Example:

    .. code-block:: bash

        salt '*' group.getent
    '''
    if 'group.getent' in __context__ and not refresh:
        return __context__['group.getent']

    ret = []

    pythoncom.CoInitialize()
    nt = win32com.client.Dispatch('AdsNameSpaces')

    results = nt.GetObject('', 'WinNT://.')
    results.Filter = ['group']
    for result in results:
        if 'dc=' in result.AdsPath.lower():
            ret.append(info(result.distinguishedName))
        else:
            ret.append(info(result.name))

    __context__['group.getent'] = ret
    return ret


def adduser(name, username):
    '''
    add a user to a group

    CLI Example:

    .. code-block:: bash

        salt '*' group.adduser foo username

    '''

    ret = {'name': name,
           'result': True,
           'changes': {'Users Added': []},
           'comment': ''}

    pythoncom.CoInitialize()
    nt = win32com.client.Dispatch('AdsNameSpaces')

    current_info = info(name)
    if current_info:
        if 'dc=' in name.lower():
            groupObj = nt.GetObject('', 'LDAP://' + name)
        else:
            groupObj = nt.GetObject('', 'WinNT://./' + current_info['name'] + ',group')

        username = _fixlocaluser(username)
        try:
            if username.lower() not in [x.lower() for x in current_info['members']]:
                if 'dc=' in username.lower():
                    groupObj.Add('LDAP://' + username)
                else:
                    # have to use a different ADSPath when adding/removing users to Domain Groups...
                    with salt.utils.winapi.Com():
                        c = wmi.WMI()
                        for wmiComp in c.Win32_ComputerSystem():
                            if wmiComp.DomainRole < 4:
                                groupObj.Add('WinNT://' + username.replace('\\', '/'))
                            else:
                                groupObj.Add(
                                        nt.GetObject(
                                        '', 'WinNT://./' + username[(
                                        username.find('\\') + 1):]).AdsPath)

                ret['changes']['Users Added'].append(username)
            else:
                ret['comment'] = (
                        'User {0} is already a member of {1}'
                        ).format(username, name)
                ret['result'] = None
        except pywintypes.com_error as com_err:
            friendly_error = ''
            if len(com_err.excepinfo) >= 2:
                if com_err.excepinfo[2]:
                    friendly_error = com_err.excepinfo[2].rstrip('\r\n')
            ret['comment'] = (
                    'Failed to add {0} to group {1}.  {2}'
                    ).format(username, name, friendly_error)
            ret['result'] = False
    else:
        ret['result'] = False
        ret['comment'] = ((
                'Group {0} does not appear to exist'
                ).format(name))
    return ret


def deluser(name, username):
    '''
    remove a user from a group

    CLI Example:

    .. code-block:: bash

        salt '*' group.deluser foo username

    '''

    ret = {'name': name,
           'result': True,
           'changes': {'Users Removed': []},
           'comment': ''}

    pythoncom.CoInitialize()
    nt = win32com.client.Dispatch('AdsNameSpaces')

    try:
        current_info = info(name)
        if current_info:
            if 'dc=' in name.lower():
                groupObj = nt.GetObject('', 'LDAP://' + name)
            else:
                groupObj = nt.GetObject('', 'WinNT://./' + current_info['name'] + ',group')

            username = _fixlocaluser(username)
            if username.lower() in [x.lower() for x in current_info['members']]:
                if 'dc=' in username.lower():
                    groupObj.Remove('LDAP://' + username)
                else:
                    # have to use a different ADSPath when adding/removing users to Domain Groups...
                    with salt.utils.winapi.Com():
                        c = wmi.WMI()
                        for wmiComp in c.Win32_ComputerSystem():
                            if wmiComp.DomainRole < 4:
                                groupObj.Remove('WinNT://' + username.replace('\\', '/'))
                            else:
                                groupObj.Remove(
                                        nt.GetObject('', 'WinNT://./' + username[(
                                        username.find('\\') + 1):]).AdsPath)

                ret['changes']['Users Removed'].append(username)
            else:
                ret['comment'] = (
                        'User {0} is not a member of {1}'
                        ).format(username, name)
                ret['result'] = None
        else:
            ret['comment'] = (
                'Group {0} does not appear to exist.'
                ).format(name)
            ret['result'] = False
    except pywintypes.com_error as com_err:
        friendly_error = ''
        if len(com_err.excepinfo) >= 2:
            if com_err.excepinfo[2]:
                friendly_error = com_err.excepinfo[2].rstrip('\r\n')
        ret['comment'] = (
                'Failed to remove {0} from group {1}.  {2}'
                ).format(username, name, friendly_error)
        ret['result'] = False

    return ret


def members(name, members_list):
    '''
    remove a user from a group

    CLI Example:

    .. code-block:: bash

        salt '*' group.members foo 'user1,user2,user3'

        if using LDAP DNs, usernames must be seperated with a ", "

        salt '*' group.members name='cn=foo,dc=domain,dc=com' members_list='cn=user1,cn=Users,dc=domain,dc=com, cn=user2,ou=Test,dc=domain,dc=com'

    '''

    ret = {'name': name,
           'result': True,
           'changes': {'Users Added': [], 'Users Removed': []},
           'comment': []}

    if isinstance(members_list, string_types):
        if 'dc=' in members_list.lower():
            members_list = members_list.split(", ")
        else:
            members_list = [_fixlocaluser(thisMember) for thisMember in members_list.split(",")]

    if not isinstance(members_list, list):
        ret['result'] = False
        ret['comment'].append('Members is not a list object')
        return ret

    current_info = info(name)
    if current_info:
        if sorted([x.lower() for x in current_info['members']]) == sorted([x.lower() for x in members_list]):
            ret['result'] = None
            ret['comment'].append(('{0} membership is correct').format(name))
        else:
            # add missing users
            for member in members_list:
                if member.lower() not in [x.lower() for x in current_info['members']]:
                    this_return = adduser(name, member)
                    if this_return['result']:
                        ret['changes']['Users Added'] += this_return['changes']['Users Added']
                    else:
                        ret['result'] = False
                        ret['comment'].append(this_return['comment'])
            # remove users not in the list
            for member in current_info['members']:
                if member.lower() not in [x.lower() for x in members_list]:
                    this_return = deluser(name, member)
                    if this_return['result']:
                        ret['changes']['Users Removed'] += this_return['changes']['Users Removed']
                    else:
                        ret['result'] = False
                        ret['comment'].append(this_return['comment'])
    else:
        ret['comment'] = (
            'Group {0} does not appear to exist.'
            ).format(name)
        ret['result'] = False

    return ret


def list_groups(useldap=False):
    '''
    Return a list of groups on Windows

    set 'useldap' to True to connect to the local LDAP server
    '''
    ret = []

    pythoncom.CoInitialize()
    nt = win32com.client.Dispatch('AdsNameSpaces')

    if useldap:
        # try to recurse through the ldap server and get all user objects...
        # could do 'LDAP:' and allow any domain member the ability to get all ldap users
        # if anonymous binds are allowed, but for now, the code will try to connect to ldap on the local
        # host
        ret = _recursecontainersforgroups('LDAP://localhost')
    else:
        results = nt.GetObject('', 'WinNT://.')
        results.Filter = ['group']
        for result in results:
            ret.append(_getnetbiosusernamefromsid(result.AdsPath))
    __context__['list_users'] = ret
    return ret


def _recursecontainersforgroups(path):
    '''
    recursively get all group objects in all sub-containers from a top level container
    for example:
            _recursecontainersfrorgroups('LDAP:')
            would find all group objects in a domain via ldap
    '''
    pythoncom.CoInitialize()
    nt = win32com.client.Dispatch('AdsNameSpaces')
    ret = []
    results = None
    try:
        results = nt.GetObject('', path)
    except pywintypes.com_error as com_err:
        pass

    if results:
        for result in results:
            if result.Class.lower() == 'group':
                ret.append(result.distinguishedName)
            else:
                ret = ret + (_recursecontainersforgroups(result.AdsPath))

    return ret


def _fixlocaluser(username):
    '''
    prefixes a username w/o a backslash with the computername or domain name

    i.e. _fixlocaluser('Administrator') would return 'computername\administrator'
    '''
    if 'dc=' not in username.lower():
        if '\\' not in username:
            try:
                pythoncom.CoInitialize()
                nt = win32com.client.Dispatch('AdsNameSpaces')
                user_info = win32security.LookupAccountSid(
                    None, pywintypes.SID(nt.GetObject('', 'WinNT://./' + username).objectSID))
                username = (('{0}\\{1}').format(user_info[1], user_info[0]))
            except Exception:
                username = ('{0}\\{1}').format(__salt__['grains.get']('host').upper(), username)

    return username


def _getnetbiosusernamefromsid(adspath):
    '''
    gets the "domain\\username" of an adspath using the SID
    '''

    if 'NT AUTHORITY'.upper() in adspath.upper():
        return adspath.replace('WinNT://', '').replace('/', '\\')
    else:
        try:
            pythoncom.CoInitialize()
            nt = win32com.client.Dispatch('AdsNameSpaces')
            user_info = win32security.LookupAccountSid(
                    None, pywintypes.SID(nt.GetObject('', adspath).objectSID))
            return ('{0}\\{1}').format(user_info[1], user_info[0])
        except Exception:
            return adspath.replace('WinNT://', '').replace('/', '\\')
