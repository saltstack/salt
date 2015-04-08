# -*- coding: utf-8 -*-
'''
Manage Windows users with ADSI

Can manage local user accounts or domain accounts (if salt-minion is running as a user w/access
to AD (or localsystem on a DC), AD accounts should be managed as LDAP objects...
'''

from __future__ import absolute_import

import salt.utils
from salt.ext.six import string_types
import logging

log = logging.getLogger(__name__)

try:
    import win32netcon
    import win32security
    import win32com.client
    import pythoncom
    import pywintypes
    HAS_WIN32NET_MODS = True
except ImportError:
    HAS_WIN32NET_MODS = False

# Define the module's virtual name
__virtualname__ = 'user'


def __virtual__():
    '''
    Set the user module if the kernel is Windows
    '''
    if HAS_WIN32NET_MODS is True and salt.utils.is_windows():
        return __virtualname__
    return False


def add(name,
        password=None,
        fullname=False,
        description=False,
        firstname=False,
        lastname=False,
        middleinitial=False,
        disabled=False,
        requirepwchange=True,
        pwneverexpires=False,
        # Disable pylint checking on the next options. They exist to match the
        # user modules of other distributions.
        # pylint: disable=W0613
        uid=None,
        gid=None,
        groups=None,
        home=False,
        shell=None,
        unique=False,
        system=False,
        roomnumber=False,
        workphone=False,
        homephone=False,
        loginclass=False,
        createhome=False
        # pylint: enable=W0613
        ):
    '''
    Add a user to the minion

    CLI Example:

    .. code-block:: bash

        salt '*' user.add name password

        if you want to create on a domain controller, you should use the LDAP DN of the object to create
        short name will work, but UPN will not get set

        you must use name='cn=user,....' since the DN contains '='

        salt 'domainController' user.add name='cn=user,cn=Users,dc=domain,dc=dom' password='pa$$word'
    '''
    ret = {'name': name,
           'result': True,
           'changes': [],
           'comment': []}

    if not info(name):
        if password is not None:
            pythoncom.CoInitialize()
            nt = win32com.client.Dispatch('AdsNameSpaces')
            try:
                compObj = None
                addUserName = name
                ldapProvider = False
                if 'dc=' in name.lower():
                    compObj = nt.GetObject('', 'LDAP://' + name[(name.find(',') + 1):len(name)])
                    addUserName = name[0:(name.find(','))]
                    ldapProvider = True
                else:
                    compObj = nt.GetObject('', 'WinNT://.,computer')
                if compObj is not None:
                    newUser = compObj.Create('user', addUserName)
                    if ldapProvider:
                        # ldap provider seems to require 'SetInfo' before you can set the password (opposite of WinNT provider)
                        # also must set the account to 'enabled' as default is disabled
                        # lots of LDAP properties could be added here/to the function
                        newUser.sAMAccountName = addUserName.replace('cn=', '').replace('CN=', '')
                        newUser.userPrincipalName = addUserName.replace('cn=', '').replace(
                                'CN=', '') + '@' + name[(name.find('dc=') + 3):len(name)].replace(
                                'dc=', '.').replace(',', '')
                        newUser.userAccountControl = 544
                        if fullname:
                            newUser.FullName = fullname
                        newUser.SetInfo()
                        newUser.SetPassword(password)
                        newUser.userAccountControl = 512
                        if description:
                            newUser.Description = description
                        if firstname:
                            newUser.givenName = firstname
                        if lastname:
                            newUser.sn = lastname
                        if middleinitial:
                            newUser.initials = middleinitial
                        if home:
                            newUser.homeDirectory = home
                        newUser.SetInfo()
                    else:
                        if fullname:
                            newUser.Put('FullName', fullname)
                        if description:
                            newUser.Put('Description', description)
                        if home:
                            newUser.Put('HomeDirectory', home)
                        newUser.SetPassword(password)
                        newUser.SetInfo()
                    ret['changes'].append((
                            'Successfully created user {0}'
                            ).format(name))
                    if disabled:
                        this_ret = disable(name)
                        if this_ret['result']:
                            ret['changes'].append(this_ret['changes'])
                        else:
                            ret['comment'].append(this_ret['comment'])
                    else:
                        this_ret = enable(name)
                        if this_ret['result']:
                            ret['changes'].append(this_ret['changes'])
                        else:
                            ret['comment'].append(this_ret['comment'])
                    if pwneverexpires:
                        this_ret = passwordneverexpires(name)
                        if this_ret['result']:
                            ret['changes'].append(this_ret['changes'])
                        else:
                            ret['comment'].append(this_ret['comment'])
                    else:
                        this_ret = passwordneverexpires(name, True)
                        if this_ret['result']:
                            ret['changes'].append(this_ret['changes'])
                        else:
                            ret['comment'].append(this_ret['comment'])

                        if requirepwchange:
                            this_ret = requirepasswordchange(name)
                            if this_ret['result']:
                                ret['changes'].append(this_ret['changes'])
                            else:
                                ret['comment'].append(this_ret['comment'])
                        else:
                            this_ret = requirepasswordchange(name, True)
                            if this_ret['result']:
                                ret['changes'].append(this_ret['changes'])
                            else:
                                ret['comment'].append(this_ret['comment'])
                else:
                    ret['result'] = False
                    ret['comment'].append('Unable to obtain ADSI object')
            except pywintypes.com_error as com_err:
                ret['result'] = False
                friendly_error = ''
                if len(com_err.excepinfo) >= 2:
                    if com_err.excepinfo[2] is not None:
                        friendly_error = com_err.excepinfo[2].rstrip('\r\n')
                ret['comment'].append((
                        'Failed to create user {0}.  {1}'
                        ).format(name, friendly_error))
        else:
            ret['result'] = False
            ret['comment'].append((
                    'A password was not supplied for new user {0}.'
                    ).format(name))
    else:
        ret['result'] = None
        ret['comment'].append((
                'The user {0} already exists.'
                ).format(name))

    return ret


