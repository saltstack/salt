'''
Manage information about files on the minion, set/read user, group, and mode
data
'''

# TODO
# We should add the capability to do u+r type operations here some time in the
# future

import os
import grp
import pwd

def gid_to_group(gid):
    '''
    Convert the group id to the group name on this system

    CLI Example:
    salt '*' file.gid_to_group 0
    '''
    try:
        return grp.getgrgid(gid).gr_name
    except KeyError:
        return ''

def group_to_gid(group):
    '''
    Convert the group to the gid on this system

    CLI Example:
    salt '*' file.group_to_gid root
    '''
    try:
        return grp.getgrnam(group).gr_gid
    except KeyError:
        return ''

def get_gid(path):
    '''
    Return the user that owns a given file

    CLI Example:
    salt '*' file.get_gid /etc/passwd
    '''
    if not os.path.isfile(path):
        return -1
    return os.stat(path).st_gid

def get_group(path):
    '''
    Return the user that owns a given file

    CLI Example:
    salt '*' file.get_group /etc/passwd
    '''
    gid = get_gid(path)
    if gid == -1:
        return False
    return gid_to_group(gid)

def uid_to_user(uid):
    '''
    Convert a uid to a user name

    CLI Example:
    salt '*' file.uid_to_user 0
    '''
    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return ''

def user_to_uid(user):
    '''
    Convert user name to a gid

    CLI Example:
    salt '*' file.user_to_uid root
    '''
    try:
        return pwd.getpwnam(user).pw_uid
    except KeyError:
        return ''

def get_uid(path):
    '''
    Return the user that owns a given file

    CLI Example:
    salt '*' file.get_uid /etc/passwd
    '''
    if not os.path.isfile(path):
        return False
    return os.stat(path).st_uid

def get_user(path):
    '''
    Return the user that owns a given file

    CLI Example:
    salt '*' file.get_user /etc/passwd
    '''
    uid = get_uid(path)
    if uid == -1:
        return False
    return uid_to_user(uid)

def get_mode(path):
    '''
    Return the mode of a file

    CLI Example:
    salt '*' file.get_mode /etc/passwd
    '''
    if not os.path.isfile(path):
        return -1
    mode = str(oct(os.stat(path).st_mode)[-4:])
    if mode.startswith('0'):
        return mode[1:]
    return mode

def set_mode(path, mode):
    '''
    Set the more of a file

    CLI Example:
    salt '*' file.set_mode /etc/passwd 0644
    '''
    mode = str(mode)
    if not os.path.isfile(path):
        return 'File not found'
    try:
        os.chmod(path, int(mode, 8))
    except:
        return 'Invalid Mode ' + mode
    return get_mode(path)

def chown(path, user, group):
    '''
    Chown a file, pass the file the desired user and group

    CLI Example:
    salt '*' file.chown /etc/passwd root root
    '''
    uid = user_to_uid(user)
    gid = group_to_gid(group)
    err = ''
    if not uid:
        err += 'User does not exist\n'
    if not gid:
        err += 'Group does not exist\n'
    if not os.path.isfile(path):
        err += 'File not found'
    if err:
        return err
    return os.chown(path, uid, gid)

def chgrp(path, group):
    '''
    Change the group of a file

    CLI Example:
    salt '*' file.chgrp /etc/passwd root
    '''
    gid = group_to_gid(group)
    err = ''
    if not gid:
        err += 'Group does not exist\n'
    if not os.path.isfile(path):
        err += 'File not found'
    if err:
        return err
    user = get_user(path)
    return chown(path, user, group)

def get_sum(path, form='md5'):
    '''
    Return the sum for the given file, default is md5, sha1, sha224, sha256,
    sha384, sha512 are supported

    CLI Example:
    salt '*' /etc/passwd sha512
    '''
    if not os.path.isfile(path):
        return 'File not found'
    try:
        return getattr(hashlib, form)(open(path, 'rb')).hexdigest()
    except:
        return 'Hash ' + form + ' not supported'
