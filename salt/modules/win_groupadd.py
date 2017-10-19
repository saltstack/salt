# -*- coding: utf-8 -*-
'''
Manage groups on Windows

.. important::
    If you feel that Salt should be using this module to manage groups on a
    minion, and it is using a different module (or gives an error similar to
    *'group.info' is not available*), see :ref:`here
    <module-provider-override>`.
'''
from __future__ import absolute_import

# Import Salt libs
import salt.utils.platform
import salt.utils.win_functions


try:
    import win32com.client
    import pythoncom
    import pywintypes
    HAS_DEPENDENCIES = True
except ImportError:
    HAS_DEPENDENCIES = False

# Define the module's virtual name
__virtualname__ = 'group'


def __virtual__():
    '''
    Set the group module if the kernel is Windows
    '''
    if salt.utils.platform.is_windows() and HAS_DEPENDENCIES:
        return __virtualname__
    return (False, "Module win_groupadd: module only works on Windows systems")


def add(name, **kwargs):
    '''
    Add the specified group

    Args:

        name (str):
            The name of the group to add

    Returns:
        dict: A dictionary of results

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
            compObj = nt.GetObject('', 'WinNT://.,computer')
            newGroup = compObj.Create('group', name)
            newGroup.SetInfo()
            ret['changes'].append('Successfully created group {0}'.format(name))
        except pywintypes.com_error as com_err:
            ret['result'] = False
            if len(com_err.excepinfo) >= 2:
                friendly_error = com_err.excepinfo[2].rstrip('\r\n')
            ret['comment'] = 'Failed to create group {0}. {1}' \
                             ''.format(name, friendly_error)
    else:
        ret['result'] = None
        ret['comment'] = 'The group {0} already exists.'.format(name)

    return ret


def delete(name, **kwargs):
    '''
    Remove the named group

    Args:

        name (str):
            The name of the group to remove

    Returns:
        dict: A dictionary of results

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
            compObj = nt.GetObject('', 'WinNT://.,computer')
            compObj.Delete('group', name)
            ret['changes'].append(('Successfully removed group {0}').format(name))
        except pywintypes.com_error as com_err:
            ret['result'] = False
            if len(com_err.excepinfo) >= 2:
                friendly_error = com_err.excepinfo[2].rstrip('\r\n')
            ret['comment'] = (
                    'Failed to remove group {0}.  {1}'
                    ).format(name, friendly_error)
    else:
        ret['result'] = None
        ret['comment'] = (
                'The group {0} does not exists.'
                ).format(name)

    return ret


def info(name):
    '''
    Return information about a group

    Args:

        name (str):
            The name of the group for which to get information

    Returns:
        dict: A dictionary of information about the group

    CLI Example:

    .. code-block:: bash

        salt '*' group.info foo
    '''
    pythoncom.CoInitialize()
    nt = win32com.client.Dispatch('AdsNameSpaces')

    try:
        groupObj = nt.GetObject('', 'WinNT://./' + name + ',group')
        gr_name = groupObj.Name
        gr_mem = []
        for member in groupObj.members():
            gr_mem.append(
                    member.ADSPath.replace('WinNT://', '').replace(
                    '/', '\\').encode('ascii', 'backslashreplace'))
    except pywintypes.com_error:
        return False

    if not gr_name:
        return False

    return {'name': gr_name,
            'passwd': None,
            'gid': None,
            'members': gr_mem}


def getent(refresh=False):
    '''
    Return info on all groups

    Args:

        refresh (bool):
            Refresh the info for all groups in ``__context__``. If False only
            the groups in ``__context__`` wil be returned. If True the
            ``__context__`` will be refreshed with current data and returned.
            Default is False

    Returns:
        A list of groups and their information

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
        member_list = []
        for member in result.members():
            member_list.append(
                    member.AdsPath.replace('WinNT://', '').replace(
                    '/', '\\').encode('ascii', 'backslashreplace'))
        group = {'gid': __salt__['file.group_to_gid'](result.name),
                'members': member_list,
                'name': result.name,
                'passwd': 'x'}
        ret.append(group)
    __context__['group.getent'] = ret
    return ret


def adduser(name, username, **kwargs):
    '''
    Add a user to a group

    Args:

        name (str):
            The name of the group to modify

        username (str):
            The name of the user to add to the group

    Returns:
        dict: A dictionary of results

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
    groupObj = nt.GetObject('', 'WinNT://./' + name + ',group')
    existingMembers = []
    for member in groupObj.members():
        existingMembers.append(
                member.ADSPath.replace('WinNT://', '').replace(
                '/', '\\').encode('ascii', 'backslashreplace').lower())

    try:
        if salt.utils.win_functions.get_sam_name(username) not in existingMembers:
            if not __opts__['test']:
                groupObj.Add('WinNT://' + username.replace('\\', '/'))

            ret['changes']['Users Added'].append(username)
        else:
            ret['comment'] = (
                    'User {0} is already a member of {1}'
                    ).format(username, name)
            ret['result'] = None
    except pywintypes.com_error as com_err:
        if len(com_err.excepinfo) >= 2:
            friendly_error = com_err.excepinfo[2].rstrip('\r\n')
        ret['comment'] = (
                'Failed to add {0} to group {1}.  {2}'
                ).format(username, name, friendly_error)
        ret['result'] = False
        return ret

    return ret