def delete(name,
           # Disable pylint checking on the next options. They exist to match
           # the user modules of other distributions.
           # pylint: disable=W0613
           purge=False,
           force=False
           # pylint: enable=W0613
           ):
    '''
    Remove a user from the minion
    NOTE: purge and force have not been implemented on Windows yet

    CLI Example:

    .. code-block:: bash

        salt '*' user.delete name
    '''
    ret = {'name': name,
           'result': True,
           'changes': [],
           'comment': ''}

    if info(name):
        pythoncom.CoInitialize()
        nt = win32com.client.Dispatch('AdsNameSpaces')
        try:
            deleteUserName = name
            compObj = None
            if 'dc=' in name.lower():
                compObj = nt.GetObject('', 'LDAP://' + name[(name.find(',') + 1):len(name)])
                deleteUserName = name[0:(name.find(','))]
            else:
                compObj = nt.GetObject('', 'WinNT://.,computer')
                if '\\' in deleteUserName:
                    deleteUserName = deleteUserName.split('\\')[1]
            if compObj is not None:
                compObj.Delete('user', deleteUserName)
                ret['changes'].append(('Successfully removed user {0}').format(name))
            else:
                ret['result'] = False
                ret['comment'] = ('Unable to obtain ADSI object')
        except pywintypes.com_error as com_err:
            ret['result'] = False
            if len(com_err.excepinfo) >= 2:
                if com_err.excepinfo[2] is not None:
                    friendly_error = com_err.excepinfo[2].rstrip('\r\n')
            ret['comment'] = (
                    'Failed to remove user {0}.  {1}'
                    ).format(name, friendly_error)
    else:
        ret['result'] = None
        ret['comment'] = (
                'The user {0} does not exists.'
                ).format(name)

    return ret


def enable(name):
    '''
    enable a user account

    salt '*' user.enable foo
    '''
    ret = disable(name, False)
    return ret


