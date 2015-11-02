'''
Set grains describing the minion process.
'''


import os

try:
    import pwd
except ImportError:
    import getpass
    pwd = None

try:
    import grp
except ImportError:
    grp = None


def _uid():
    '''Grain for the minion User ID'''
    return os.getuid()


def _username():
    '''Grain for the minion username'''
    if pwd:
        username = pwd.getpwuid(os.getuid()).pw_name
    else:
        username = getpass.getuser()

    return username


def _gid():
    '''Grain for the minion Group ID'''
    return os.getgid()


def _groupname():
    '''Grain for the minion groupname'''
    if grp:
        groupname = grp.getgrgid(os.getgid()).gr_name
    else:
        groupname = ''

    return groupname


def _pid():
    return os.getpid()


def grains():
    return {
        'uid'       : _uid(),
        'username'  : _username(),
        'gid'       : _gid(),
        'groupname' : _groupname(),
        'pid'       : _pid(),
    }
