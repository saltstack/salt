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
import hashlib

import salt.utils.find

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
    if not os.path.exists(path):
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
    if not os.path.exists(path):
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
    if not os.path.exists(path):
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
    if not os.path.exists(path):
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
    if uid == '':
        err += 'User does not exist\n'
    if gid == '':
        err += 'Group does not exist\n'
    if not os.path.exists(path):
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
    if gid == '':
        err += 'Group does not exist\n'
    if not os.path.exists(path):
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
        return getattr(hashlib, form)(open(path, 'rb').read()).hexdigest()
    except (IOError, OSError), e:
        return 'File Error: %s' % (str(e))
    except AttributeError, e:
        return 'Hash ' + form + ' not supported'
    except NameError, e:
        return 'Hashlib unavailable - please fix your python install'
    except Exception, e:
        return str(e)

def find(path, *opts):
    '''
    Approximate the Unix find(1) command and return a list of paths that
    meet the specified critera.

    The options include match criteria::

        name    = path-glob                 # case sensitive
        iname   = path-glob                 # case insensitive
        regex   = path-regex                # case sensitive
        iregex  = path-regex                # case insensitive
        type    = file-types                # match any listed type
        user    = users                     # match any listed user
        group   = groups                    # match any listed group
        size    = [+-]number[size-unit]     # default unit = byte
        mtime   = interval                  # modified since date
        grep    = regex                     # search file contents

    and/or actions::

        delete [= file-types]               # default type = 'f'
        exec    = command [arg ...]         # where {} is replaced by pathname
        print  [= print-opts]

    The default action is 'print=path'.

    file-glob::

        *                = match zero or more chars
        ?                = match any char
        [abc]            = match a, b, or c
        [!abc] or [^abc] = match anything except a, b, and c
        [x-y]            = match chars x through y
        [!x-y] or [^x-y] = match anything except chars x through y
        {a,b,c}          = match a or b or c

    path-regex:
        a Python re (regular expression) pattern to match pathnames

    file-types: a string of one or more of the following::

        a: all file types
        b: block device
        c: character device
        d: directory
        p: FIFO (named pipe)
        f: plain file
        l: symlink
        s: socket

    users:
        a space and/or comma separated list of user names and/or uids

    groups:
        a space and/or comma separated list of group names and/or gids

    size-unit::

        b: bytes
        k: kilobytes
        m: megabytes
        g: gigabytes
        t: terabytes

    interval::

        [<num>w] [<num>[d]] [<num>h] [<num>m] [<num>s]

        where:
            w: week
            d: day
            h: hour
            m: minute
            s: second

    print-opts: a comma and/or space separated list of one or more of the
    following::

        group: group name
        md5:   MD5 digest of file contents
        mode:  file permissions (as integer)
        mtime: last modification time (as time_t)
        name:  file basename
        path:  file absolute path
        size:  file size in bytes
        type:  file type
        user:  user name

    CLI Examples::

        salt '*' / type=f name=\*.bak size=+10m
        salt '*' /var mtime=+30d size=+10m print=path,size,mtime
        salt '*' /var/log name=\*.[0-9] mtime=+30d size=+10m delete
    '''
    opts_dict = {}
    for opt in opts:
        key, value = opt.split('=', 1)
        opts_dict[key] = value
    try:
        f = salt.utils.find.Finder(opts_dict)
    except ValueError, ex:
        return 'error: {0}'.format(ex)

    ret = [p for p in f.find(path)]
    ret.sort()
    return ret