def disable(name, disabled=True):
    '''
    disable a user account

    salt '*' disableuser foo

    to enable a user:

    salt '*' disableuser foot False
    '''
    ret = {'name': name,
           'result': True,
           'changes': '',
           'comment': ''}
    pythoncom.CoInitialize()
    nt = win32com.client.Dispatch('AdsNameSpaces')
    if disabled:
        accountstatus = 'disabled'
    else:
        accountstatus = 'enabled'
    try:
        if 'dc=' in name.lower():
            userObj = nt.GetObject('', 'LDAP://' + name)

        else:
            userObj = nt.GetObject('', 'WinNT://./' + name + ',user')

        userObj.AccountDisabled = disabled
        userObj.SetInfo()
        ret['result'] = True
        ret['changes'] = (
                'User {0} is now {1}.'
                ).format(name, accountstatus)
    except pywintypes.com_error as com_err:
        ret['result'] = False
        friendly_error = ''
        if len(com_err.excepinfo) >= 2:
            if com_err.excepinfo[2] is not None:
                friendly_error = com_err.excepinfo[2].rstrip('\r\n')
        ret['comment'] = (
                'Failed to set password for user {0}.  {1} - {2}'
                ).format(name, friendly_error, com_err)
    return ret


def passwordneverexpires(name, clear=False):
    '''
    set a user's password to never expire

    salt '*' user.passwordneverexpires foo

    to clear the password never expires setting (i.e. set it to expire), use clear=True

    salt '*' user.passwordneverexpires foo True
    '''
    ret = {'name': name,
           'result': True,
           'changes': '',
           'comment': ''}
    pythoncom.CoInitialize()
    nt = win32com.client.Dispatch('AdsNameSpaces')
    if clear:
        expirestatus = 'expire'
    else:
        expirestatus = 'never expire'
    try:
        if 'dc=' in name.lower():
            userObj = nt.GetObject('', 'LDAP://' + name)
            if clear:
                if bool(userObj.userAccountControl & win32netcon.UF_DONT_EXPIRE_PASSWD):
                    userObj.userAccountControl = userObj.userAccountControl ^ win32netcon.UF_DONT_EXPIRE_PASSWD
            else:
                userObj.userAccountControl = userObj.userAccountControl | win32netcon.UF_DONT_EXPIRE_PASSWD
        else:
            userObj = nt.GetObject('', 'WinNT://./' + name + ',user')
            if clear:
                if bool(userObj.UserFlags & win32netcon.UF_DONT_EXPIRE_PASSWD):
                    userObj.Put('UserFlags', userObj.UserFlags ^ win32netcon.UF_DONT_EXPIRE_PASSWD)
            else:
                userObj.Put('UserFlags', userObj.UserFlags | win32netcon.UF_DONT_EXPIRE_PASSWD)
        userObj.SetInfo()
        ret['result'] = True
        ret['changes'] = (
                'Password for user {0} is now set to {1}.'
                ).format(name, expirestatus)
    except pywintypes.com_error as com_err:
        ret['result'] = False
        friendly_error = ''
        if len(com_err.excepinfo) >= 2:
            if com_err.excepinfo[2] is not None:
                friendly_error = com_err.excepinfo[2].rstrip('\r\n')
        ret['comment'] = (
                'Failed to set password for user {0}.  {1} - {2}'
                ).format(name, friendly_error, com_err)

    return ret


def requirepasswordchange(name, clear=False):
    '''
    expire a user's password (i.e. require it to change on next logon)
    if the password is set to "never expire" this has no effect

    salt '*' user.requirepasswordchange foo

    to clear the require password change flag, use clear=True

    salt '*' user.requirepasswordchange foo True
    '''
    ret = {'name': name,
           'result': True,
           'changes': '',
           'comment': ''}
    pythoncom.CoInitialize()
    nt = win32com.client.Dispatch('AdsNameSpaces')
    if clear:
        expiredstatus = 'cleared'
    else:
        expiredstatus = 'set'
    try:
        if 'dc=' in name.lower():
            userObj = nt.GetObject('', 'LDAP://' + name)
            if clear:
                userObj.pwdLastSet = -1
            else:
                userObj.pwdLastSet = 0
        else:
            userObj = nt.GetObject('', 'WinNT://./' + name + ',user')
            if clear:
                userObj.Put('PasswordExpired', 0)
            else:
                userObj.Put('PasswordExpired', 1)
        userObj.SetInfo()
        ret['result'] = True
        ret['changes'] = (
                'Password must be changed at next logon for {0} is now {1}.'
                ).format(name, expiredstatus)
    except pywintypes.com_error as com_err:
        ret['result'] = False
        friendly_error = ''
        if len(com_err.excepinfo) >= 2:
            if com_err.excepinfo[2] is not None:
                friendly_error = com_err.excepinfo[2].rstrip('\r\n')
        ret['comment'] = (
                'Failed to set password for user {0}.  {1} - {2}'
                ).format(name, friendly_error, com_err)

    return ret


