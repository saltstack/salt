# -*- coding: utf-8 -*-
'''
Management of user accounts
===========================

The user module is used to create and manage user settings, users can be set
as either absent or present

.. code-block:: yaml

    fred:
      user.present:
        - fullname: Fred Jones
        - shell: /bin/zsh
        - home: /home/fred
        - uid: 4000
        - gid: 4000
        - groups:
          - wheel
          - storage
          - games

    testuser:
      user.absent
'''

# Import python libs
from __future__ import absolute_import
import os
import logging

# Import salt libs
import salt.utils
from salt.utils.locales import sdecode, sdecode_if_string

# Import 3rd-party libs
from salt.ext.six import string_types, iteritems

log = logging.getLogger(__name__)


def _group_changes(cur, wanted, remove=False):
    '''
    Determine if the groups need to be changed
    '''
    old = set(cur)
    new = set(wanted)
    if (remove and old != new) or (not remove and not new.issubset(old)):
        return True
    return False


def _changes(name,
             uid=None,
             gid=None,
             groups=None,
             optional_groups=None,
             remove_groups=True,
             home=None,
             createhome=True,
             password=None,
             enforce_password=True,
             empty_password=False,
             shell=None,
             fullname='',
             roomnumber='',
             workphone='',
             homephone='',
             loginclass=None,
             date=0,
             mindays=0,
             maxdays=999999,
             inactdays=0,
             warndays=7,
             expire=None,
             win_homedrive=None,
             win_profile=None,
             win_logonscript=None,
             win_description=None):
    '''
    Return a dict of the changes required for a user if the user is present,
    otherwise return False.

    Updated in 2015.8.0 to include support for windows homedrive, profile,
    logonscript, and description fields.

    Updated in 2014.7.0 to include support for shadow attributes, all
    attributes supported as integers only.
    '''

    if 'shadow.info' in __salt__:
        lshad = __salt__['shadow.info'](name)

    lusr = __salt__['user.info'](name)
    if not lusr:
        return False

    change = {}
    if groups is None:
        groups = lusr['groups']
    wanted_groups = sorted(set((groups or []) + (optional_groups or [])))
    if uid and lusr['uid'] != uid:
        change['uid'] = uid
    if gid is not None and lusr['gid'] not in (gid, __salt__['file.group_to_gid'](gid)):
        change['gid'] = gid
    default_grp = __salt__['file.gid_to_group'](
        gid if gid is not None else lusr['gid']
    )
    # remove the default group from the list for comparison purposes
    if default_grp in lusr['groups']:
        lusr['groups'].remove(default_grp)
    if name in lusr['groups'] and name not in wanted_groups:
        lusr['groups'].remove(name)
    # remove default group from wanted_groups, as this requirement is
    # already met
    if default_grp in wanted_groups:
        wanted_groups.remove(default_grp)
    if _group_changes(lusr['groups'], wanted_groups, remove_groups):
        change['groups'] = wanted_groups
    if home and lusr['home'] != home:
        change['home'] = home
    if createhome:
        newhome = home if home else lusr['home']
        if newhome is not None and not os.path.isdir(newhome):
            change['homeDoesNotExist'] = newhome
    if shell and lusr['shell'] != shell:
        change['shell'] = shell
    if 'shadow.info' in __salt__ and 'shadow.default_hash' in __salt__:
        if password:
            default_hash = __salt__['shadow.default_hash']()
            if lshad['passwd'] == default_hash \
                    or lshad['passwd'] != default_hash and enforce_password:
                if lshad['passwd'] != password:
                    change['passwd'] = password
        if date and date is not 0 and lshad['lstchg'] != date:
            change['date'] = date
        if mindays and mindays is not 0 and lshad['min'] != mindays:
            change['mindays'] = mindays
        if maxdays and maxdays is not 999999 and lshad['max'] != maxdays:
            change['maxdays'] = maxdays
        if inactdays and inactdays is not 0 and lshad['inact'] != inactdays:
            change['inactdays'] = inactdays
        if warndays and warndays is not 7 and lshad['warn'] != warndays:
            change['warndays'] = warndays
        if expire and lshad['expire'] != expire:
            change['expire'] = expire
    elif 'shadow.info' in __salt__ and salt.utils.is_windows():
        if expire and expire is not -1 and salt.utils.date_format(lshad['expire']) != salt.utils.date_format(expire):
            change['expire'] = expire

    # GECOS fields
    fullname = sdecode_if_string(fullname)
    lusr['fullname'] = sdecode_if_string(lusr['fullname'])
    if fullname is not None and lusr['fullname'] != fullname:
        change['fullname'] = fullname
    if win_homedrive and lusr['homedrive'] != win_homedrive:
        change['homedrive'] = win_homedrive
    if win_profile and lusr['profile'] != win_profile:
        change['profile'] = win_profile
    if win_logonscript and lusr['logonscript'] != win_logonscript:
        change['logonscript'] = win_logonscript
    if win_description and lusr['description'] != win_description:
        change['description'] = win_description

    # MacOS doesn't have full GECOS support, so check for the "ch" functions
    # and ignore these parameters if these functions do not exist.
    if 'user.chroomnumber' in __salt__ \
            and roomnumber is not None:
        roomnumber = sdecode_if_string(roomnumber)
        lusr['roomnumber'] = sdecode_if_string(lusr['roomnumber'])
        if lusr['roomnumber'] != roomnumber:
            change['roomnumber'] = roomnumber
    if 'user.chworkphone' in __salt__ \
            and workphone is not None:
        workphone = sdecode_if_string(workphone)
        lusr['workphone'] = sdecode_if_string(lusr['workphone'])
        if lusr['workphone'] != workphone:
            change['workphone'] = workphone
    if 'user.chhomephone' in __salt__ \
            and homephone is not None:
        homephone = sdecode_if_string(homephone)
        lusr['homephone'] = sdecode_if_string(lusr['homephone'])
        if lusr['homephone'] != homephone:
            change['homephone'] = homephone
    # OpenBSD/FreeBSD login class
    if __grains__['kernel'] in ('OpenBSD', 'FreeBSD'):
        if loginclass:
            if __salt__['user.get_loginclass'](name) != loginclass:
                change['loginclass'] = loginclass

    return change


