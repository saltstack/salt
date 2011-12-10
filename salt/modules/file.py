'''
Manage information about files on the minion, set/read user, group, and mode
data
'''

# TODO: We should add the capability to do u+r type operations here
# some time in the future

import grp
import hashlib
import os
import pwd

import salt.utils.find


def gid_to_group(gid):
    '''
    Convert the group id to the group name on this system

    CLI Example::

        salt '*' file.gid_to_group 0
    '''
    try:
        return grp.getgrgid(gid).gr_name
    except KeyError:
        return ''


def group_to_gid(group):
    '''
    Convert the group to the gid on this system

    CLI Example::

        salt '*' file.group_to_gid root
    '''
    try:
        return grp.getgrnam(group).gr_gid
    except KeyError:
        return ''


def get_gid(path):
    '''
    Return the id of the group that owns a given file

    CLI Example::

        salt '*' file.get_gid /etc/passwd
    '''
    if not os.path.exists(path):
        return -1
    return os.stat(path).st_gid


def get_group(path):
    '''
    Return the group that owns a given file

    CLI Example::

        salt '*' file.get_group /etc/passwd
    '''
    gid = get_gid(path)
    if gid == -1:
        return False
    return gid_to_group(gid)


def uid_to_user(uid):
    '''
    Convert a uid to a user name

    CLI Example::

        salt '*' file.uid_to_user 0
    '''
    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return ''


def user_to_uid(user):
    '''
    Convert user name to a uid

    CLI Example::

        salt '*' file.user_to_uid root
    '''
    try:
        return pwd.getpwnam(user).pw_uid
    except KeyError:
        return ''


def get_uid(path):
    '''
    Return the id of the user that owns a given file

    CLI Example::

        salt '*' file.get_uid /etc/passwd
    '''
    if not os.path.exists(path):
        return False
    return os.stat(path).st_uid


def get_user(path):
    '''
    Return the user that owns a given file

    CLI Example::

        salt '*' file.get_user /etc/passwd
    '''
    uid = get_uid(path)
    if uid == -1:
        return False
    return uid_to_user(uid)


def get_mode(path):
    '''
    Return the mode of a file

    CLI Example::

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
    Set the mode of a file

    CLI Example::

        salt '*' file.set_mode /etc/passwd 0644
    '''
    mode = str(mode)
    if not os.path.exists(path):
        return 'File not found'
    try:
        os.chmod(path, int(mode, 8))
    # FIXME: don't use a catch-all, be more specific...
    except:
        return 'Invalid Mode ' + mode
    return get_mode(path)


def chown(path, user, group):
    '''
    Chown a file, pass the file the desired user and group

    CLI Example::

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

    CLI Example::

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

    CLI Example::

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

    path-regex: a Python re (regular expression) pattern to match pathnames

    file-types: a string of one or more of the following::

        a: all file types
        b: block device
        c: character device
        d: directory
        p: FIFO (named pipe)
        f: plain file
        l: symlink
        s: socket

    users: a space and/or comma separated list of user names and/or uids

    groups: a space and/or comma separated list of group names and/or gids

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

def sed_esc(s):
    '''
    Escape single quotes and forward slashes
    '''
    return s.replace("'", "'\"'\"'").replace("/", "\/")

def sed(path, before, after, limit='', backup='.bak', options='-r -e',
        flags='g'):
    '''
    Make a simple edit to a file

    Equivalent to::

        sed <backup> <options> "/<limit>/ s/<before>/<after>/<flags> <file>"

    For convenience, ``before`` and ``after`` will automatically escape forward
    slashes, single quotes and parentheses for you, so you don't need to
    specify e.g.  ``http:\/\/foo\.com``, instead just using ``http://foo\.com``
    is fine.

    Usage::

        salt '*' file.sed /etc/httpd/httpd.conf 'LogLevel warn' 'LogLevel info'

    .. versionadded:: 0.9.5
    '''
    # This is largely stolen from Fabric's contrib.files.sed()

    before = sed_esc(before)
    after = sed_esc(after)
    after = after.replace("(", r"\(").replace(")", r"\)")

    cmd = r"sed {backup}{options} '{limit}s/{before}/{after}/{flags}' {path}".format(
            backup = '-i{0} '.format(backup) if backup else '',
            options = options,
            limit = '/{0}/ '.format(limit) if limit else '',
            before = before,
            after = after,
            flags = flags,
            path = path)

    return __salt__['cmd.run'](cmd)

def uncomment(path, regex, char='#', backup='.bak'):
    '''
    Uncomment specified commented lines in a file

    The default comment delimiter is `#` and may be overridden by the ``char``
    argument.

    `uncomment` will remove a single whitespace character following the comment
    character, if it exists, but will preserve all preceding whitespace.  For
    example, ``# foo`` would become ``foo`` (the single space is stripped) but
    ``    # foo`` would become ``    foo`` (the single space is still stripped,
    but the preceding 4 spaces are not.)

    Usage::

        salt '*' file.uncomment /etc/hosts.deny 'ALL: PARANOID'

    .. versionadded:: 0.9.5
    '''
    # This is largely stolen from Fabric's contrib.files.uncomment()

    return __salt__['file.sed'](path,
        before=r'^([[:space:]]*){0}[[:space:]]?'.format(char),
        after=r'\1',
        limit=regex,
        backup=backup)

def comment(path, regex, char='#', backup='.bak'):
    '''
    Comment out specified lines in a file

    The default commenting character is `#` and may be overridden by the
    ``char`` argument.

    `comment` will prepend the comment character to the very beginning of the
    line, so that lines end up looking like so::

        this line is uncommented
        #this line is commented
        #   this line is indented and commented

    .. note::

        In order to preserve the line being commented out, this function will
        wrap your ``regex`` argument in parentheses, so you don't need to. It
        will ensure that any preceding/trailing ``^`` or ``$`` characters are
        correctly moved outside the parentheses. For example, calling
        ``comment(filename, r'^foo$')`` will result in a `sed` call with the
        "before" regex of ``r'^(foo)$'`` (and the "after" regex, naturally, of
        ``r'#\\1'``.)

    Usage::

        salt '*' file.comment /etc/modules pcspkr

    .. versionadded:: 0.9.5
    '''
    # This is largely stolen from Fabric's contrib.files.comment()

    carot, dollar = '', ''

    if regex.startswith('^'):
        carot = '^'
        regex = regex[1:]

    if regex.endswith('$'):
        dollar = '$'
        regex = regex[:-1]

    regex = "{0}({1}){2}".format(carot, regex, dollar)

    return __salt__['file.sed'](
        path,
        before=regex,
        after=r'{0}\1'.format(char),
        backup=backup)

def contains(path, text, limit=''):
    '''
    Return True if the file at ``path`` contains ``text``

    Usage::

        salt '*' file.contains /etc/crontab 'mymaintenance.sh'

    .. versionadded:: 0.9.5
    '''
    # This is largely inspired by Fabric's contrib.files.contains()

    if not os.path.exists(path):
        return False

    result = __salt__['filenew.sed'](path, text, '&', limit=limit, backup='',
            options='-n -r -e', flags='gp')

    return bool(result)

def append(path, *args):
    '''
    Append text to the end of a file

    Usage::

        salt '*' file.append /etc/motd \\
                "With all thine offerings thou shalt offer salt."\\
                "Salt is what makes things taste bad when it isn't in them."

    .. versionadded:: 0.9.5
    '''
    # This is largely inspired by Fabric's contrib.files.append()

    with open(path, "a") as f:
        for line in args:
            f.write('{0}\n'.format(line))

    return "Wrote {0} lines to '{1}'".format(len(args), path)