def setpassword(name, password, mustchange=None, neverexpires=None):
    '''
    Set a user's password

    use 'mustchange' and 'neverexpires' to set those user account attributes, by default they will be left alone (None)
        setting to 'False' will clear them, setting to 'True' will set them
    CLI Example:

    .. code-block:: bash

        salt '*' user.setpassword name password
    '''
    ret = {'name': name,
           'result': True,
           'changes': [],
           'comment': ''}

    if info(name):
        pythoncom.CoInitialize()
        nt = win32com.client.Dispatch('AdsNameSpaces')
        try:
            userObj = None
            if 'dc=' in name.lower():
                userObj = nt.GetObject('', 'LDAP://' + name)
            else:
                userObj = nt.GetObject('', 'WinNT://./' + name + ',user')
            if userObj is not None:
                userObj.SetPassword(password)
                ret['changes'].append((
                        'Successfully set password for user {0}'
                        ).format(name))
                if mustchange is not None:
                    if mustchange:
                        temp_ret = requirepasswordchange(name)
                        ret['changes'].append(temp_ret['changes'])
                    else:
                        temp_ret = requirepasswordchange(name, True)
                        ret['changes'].append(temp_ret['changes'])
                if neverexpires is not None:
                    if neverexpires:
                        temp_ret = passwordneverexpires(name)
                        ret['changes'].append(temp_ret['changes'])
                    else:
                        temp_ret = passwordneverexpires(name, True)
                        ret['changes'].append(temp_ret['changes'])
            else:
                ret['result'] = False
                ret['comment'] = ('Unable to obtain ADSI user object')
        except pywintypes.com_error as com_err:
            ret['result'] = False
            friendly_error = ''
            if len(com_err.excepinfo) >= 2:
                if com_err.excepinfo[2] is not None:
                    friendly_error = com_err.excepinfo[2].rstrip('\r\n')
            ret['comment'] = (
                    'Failed to set password for user {0}.  {1}'
                    ).format(name, friendly_error)
    else:
        ret['result'] = None
        ret['comment'] = (
                'The user {0} does not exists.'
                ).format(name)

    return ret


def addgroup(name, group):
    '''
    Add user to a group

    CLI Example:

    .. code-block:: bash

        salt '*' user.addgroup username groupname
    '''
    ret = __salt__['group.adduser'](group, name)
    return ret


def removegroup(name, group):
    '''
    Remove user from a group

    CLI Example:

    .. code-block:: bash

        salt '*' user.removegroup username groupname
    '''
    ret = __salt__['group.deluser'](group, name)
    return ret


def chhome(name, home):
    '''
    Change the home directory of the user

    CLI Example:

    .. code-block:: bash

        salt '*' user.chhome foo \\\\fileserver\\home\\foo
    '''
    ret = {'name': name,
           'result': True,
           'changes': [],
           'comment': ''}

    current_info = info(name)
    pythoncom.CoInitialize()
    nt = win32com.client.Dispatch('AdsNameSpaces')

    if current_info:
        try:
            if "dc=" in name.lower():
                userObj = nt.GetObject('', 'LDAP://' + name)
                userObj.HomeDirectory = home
                userObj.SetInfo()
            else:
                userObj = nt.GetObject('', 'WinNT://./' + name + ',user')
                userObj.Put('HomeDirectory', home)
                userObj.SetInfo()
            ret['result'] = True
            ret['changes'] = (
                    'Successfully changed user {0}\'s home directory from "{1}" to "{2}"'
                    ).format(name, current_info['home'], home)
        except pywintypes.com_error as com_err:
            ret['result'] = False
            if len(com_err.excepinfo) >= 2:
                if com_err.excepinfo[2] is not None:
                    friendly_error = com_err.excepinfo[2].rstrip('\r\n')
            ret['comment'] = (
                    'Failed to set home directory for user {0}.  {1}'
                    ).format(name, friendly_error)
    else:
        ret['result'] = False
        ret['comment'] = (
                'The user {0} does not appear to exist.'
                ).format(name)
    return ret