def deluser(name, username, **kwargs):
    '''
    Remove a user from a group

    Args:

        name (str):
            The name of the group to modify

        username (str):
            The name of the user to remove from the group

    Returns:
        dict: A dictionary of results

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
    groupObj = nt.GetObject('', 'WinNT://./' + name + ',group')
    existingMembers = []
    for member in groupObj.members():
        existingMembers.append(
                member.ADSPath.replace('WinNT://', '').replace(
                '/', '\\').encode('ascii', 'backslashreplace').lower())

    try:
        if salt.utils.win_functions.get_sam_name(username) in existingMembers:
            if not __opts__['test']:
                groupObj.Remove('WinNT://' + username.replace('\\', '/'))

            ret['changes']['Users Removed'].append(username)
        else:
            ret['comment'] = (
                    'User {0} is not a member of {1}'
                    ).format(username, name)
            ret['result'] = None
    except pywintypes.com_error as com_err:
        if len(com_err.excepinfo) >= 2:
            friendly_error = com_err.excepinfo[2].rstrip('\r\n')
        ret['comment'] = (
                'Failed to remove {0} from group {1}.  {2}'
                ).format(username, name, friendly_error)
        ret['result'] = False
        return ret

    return ret


def members(name, members_list, **kwargs):
    '''
    Ensure a group contains only the members in the list

    Args:

        name (str):
            The name of the group to modify

        members_list (str):
            A single user or a comma separated list of users. The group will
            contain only the users specified in this list.

    Returns:
        dict: A dictionary of results

    CLI Example:

    .. code-block:: bash

        salt '*' group.members foo 'user1,user2,user3'
    '''

    ret = {'name': name,
           'result': True,
           'changes': {'Users Added': [], 'Users Removed': []},
           'comment': []}

    members_list = [salt.utils.win_functions.get_sam_name(m) for m in members_list.split(",")]
    if not isinstance(members_list, list):
        ret['result'] = False
        ret['comment'].append('Members is not a list object')
        return ret

    pythoncom.CoInitialize()
    nt = win32com.client.Dispatch('AdsNameSpaces')
    try:
        groupObj = nt.GetObject('', 'WinNT://./' + name + ',group')
    except pywintypes.com_error as com_err:
        if len(com_err.excepinfo) >= 2:
            friendly_error = com_err.excepinfo[2].rstrip('\r\n')
        ret['result'] = False
        ret['comment'].append((
                'Failure accessing group {0}.  {1}'
                ).format(name, friendly_error))
        return ret
    existingMembers = []
    for member in groupObj.members():
        existingMembers.append(
                member.ADSPath.replace('WinNT://', '').replace(
                '/', '\\').encode('ascii', 'backslashreplace').lower())

    existingMembers.sort()
    members_list.sort()

    if existingMembers == members_list:
        ret['result'] = None
        ret['comment'].append(('{0} membership is correct').format(name))
        return ret

    # add users
    for member in members_list:
        if member not in existingMembers:
            try:
                if not __opts__['test']:
                    groupObj.Add('WinNT://' + member.replace('\\', '/'))
                ret['changes']['Users Added'].append(member)
            except pywintypes.com_error as com_err:
                if len(com_err.excepinfo) >= 2:
                    friendly_error = com_err.excepinfo[2].rstrip('\r\n')
                ret['result'] = False
                ret['comment'].append((
                        'Failed to add {0} to {1}.  {2}'
                        ).format(member, name, friendly_error))
                #return ret

    # remove users not in members_list
    for member in existingMembers:
        if member not in members_list:
            try:
                if not __opts__['test']:
                    groupObj.Remove('WinNT://' + member.replace('\\', '/'))
                ret['changes']['Users Removed'].append(member)
            except pywintypes.com_error as com_err:
                if len(com_err.excepinfo) >= 2:
                    friendly_error = com_err.excepinfo[2].rstrip('\r\n')
                ret['result'] = False
                ret['comment'].append((
                        'Failed to remove {0} from {1}.  {2}'
                        ).format(member, name, friendly_error))
                #return ret

    return ret


def list_groups(refresh=False):
    '''
    Return a list of groups

    Args:

        refresh (bool):
            Refresh the info for all groups in ``__context__``. If False only
            the groups in ``__context__`` wil be returned. If True, the
            ``__context__`` will be refreshed with current data and returned.
            Default is False

    Returns:
        list: A list of groups on the machine

    CLI Example:

    .. code-block:: bash

        salt '*' group.list_groups
    '''
    if 'group.list_groups' in __context__ and not refresh:
        return __context__['group.getent']

    ret = []

    pythoncom.CoInitialize()
    nt = win32com.client.Dispatch('AdsNameSpaces')

    results = nt.GetObject('', 'WinNT://.')
    results.Filter = ['group']

    for result in results:
        ret.append(result.name)

    __context__['group.list_groups'] = ret

    return ret