def present(name,
            uid=None,
            gid=None,
            gid_from_name=False,
            groups=None,
            optional_groups=None,
            remove_groups=True,
            home=None,
            createhome=True,
            password=None,
            hash_password=False,
            enforce_password=True,
            empty_password=False,
            shell=None,
            unique=True,
            system=False,
            fullname=None,
            roomnumber=None,
            workphone=None,
            homephone=None,
            loginclass=None,
            date=None,
            mindays=None,
            maxdays=None,
            inactdays=None,
            warndays=None,
            expire=None,
            win_homedrive=None,
            win_profile=None,
            win_logonscript=None,
            win_description=None,
            nologinit=False):
    '''
    Ensure that the named user is present with the specified properties

    name
        The name of the user to manage

    uid
        The user id to assign, if left empty then the next available user id
        will be assigned

    gid
        The default group id. Also accepts group name.

    gid_from_name
        If True, the default group id will be set to the id of the group with
        the same name as the user, Default is ``False``.

    groups
        A list of groups to assign the user to, pass a list object. If a group
        specified here does not exist on the minion, the state will fail.
        If set to the empty list, the user will be removed from all groups
        except the default group. If unset, salt will assume current groups
        are still wanted (see issue #28706).

    optional_groups
        A list of groups to assign the user to, pass a list object. If a group
        specified here does not exist on the minion, the state will silently
        ignore it.

    NOTE: If the same group is specified in both "groups" and
    "optional_groups", then it will be assumed to be required and not optional.

    remove_groups
        Remove groups that the user is a member of that weren't specified in
        the state, Default is ``True``.

    home
        The custom login directory of user. Uses default value of underlying
        system if not set. Notice that this directory does not have to exist.
        This also the location of the home directory to create if createhome is
        set to True.

    createhome : True
        If set to ``False``, the home directory will not be created if it
        doesn't already exist.

        .. warning::
            Not supported on Windows or Mac OS.

            Additionally, parent directories will *not* be created. The parent
            directory for ``home`` must already exist.

    nologinit : False
        If set to ``True``, it will not add the user to lastlog and faillog
        databases.

        .. note::
            Not supported on Windows or Mac OS.

    password
        A password hash to set for the user. This field is only supported on
        Linux, FreeBSD, NetBSD, OpenBSD, and Solaris. If the ``empty_password``
        argument is set to ``True`` then ``password`` is ignored.
        For Windows this is the plain text password.
        For Linux, the hash can be generated with ``openssl passwd -1``.

    .. versionchanged:: 0.16.0
       BSD support added.

    hash_password
        Set to True to hash the clear text password. Default is ``False``.


    enforce_password
        Set to False to keep the password from being changed if it has already
        been set and the password hash differs from what is specified in the
        "password" field. This option will be ignored if "password" is not
        specified, Default is ``True``.

    empty_password
        Set to True to enable password-less login for user, Default is ``False``.

    shell
        The login shell, defaults to the system default shell

    unique
        Require a unique UID, Default is ``True``.

    system
        Choose UID in the range of FIRST_SYSTEM_UID and LAST_SYSTEM_UID, Default is
        ``False``.

    loginclass
        The login class, defaults to empty
        (BSD only)

    User comment field (GECOS) support (currently Linux, BSD, and MacOS
    only):

    The below values should be specified as strings to avoid ambiguities when
    the values are loaded. (Especially the phone and room number fields which
    are likely to contain numeric data)

    fullname
        The user's full name

    roomnumber
        The user's room number (not supported in MacOS)

    workphone
        The user's work phone number (not supported in MacOS)

    homephone
        The user's home phone number (not supported in MacOS)
        If GECOS field contains more than 3 commas, this field will have the rest of 'em

    .. versionchanged:: 2014.7.0
       Shadow attribute support added.

    Shadow attributes support (currently Linux only):

    The below values should be specified as integers.

    date
        Date of last change of password, represented in days since epoch
        (January 1, 1970).

    mindays
        The minimum number of days between password changes.

    maxdays
        The maximum number of days between password changes.

    inactdays
        The number of days after a password expires before an account is
        locked.

    warndays
        Number of days prior to maxdays to warn users.

    expire
        Date that account expires, represented in days since epoch (January 1,
        1970).

    The below parameters apply to windows only:

    win_homedrive (Windows Only)
        The drive letter to use for the home directory. If not specified the
        home directory will be a unc path. Otherwise the home directory will be
        mapped to the specified drive. Must be a letter followed by a colon.
        Because of the colon, the value must be surrounded by single quotes. ie:
        - win_homedrive: 'U:

        .. versionchanged:: 2015.8.0

    win_profile (Windows Only)
        The custom profile directory of the user. Uses default value of
        underlying system if not set.

        .. versionchanged:: 2015.8.0

    win_logonscript (Windows Only)
        The full path to the logon script to run when the user logs in.

        .. versionchanged:: 2015.8.0

    win_description (Windows Only)
        A brief description of the purpose of the users account.

        .. versionchanged:: 2015.8.0
    '''

    # First check if a password is set. If password is set, check if
    # hash_password is True, then hash it.

    if password and hash_password:
        log.debug('Hashing a clear text password')
        password = __salt__['shadow.gen_password'](password)

    if fullname is not None:
        fullname = sdecode(fullname)
    if roomnumber is not None:
        roomnumber = sdecode(roomnumber)
    if workphone is not None:
        workphone = sdecode(workphone)
    if homephone is not None:
        homephone = sdecode(homephone)

    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'User {0} is present and up to date'.format(name)}

    # the comma is used to separate field in GECOS, thus resulting into
    # salt adding the end of fullname each time this function is called
    for gecos_field in ['fullname', 'roomnumber', 'workphone']:
        if isinstance(gecos_field, string_types) and ',' in gecos_field:
            ret['comment'] = "Unsupported char ',' in {0}".format(gecos_field)
            ret['result'] = False
            return ret

    if groups:
        missing_groups = [x for x in groups if not __salt__['group.info'](x)]
        if missing_groups:
            ret['comment'] = 'The following group(s) are not present: ' \
                             '{0}'.format(','.join(missing_groups))
            ret['result'] = False
            return ret

    if optional_groups:
        present_optgroups = [x for x in optional_groups
                             if __salt__['group.info'](x)]
        for missing_optgroup in [x for x in optional_groups
                                 if x not in present_optgroups]:
            log.debug('Optional group "{0}" for user "{1}" is not '
                      'present'.format(missing_optgroup, name))
    else:
        present_optgroups = None

    # Log a warning for all groups specified in both "groups" and
    # "optional_groups" lists.
    if groups and optional_groups:
        for isected in set(groups).intersection(optional_groups):
            log.warning('Group "{0}" specified in both groups and '
                        'optional_groups for user {1}'.format(isected, name))

    if gid_from_name:
        gid = __salt__['file.group_to_gid'](name)

    if empty_password:
        __salt__['shadow.del_password'](name)

    changes = _changes(name,
                       uid,
                       gid,
                       groups,
                       present_optgroups,
                       remove_groups,
                       home,
                       createhome,
                       password,
                       enforce_password,
                       empty_password,
                       shell,
                       fullname,
                       roomnumber,
                       workphone,
                       homephone,
                       loginclass,
                       date,
                       mindays,
                       maxdays,
                       inactdays,
                       warndays,
                       expire,
                       win_homedrive,
                       win_profile,
                       win_logonscript,
                       win_description)

    if changes:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = ('The following user attributes are set to be '
                              'changed:\n')
            for key, val in iteritems(changes):
                if key == 'passwd':
                    val = 'XXX-REDACTED-XXX'
                elif key == 'group' and not remove_groups:
                    key = 'ensure groups'
                ret['comment'] += u'{0}: {1}\n'.format(key, val)
            return ret
        # The user is present
        if 'shadow.info' in __salt__:
            lshad = __salt__['shadow.info'](name)
        if __grains__['kernel'] in ('OpenBSD', 'FreeBSD'):
            lcpre = __salt__['user.get_loginclass'](name)
        pre = __salt__['user.info'](name)
        for key, val in iteritems(changes):
            if key == 'passwd' and not empty_password:
                __salt__['shadow.set_password'](name, password)
                continue
            if key == 'passwd' and empty_password:
                log.warn("No password will be set when empty_password=True")
                continue
            if key == 'date':
                __salt__['shadow.set_date'](name, date)
                continue
            # run chhome once to avoid any possible bad side-effect
            if key == 'home' and 'homeDoesNotExist' not in changes:
                if __grains__['kernel'] in ('Darwin', 'Windows'):
                    __salt__['user.chhome'](name, val)
                else:
                    __salt__['user.chhome'](name, val, persist=False)
                continue
            if key == 'homeDoesNotExist':
                if __grains__['kernel'] in ('Darwin', 'Windows'):
                    __salt__['user.chhome'](name, val)
                else:
                    __salt__['user.chhome'](name, val, persist=True)
                if not os.path.isdir(val):
                    __salt__['file.mkdir'](val, pre['uid'], pre['gid'], 0o755)
                continue
            if key == 'mindays':
                __salt__['shadow.set_mindays'](name, mindays)
                continue
            if key == 'maxdays':
                __salt__['shadow.set_maxdays'](name, maxdays)
                continue
            if key == 'inactdays':
                __salt__['shadow.set_inactdays'](name, inactdays)
                continue
            if key == 'warndays':
                __salt__['shadow.set_warndays'](name, warndays)
                continue
            if key == 'expire':
                __salt__['shadow.set_expire'](name, expire)
                continue
            if key == 'win_homedrive':
                __salt__['user.update'](name=name, homedrive=val)
                continue
            if key == 'win_profile':
                __salt__['user.update'](name=name, profile=val)
                continue
            if key == 'win_logonscript':
                __salt__['user.update'](name=name, logonscript=val)
                continue
            if key == 'win_description':
                __salt__['user.update'](name=name, description=val)
                continue
            if key == 'groups':
                __salt__['user.ch{0}'.format(key)](
                    name, val, not remove_groups
                )
            else:
                __salt__['user.ch{0}'.format(key)](name, val)

        post = __salt__['user.info'](name)
        spost = {}
        if 'shadow.info' in __salt__ and lshad['passwd'] != password:
            spost = __salt__['shadow.info'](name)
        if __grains__['kernel'] in ('OpenBSD', 'FreeBSD'):
            lcpost = __salt__['user.get_loginclass'](name)
        # See if anything changed
        for key in post:
            if post[key] != pre[key]:
                ret['changes'][key] = post[key]
        if 'shadow.info' in __salt__:
            for key in spost:
                if lshad[key] != spost[key]:
                    if key == 'passwd':
                        ret['changes'][key] = 'XXX-REDACTED-XXX'
                    else:
                        ret['changes'][key] = spost[key]
        if __grains__['kernel'] in ('OpenBSD', 'FreeBSD') and lcpost != lcpre:
            ret['changes']['loginclass'] = lcpost
        if ret['changes']:
            ret['comment'] = 'Updated user {0}'.format(name)
        changes = _changes(name,
                           uid,
                           gid,
                           groups,
                           present_optgroups,
                           remove_groups,
                           home,
                           createhome,
                           password,
                           enforce_password,
                           empty_password,
                           shell,
                           fullname,
                           roomnumber,
                           workphone,
                           homephone,
                           loginclass,
                           date,
                           mindays,
                           maxdays,
                           inactdays,
                           warndays,
                           expire,
                           win_homedrive,
                           win_profile,
                           win_logonscript,
                           win_description)

        if changes:
            ret['comment'] = 'These values could not be changed: {0}'.format(
                changes
            )
            ret['result'] = False
        return ret

    if changes is False:
        # The user is not present, make it!
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'User {0} set to be added'.format(name)
            return ret
        if groups and present_optgroups:
            groups.extend(present_optgroups)
        elif present_optgroups:
            groups = present_optgroups[:]

        # Setup params specific to Linux and Windows to be passed to the
        # add.user function
        if not salt.utils.is_windows():
            params = {'name': name,
                      'uid': uid,
                      'gid': gid,
                      'groups': groups,
                      'home': home,
                      'shell': shell,
                      'unique': unique,
                      'system': system,
                      'fullname': fullname,
                      'roomnumber': roomnumber,
                      'workphone': workphone,
                      'homephone': homephone,
                      'createhome': createhome,
                      'nologinit': nologinit,
                      'loginclass': loginclass}
        else:
            params = ({'name': name,
                       'password': password,
                       'fullname': fullname,
                       'description': win_description,
                       'groups': groups,
                       'home': home,
                       'homedrive': win_homedrive,
                       'profile': win_profile,
                       'logonscript': win_logonscript})

        if __salt__['user.add'](**params):
            ret['comment'] = 'New user {0} created'.format(name)
            ret['changes'] = __salt__['user.info'](name)
            if not createhome:
                # pwd incorrectly reports presence of home
                ret['changes']['home'] = ''
            if 'shadow.info' in __salt__ \
                and not salt.utils.is_windows()\
                and not salt.utils.is_darwin():
                if password and not empty_password:
                    __salt__['shadow.set_password'](name, password)
                    spost = __salt__['shadow.info'](name)
                    if spost['passwd'] != password:
                        ret['comment'] = 'User {0} created but failed to set' \
                                         ' password to' \
                                         ' {1}'.format(name, 'XXX-REDACTED-XXX')
                        ret['result'] = False
                    ret['changes']['password'] = 'XXX-REDACTED-XXX'
                if date:
                    __salt__['shadow.set_date'](name, date)
                    spost = __salt__['shadow.info'](name)
                    if spost['lstchg'] != date:
                        ret['comment'] = 'User {0} created but failed to set' \
                                         ' last change date to' \
                                         ' {1}'.format(name, date)
                        ret['result'] = False
                    ret['changes']['date'] = date
                if mindays:
                    __salt__['shadow.set_mindays'](name, mindays)
                    spost = __salt__['shadow.info'](name)
                    if spost['min'] != mindays:
                        ret['comment'] = 'User {0} created but failed to set' \
                                         ' minimum days to' \
                                         ' {1}'.format(name, mindays)
                        ret['result'] = False
                    ret['changes']['mindays'] = mindays
                if maxdays:
                    __salt__['shadow.set_maxdays'](name, maxdays)
                    spost = __salt__['shadow.info'](name)
                    if spost['max'] != maxdays:
                        ret['comment'] = 'User {0} created but failed to set' \
                                         ' maximum days to' \
                                         ' {1}'.format(name, maxdays)
                        ret['result'] = False
                    ret['changes']['maxdays'] = maxdays
                if inactdays:
                    __salt__['shadow.set_inactdays'](name, inactdays)
                    spost = __salt__['shadow.info'](name)
                    if spost['inact'] != inactdays:
                        ret['comment'] = 'User {0} created but failed to set' \
                                         ' inactive days to' \
                                         ' {1}'.format(name, inactdays)
                        ret['result'] = False
                    ret['changes']['inactdays'] = inactdays
                if warndays:
                    __salt__['shadow.set_warndays'](name, warndays)
                    spost = __salt__['shadow.info'](name)
                    if spost['warn'] != warndays:
                        ret['comment'] = 'User {0} created but failed to set' \
                                         ' warn days to' \
                                         ' {1}'.format(name, warndays)
                        ret['result'] = False
                    ret['changes']['warndays'] = warndays
                if expire:
                    __salt__['shadow.set_expire'](name, expire)
                    spost = __salt__['shadow.info'](name)
                    if spost['expire'] != expire:
                        ret['comment'] = 'User {0} created but failed to set' \
                                         ' expire days to' \
                                         ' {1}'.format(name, expire)
                        ret['result'] = False
                    ret['changes']['expire'] = expire
            elif salt.utils.is_windows():
                if password and not empty_password:
                    if not __salt__['user.setpassword'](name, password):
                        ret['comment'] = 'User {0} created but failed to set' \
                                         ' password to' \
                                         ' {1}'.format(name, 'XXX-REDACTED-XXX')
                        ret['result'] = False
                    ret['changes']['passwd'] = 'XXX-REDACTED-XXX'
                if expire:
                    __salt__['shadow.set_expire'](name, expire)
                    spost = __salt__['shadow.info'](name)
                    if salt.utils.date_format(spost['expire']) != salt.utils.date_format(expire):
                        ret['comment'] = 'User {0} created but failed to set' \
                                         ' expire days to' \
                                         ' {1}'.format(name, expire)
                        ret['result'] = False
                    ret['changes']['expiration_date'] = spost['expire']
            elif salt.utils.is_darwin() and password and not empty_password:
                if not __salt__['shadow.set_password'](name, password):
                    ret['comment'] = 'User {0} created but failed to set' \
                                     ' password to' \
                                     ' {1}'.format(name, 'XXX-REDACTED-XXX')
                    ret['result'] = False
                ret['changes']['passwd'] = 'XXX-REDACTED-XXX'
        else:
            ret['comment'] = 'Failed to create new user {0}'.format(name)
            ret['result'] = False

    return ret


def absent(name, purge=False, force=False):
    '''
    Ensure that the named user is absent

    name
        The name of the user to remove

    purge
        Set purge to True to delete all of the user's files as well as the user,
        Default is ``False``.

    force
        If the user is logged in, the absent state will fail. Set the force
        option to True to remove the user even if they are logged in. Not
        supported in FreeBSD and Solaris, Default is ``False``.
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    lusr = __salt__['user.info'](name)
    if lusr:
        # The user is present, make it not present
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'User {0} set for removal'.format(name)
            return ret
        beforegroups = set(salt.utils.get_group_list(name))
        ret['result'] = __salt__['user.delete'](name, purge, force)
        aftergroups = set([g for g in beforegroups if __salt__['group.info'](g)])
        if ret['result']:
            ret['changes'] = {}
            for g in beforegroups - aftergroups:
                ret['changes']['{0} group'.format(g)] = 'removed'
            ret['changes'][name] = 'removed'
            ret['comment'] = 'Removed user {0}'.format(name)
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to remove user {0}'.format(name)
        return ret

    ret['comment'] = 'User {0} is not present'.format(name)

    return ret