def chprofile(name, profile):
    '''
    Change the profile directory of the user

    CLI Example:

    .. code-block:: bash

        salt '*' user.chprofile foo \\\\fileserver\\profiles\\foo

    '''
    ret = {'name': name,
           'result': True,
           'changes': [],
           'comment': ''}

    current_info = info(name)
    pythoncom.CoInitialize()
    nt = win32com.client.Dispatch('AdsNameSpaces')

    if current_info:
        try:
            if "dc=" in name.lower():
                userObj = nt.GetObject('', 'LDAP://' + name)
                userObj.profilePath = profile
                userObj.SetInfo()
            else:
                userObj = nt.GetObject('', 'WinNT://./' + name + ',user')
                userObj.Put('profile', profile)
                userObj.SetInfo()
            ret['result'] = True
            ret['changes'] = (
                    'Successfully changed user {0}\'s profile directory from "{1}" to "{2}"'
                    ).format(name, current_info['profile'], profile)
        except pywintypes.com_error as com_err:
            ret['result'] = False
            friendly_error = ''
            if len(com_err.excepinfo) >= 2:
                if com_err.excepinfo[2] is not None:
                    friendly_error = com_err.excepinfo[2].rstrip('\r\n')
            ret['comment'] = (
                    'Failed to set profile path for user {0}.  {1}'
                    ).format(name, friendly_error)
    else:
        ret['result'] = False
        ret['comment'] = (
                'The user {0} does not appear to exist.'
                ).format(name)
    return ret


def chfullname(name, fullname):
    '''
    Change the full name of the user

    CLI Example:

    .. code-block:: bash

        salt '*' user.chfullname user 'First Last'
    '''
    ret = {'name': name,
           'result': True,
           'changes': [],
           'comment': ''}

    current_info = info(name)
    pythoncom.CoInitialize()
    nt = win32com.client.Dispatch('AdsNameSpaces')

    if current_info:
        try:
            if "dc=" in name.lower():
                userObj = nt.GetObject('', 'LDAP://' + name)
                userObj.FullName = fullname
                userObj.SetInfo()
            else:
                userObj = nt.GetObject('', 'WinNT://./' + name + ',user')
                userObj.Put('FullName', fullname)
                userObj.SetInfo()
            ret['result'] = True
            ret['changes'] = (
                    'Successfully changed user {0}\'s full name from "{1}" to "{2}"'
                    ).format(name, current_info['fullname'], fullname)
        except pywintypes.com_error as com_err:
            ret['result'] = False
            if len(com_err.excepinfo) >= 2:
                if com_err.excepinfo[2] is not None:
                    friendly_error = com_err.excepinfo[2].rstrip('\r\n')
            ret['comment'] = (
                    'Failed to change the full name for user {0}.  {1}'
                    ).format(name, friendly_error)
    else:
        ret['result'] = False
        ret['comment'] = (
                'The user {0} does not appear to exist.'
                ).format(name)
    return ret


