'''
Manage information about files on the minion, set/read user, group, and mode
data
'''

import os
import grp
import pwd
import hashlib

def gid_to_group(gid):
    '''
    Convert the group id to the group name on this system
    '''
    try:
        return grp.getgrgid(gid).gr_name
    except KeyError:
        return ''

def group_to_gid(group):
    '''
    Convert the group to the gid on this system
    '''
    try:
        return grp.getgrnam(group).gr_gid
    except KeyError:
        return ''

def get_gid(path):
    '''
    Return the user that owns a given file
    '''
    if not os.path.isfile(path):
        return False
    return os.stat(path).st_gid

def get_group(path):
    '''
    Return the user that owns a given file
    '''
    gid = get_gid(path)
    if not gid:
        return False
    return gid_to_user(gid)

def uid_to_user(uid):
    '''
    Convert a uid to a user name
    '''
    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return ''

def user_to_uid(user):
    '''
    Convert user name to a gid
    '''
    try:
        return pwd.getpwnam(user).pw_uid
    except KeyError:
        return ''

def get_uid(path):
    '''
    Return the user that owns a given file
    '''
    if not os.path.isfile(path):
        return False
    return os.stat(path).st_uid

def get_user(path):
    '''
    Return the user that owns a given file
    '''
    uid = get_uid(path)
    if not uid:
        return False
    return uid_to_user(uid)

def get_mode(path):
    '''
    Return the mode of a file
    '''
    if not os.path.isfile(path):
        return False
    return oct(os.stat(path).st_mode)[-4:]

def set_mode(path, mode):
    '''
    Set the more of a file
    '''
    if not os.path.isfile(path):
        return 'File not found'
    try:
        os.chmod(path, int(mode, 8))
    except:
        return 'Invalid Mode ' + mode
    return get_mode(path)

def get_sum(path, form='md5'):
    '''
    Return the sum for the given file, default is md5, sha1, sha224, sha256,
    sha384, sha512 are supported
    '''
    if not os.path.isfile(path):
        return 'File not found'
    try:
        return getattr(hashlib, form)(open(path, 'rb')).hexdigest()
    except:
        return 'Hash ' + form + ' not supported'