def chgroups(name, groups, append=False):
    '''
    Change the groups this user belongs to, add append to append the specified
    groups

    CLI Example:

    .. code-block:: bash

        salt '*' user.chgroups foo wheel,root True

        if using DNs, group names must be separated with ', '
    '''
    ret = {'name': name,
           'result': True,
           'changes': {'Groups Added': [], 'Groups Removed': []},
           'comment': []}

    current_info = info(name)
    if isinstance(groups, string_types):
        if 'dc=' in groups.lower():
            groups = groups.split(", ")
        else:
            groups = groups.split(',')
    groups = [_fixlocaluser(x.strip(' *')) for x in groups]
    groups.sort()
    current_info['groups'].sort()

    if current_info:
        if [x.lower() for x in groups] == [x.lower() for x in current_info['groups']]:
            # nothing done
            ret['result'] = None
            ret['changes'] = None
            ret['comment'].append((
                    '{0}\'s group membership is correct.'
                    ).format(name))
        else:
            if append:
                for group in groups:
                    if group.lower() not in [x.lower() for x in current_info['groups']]:
                        thisRet = addgroup(name, group)
                        if thisRet['result']:
                            ret['changes']['Groups Added'].append(group)
                        else:
                            ret['result'] = False
                            ret['comment'].append(thisRet['comment'])
                            return ret
            else:
                for group in current_info['groups']:
                    if group.lower() not in [x.lower() for x in groups]:
                        # remove it
                        thisRet = removegroup(name, group)
                        if thisRet['result']:
                            ret['changes']['Groups Removed'].append(group)
                        else:
                            ret['result'] = False
                            ret['comment'].append(thisRet['comment'])
                            return ret
                for group in groups:
                    if group.lower() not in [x.lower() for x in current_info['groups']]:
                        # add it
                        thisRet = addgroup(name, group)
                        if thisRet['result']:
                            ret['changes']['Groups Added'].append(group)
                        else:
                            ret['result'] = False
                            ret['comment'].append(thisRet['comment'])
                            return ret

            ret['result'] = True
    else:
        ret['result'] = False
        ret['comment'].append((
                'The user {0} does not appear to exist.'
                ).format(name))
    return ret


def info(name):
    '''
    Return user information

    CLI Example:

    .. code-block:: bash

        salt '*' user.info root
    '''
    pythoncom.CoInitialize()
    nt = win32com.client.Dispatch('AdsNameSpaces')

    ret = {'name': '',
            'fullname': '',
            'uid': '',
            'comment': '',
            'active': '',
            'logonscript': '',
            'profile': '',
            'home': '',
            'groups': '',
            'gid': ''}
    try:
        if 'dc=' in name.lower():
            userObj = nt.GetObject('', 'LDAP://' + name)
            ret['active'] = (not bool(userObj.userAccountControl & win32netcon.UF_ACCOUNTDISABLE))
            ret['logonscript'] = userObj.scriptPath
            ret['profile'] = userObj.profilePath
            ret['fullname'] = userObj.DisplayName
            ret['name'] = userObj.sAMAccountName
        else:
            if '\\' in name:
                name = name.split('\\')[1]
            userObj = nt.GetObject('', 'WinNT://./' + name + ',user')
            ret['logonscript'] = userObj.LoginScript
            ret['active'] = (not userObj.AccountDisabled)
            ret['fullname'] = userObj.FullName
            ret['name'] = userObj.Name
            if not userObj.Profile:
                regProfile = _get_userprofile_from_registry(
                        name, win32security.ConvertSidToStringSid(
                        pywintypes.SID(userObj.objectSID)))
                if regProfile:
                    ret['profile'] = regProfile
            else:
                ret['profile'] = userObj.Profile

        gr_mem = []

        for group in userObj.groups():
            if 'winnt' in group.ADSPath.lower():
                gr_mem.append(
                        _getnetbiosusernamefromsid(group.ADSPath))
            else:
                gr_mem.append(
                        group.distinguishedName)
        ret['groups'] = gr_mem

        ret['uid'] = win32security.ConvertSidToStringSid(pywintypes.SID(userObj.objectSID))
        ret['comment'] = userObj.description
        ret['home'] = userObj.homeDirectory
        ret['gid'] = userObj.primaryGroupID
    except pywintypes.com_error:
        return False

    return ret


def _get_userprofile_from_registry(user, sid):
    '''
    In case net user doesn't return the userprofile
    we can get it from the registry
    '''
    profile_dir = __salt__['reg.read_key'](
        'HKEY_LOCAL_MACHINE', 'SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\ProfileList\\{0}'.format(sid),
        'ProfileImagePath'
    )
    log.debug('user {0} with sid={2} profile is located at "{1}"'.format(user, profile_dir, sid))
    return profile_dir


def list_groups(name):
    '''
    Return a list of groups the named user belongs to

    CLI Example:

    .. code-block:: bash

        salt '*' user.list_groups foo
    '''

    user = info(name)
    if user:
        return sorted(user['groups'])
    else:
        return False


def getent(refresh=False):
    '''
    Return the list of all info for all users

    CLI Example:

    .. code-block:: bash

        salt '*' user.getent
    '''
    if 'user.getent' in __context__ and not refresh:
        return __context__['user.getent']

    ret = []
    for user in __salt__['user.list_users']():
        user_info = __salt__['user.info'](user)
        ret.append(user_info)
    __context__['user.getent'] = ret
    return ret


def list_users(useldap=False):
    '''
    Return a list of users on Windows
    '''
    ret = []

    pythoncom.CoInitialize()
    nt = win32com.client.Dispatch('AdsNameSpaces')

    if useldap:
        # try to recurse through the ldap server and get all user objects...
        # could do 'LDAP:' and allow any domain member the ability to get all ldap users
        # if anonymous binds are allowed, but for now, the code will try to connect to ldap on the local
        # host
        ret = _recursecontainersforusers('LDAP://localhost')
    else:
        results = nt.GetObject('', 'WinNT://.')
        results.Filter = ['user']
        for result in results:
            ret.append(_getnetbiosusernamefromsid(result.AdsPath))
    __context__['list_users'] = ret
    return ret


def _recursecontainersforusers(path):
    '''
    recursively get all user objects in all sub-containers from a top level container
    for example:
            _recursecontainersfrorusers('LDAP:')
            would find all user objects in a domain via ldap
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
            if result.Class.lower() == 'user':
                ret.append(result.distinguishedName)
            else:
                ret = ret + (_recursecontainersforusers(result.AdsPath))

    return ret


def rename(name, new_name):
    '''
    Change the username for a named user

    CLI Example:

    .. code-block:: bash

        salt '*' user.rename name new_name

        domain users should use LDAP, to rename the cn, sAMAccountName, and UPN
        salt 'domainController' user.rename name='cn=user,cn=Users,dc=domain,dc=dom' new_name='newUserName'
    '''
    ret = {'result': True,
           'changes': [],
           'comment': ''}

    current_info = info(name)
    pythoncom.CoInitialize()
    nt = win32com.client.Dispatch('AdsNameSpaces')

    if current_info:
        try:
            if "dc=" in name.lower():
                userObj = nt.GetObject('', 'LDAP://' + name)
                userObj.sAMAccountName = new_name
                userObj.userPrincipalName = new_name + '@' + name[(
                        name.find('dc=') + 3):len(name)].replace('dc=', '.').replace(',', '')
                userObj.SetInfo()
                containerObj = nt.GetObject('', userObj.parent)
                containerObj.MoveHere(userObj.AdsPath, 'cn=' + new_name)
            else:
                containerObj = nt.GetObject('', 'WinNT://.,computer')
                userObj = nt.GetObject('', 'WinNT://./' + name + ',user')
                containerObj.MoveHere(userObj.AdsPath, new_name)
            ret['changes'] = (
                    'Successfully renamed user {0} to {1}'
                    ).format(name, new_name)
        except pywintypes.com_error as com_err:
            ret['result'] = False
            if len(com_err.excepinfo) >= 2:
                if com_err.excepinfo[2] is not None:
                    friendly_error = com_err.excepinfo[2].rstrip('\r\n')
            ret['comment'] = (
                    'Failed to remove user {0}.  {1}'
                    ).format(name, friendly_error)
    else:
        ret['result'] = False
        ret['comment'] = (
                'The user {0} does not appear to exist.'
                ).format(name)

    return ret


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


def _fixlocaluser(username):
    '''
    prefixes a username w/o a backslash with the computername

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
                username = ('{0}\\{1}').format(__salt__['grains.get']('host'), username)

    return username
