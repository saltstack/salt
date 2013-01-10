'''
Manage information about files on the minion, set/read user, group, and mode
data
'''

# TODO: We should add the capability to do u+r type operations here
# some time in the future

# Import python libs
from contextlib import nested  # For < 2.7 compat
import os
import re
import time
import shutil
import stat
import tempfile
import sys
import getpass
import hashlib
import difflib
import fnmatch
import errno
try:
    import grp
    import pwd
except ImportError:
    pass

# Import salt libs
import salt.utils
import salt.utils.find
from salt.utils.filebuffer import BufferedReader
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt._compat import string_types, urlparse


def __virtual__():
    '''
    Only work on posix-like systems
    '''
    # win_file takes care of windows
    if salt.utils.is_windows():
        return False
    return 'file'


def __clean_tmp(sfn):
    '''
    Clean out a template temp file
    '''
    if sfn.startswith(tempfile.gettempdir()):
        # Only clean up files that exist
        if os.path.exists(sfn):
            os.remove(sfn)


def _error(ret, err_msg):
    ret['result'] = False
    ret['comment'] = err_msg
    return ret


def _is_bin(path):
    '''
    Return True if a file is a bin, just checks for NULL char, this should be
    expanded to reflect how git checks for bins
    '''
    with salt.utils.fopen(path, 'rb') as ifile:
        return '\0' in ifile.read(2048)


def gid_to_group(gid):
    '''
    Convert the group id to the group name on this system

    CLI Example::

        salt '*' file.gid_to_group 0
    '''
    try:
        gid = int(gid)
    except ValueError:
        # This is not an integer, maybe it's already the group name?
        gid = group_to_gid(gid)

    if gid == '':
        # Don't even bother to feed it to grp
        return ''

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
    if not group:
        return ''
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
    if not user:
        user = getpass.getuser()
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
    mode = str(mode).lstrip('0')
    if not mode:
        mode = '0'
    if not os.path.exists(path):
        return 'File not found'
    try:
        os.chmod(path, int(mode, 8))
    except Exception:
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
        if user:
            err += 'User does not exist\n'
        else:
            uid = -1
    if gid == '':
        if group:
            err += 'Group does not exist\n'
        else:
            gid = -1
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
    user = get_user(path)
    return chown(path, user, group)


def get_sum(path, form='md5'):
    '''
    Return the sum for the given file, default is md5, sha1, sha224, sha256,
    sha384, sha512 are supported

    CLI Example::

        salt '*' file.get_sum /etc/passwd sha512
    '''
    if not os.path.isfile(path):
        return 'File not found'
    try:
        with salt.utils.fopen(path, 'rb') as ifile:
            return getattr(hashlib, form)(ifile.read()).hexdigest()
    except (IOError, OSError) as err:
        return 'File Error: {0}'.format(err)
    except AttributeError:
        return 'Hash {0} not supported'.format(form)
    except NameError:
        return 'Hashlib unavailable - please fix your python install'
    except Exception as err:
        return str(err)


def get_hash(path, form='md5', chunk_size=4096):
    '''
    Get the hash sum of a file

    This is better than ``get_sum`` for the following reasons:
        - It does not read the entire file into memory.
        - It does not return a string on error. The returned value of
            ``get_sum`` cannot really be trusted since it is vulnerable to
            collisions: ``get_sum(..., 'xyz') == 'Hash xyz not supported'``
    '''
    try:
        hash_type = getattr(hashlib, form)
    except AttributeError:
        raise ValueError('Invalid hash type: {0}'.format(form))
    with salt.utils.fopen(path, 'rb') as ifile:
        hash_obj = hash_type()
        while True:
            chunk = ifile.read(chunk_size)
            if not chunk:
                return hash_obj.hexdigest()
            hash_obj.update(chunk)


def check_hash(path, hash):
    '''
    Check if a file matches the given hash string

    Returns true if the hash matched, otherwise false. Raises ValueError if
    the hash was not formatted correctly.

    path
        A file path
    hash
        A string in the form <hash_type>=<hash_value>. For example:
        ``md5=e138491e9d5b97023cea823fe17bac22``
    '''
    hash_parts = hash.split('=', 1)
    if len(hash_parts) != 2:
        raise ValueError('Bad hash format: {!r}'.format(hash))
    hash_form, hash_value = hash_parts
    return get_hash(path, hash_form) == hash_value


def find(path, **kwargs):
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

        salt '*' file.find / type=f name=\*.bak size=+10m
        salt '*' file.find /var mtime=+30d size=+10m print=path,size,mtime
        salt '*' file.find /var/log name=\*.[0-9] mtime=+30d size=+10m delete
    '''
    try:
        finder = salt.utils.find.Finder(kwargs)
    except ValueError as ex:
        return 'error: {0}'.format(ex)

    ret = [p for p in finder.find(path)]
    ret.sort()
    return ret


def _sed_esc(string, escape_all=False):
    '''
    Escape single quotes and forward slashes
    '''
    special_chars = "^.[$()|*+?{"
    string = string.replace("'", "'\"'\"'").replace("/", "\/")
    if escape_all:
        for char in special_chars:
            string = string.replace(char, "\\" + char)
    return string


def sed(path, before, after, limit='', backup='.bak', options='-r -e',
        flags='g', escape_all=False):
    '''
    Make a simple edit to a file

    Equivalent to::

        sed <backup> <options> "/<limit>/ s/<before>/<after>/<flags> <file>"

    path
        The full path to the file to be edited
    before
        A pattern to find in order to replace with ``after``
    after
        Text that will replace ``before``
    limit : ``''``
        An initial pattern to search for before searching for ``before``
    backup : ``.bak``
        The file will be backed up before edit with this file extension;
        **WARNING:** each time ``sed``/``comment``/``uncomment`` is called will
        overwrite this backup
    options : ``-r -e``
        Options to pass to sed
    flags : ``g``
        Flags to modify the sed search; e.g., ``i`` for case-insensitve pattern
        matching

    Forward slashes and single quotes will be escaped automatically in the
    ``before`` and ``after`` patterns.

    CLI Example::

        salt '*' file.sed /etc/httpd/httpd.conf 'LogLevel warn' 'LogLevel info'

    .. versionadded:: 0.9.5
    '''
    # Largely inspired by Fabric's contrib.files.sed()
    # XXX:dc: Do we really want to always force escaping?
    #
    # Mandate that before and after are strings
    before = str(before)
    after = str(after)
    before = _sed_esc(before, escape_all)
    after = _sed_esc(after, escape_all)
    if sys.platform == 'darwin':
        options = options.replace('-r', '-E')

    cmd = r"sed {backup}{options} '{limit}s/{before}/{after}/{flags}' {path}".format(
            backup='-i{0} '.format(backup) if backup else '-i ',
            options=options,
            limit='/{0}/ '.format(limit) if limit else '',
            before=before,
            after=after,
            flags=flags,
            path=path)

    return __salt__['cmd.run'](cmd)


def uncomment(path, regex, char='#', backup='.bak'):
    '''
    Uncomment specified commented lines in a file

    path
        The full path to the file to be edited
    regex
        A regular expression used to find the lines that are to be uncommented.
        This regex should not include the comment character. A leading ``^``
        character will be stripped for convenience (for easily switching
        between comment() and uncomment()).
    char : ``#``
        The character to remove in order to uncomment a line; if a single
        whitespace character follows the comment it will also be removed
    backup : ``.bak``
        The file will be backed up before edit with this file extension;
        **WARNING:** each time ``sed``/``comment``/``uncomment`` is called will
        overwrite this backup

    CLI Example::

        salt '*' file.uncomment /etc/hosts.deny 'ALL: PARANOID'

    .. versionadded:: 0.9.5
    '''
    # Largely inspired by Fabric's contrib.files.uncomment()

    return __salt__['file.sed'](path,
        before=r'^([[:space:]]*){0}[[:space:]]?'.format(char),
        after=r'\1',
        limit=regex.lstrip('^'),
        backup=backup)


def comment(path, regex, char='#', backup='.bak'):
    '''
    Comment out specified lines in a file

    path
        The full path to the file to be edited
    regex
        A regular expression used to find the lines that are to be commented;
        this pattern will be wrapped in parenthesis and will move any
        preceding/trailing ``^`` or ``$`` characters outside the parenthesis
        (e.g., the pattern ``^foo$`` will be rewritten as ``^(foo)$``)
    char : ``#``
        The character to be inserted at the beginning of a line in order to
        comment it out
    backup : ``.bak``
        The file will be backed up before edit with this file extension

        .. warning::

            This backup will be overwritten each time ``sed`` / ``comment`` /
            ``uncomment`` is called. Meaning the backup will only be useful
            after the first invocation.

    CLI Example::

        salt '*' file.comment /etc/modules pcspkr

    .. versionadded:: 0.9.5
    '''
    # Largely inspired by Fabric's contrib.files.comment()

    regex = '{0}({1}){2}'.format(
            '^' if regex.startswith('^') else '',
            regex.lstrip('^').rstrip('$'),
            '$' if regex.endswith('$') else '')

    return __salt__['file.sed'](
        path,
        before=regex,
        after=r'{0}\1'.format(char),
        backup=backup)


def patch(originalfile, patchfile, options='', dry_run=False):
    '''
    Apply a patch to a file

    Equivalent to::

        patch <options> <originalfile> <patchfile>

    originalfile
        The full path to the file or directory to be patched
    patchfile
        A patch file to apply to ``originalfile``
    options
        Options to pass to patch.

    CLI Example::

        salt '*' file.patch /opt/file.txt /tmp/file.txt.patch

    .. versionadded:: 0.10.4
    '''
    if dry_run:
        if __grains__['kernel'] in ('FreeBSD', 'OpenBSD'):
            dry_run_opt = ' -C'
        else:
            dry_run_opt = ' --dry-run'
    else:
        dry_run_opt = ''
    cmd = 'patch {0}{1} {2} {3}'.format(
        options, dry_run_opt, originalfile, patchfile)
    return __salt__['cmd.run_all'](cmd)


def contains(path, text):
    '''
    Return True if the file at ``path`` contains ``text``

    CLI Example::

        salt '*' file.contains /etc/crontab 'mymaintenance.sh'

    .. versionadded:: 0.9.5
    '''
    if not os.path.exists(path):
        return False

    stripped_text = text.strip()
    try:
        with BufferedReader(path) as breader:
            for chunk in breader:
                if stripped_text in chunk:
                    return True
        return False
    except (IOError, OSError):
        return False


def contains_regex(path, regex, lchar=''):
    '''
    Return True if the given regular expression matches anything in the text
    of a given file

    CLI Example::

        salt '*' /etc/crontab '^maint'
    '''
    if not os.path.exists(path):
        return False

    try:
        with BufferedReader(path) as breader:
            for chunk in breader:
                if lchar:
                    chunk = chunk.lstrip(lchar)
                if re.search(regex, chunk, re.MULTILINE):
                    return True
            return False
    except (IOError, OSError):
        return False


def contains_glob(path, glob):
    '''
    Return True if the given glob matches a string in the named file

    CLI Example::

        salt '*' /etc/foobar '*cheese*'
    '''
    if not os.path.exists(path):
        return False

    try:
        with BufferedReader(path) as breader:
            for chunk in breader:
                if fnmatch.fnmatch(chunk, glob):
                    return True
            return False
    except (IOError, OSError):
        return False


def append(path, *args):
    '''
    Append text to the end of a file

    CLI Example::

        salt '*' file.append /etc/motd \\
                "With all thine offerings thou shalt offer salt."\\
                "Salt is what makes things taste bad when it isn't in them."

    .. versionadded:: 0.9.5
    '''
    # Largely inspired by Fabric's contrib.files.append()

    with salt.utils.fopen(path, "a") as ofile:
        for line in args:
            ofile.write('{0}\n'.format(line))

    return 'Wrote {0} lines to "{1}"'.format(len(args), path)


def touch(name, atime=None, mtime=None):
    '''
    Just like 'nix's "touch" command, create a file if it
    doesn't exist or simply update the atime and mtime if
    it already does.

    atime:
        Access time in Unix epoch time
    mtime:
        Last modification in Unix epoch time

    CLI Example::

        salt '*' file.touch /var/log/emptyfile

    .. versionadded:: 0.9.5
    '''
    if atime and atime.isdigit():
        atime = int(atime)
    if mtime and mtime.isdigit():
        mtime = int(mtime)
    try:
        if not os.path.exists(name):
            salt.utils.fopen(name, 'a')

        if not atime and not mtime:
            times = None
        elif not mtime and atime:
            times = (atime, time.time())
        elif not atime and mtime:
            times = (time.time(), mtime)
        else:
            times = (atime, mtime)
        os.utime(name, times)

    except TypeError:
        raise SaltInvocationError('atime and mtime must be integers')
    except (IOError, OSError) as exc:
        raise CommandExecutionError(exc.strerror)

    return os.path.exists(name)


def stats(path, hash_type='md5', follow_symlink=False):
    '''
    Return a dict containing the stats for a given file

    CLI Example::

        salt '*' file.stats /etc/passwd
    '''
    ret = {}
    if not os.path.exists(path):
        return ret
    if follow_symlink:
        pstat = os.stat(path)
    else:
        pstat = os.lstat(path)
    ret['inode'] = pstat.st_ino
    ret['uid'] = pstat.st_uid
    ret['gid'] = pstat.st_gid
    ret['group'] = gid_to_group(pstat.st_gid)
    ret['user'] = uid_to_user(pstat.st_uid)
    ret['atime'] = pstat.st_atime
    ret['mtime'] = pstat.st_mtime
    ret['ctime'] = pstat.st_ctime
    ret['size'] = pstat.st_size
    ret['mode'] = str(oct(stat.S_IMODE(pstat.st_mode)))
    ret['sum'] = get_sum(path, hash_type)
    ret['type'] = 'file'
    if stat.S_ISDIR(pstat.st_mode):
        ret['type'] = 'dir'
    if stat.S_ISCHR(pstat.st_mode):
        ret['type'] = 'char'
    if stat.S_ISBLK(pstat.st_mode):
        ret['type'] = 'block'
    if stat.S_ISREG(pstat.st_mode):
        ret['type'] = 'file'
    if stat.S_ISLNK(pstat.st_mode):
        ret['type'] = 'link'
    if stat.S_ISFIFO(pstat.st_mode):
        ret['type'] = 'pipe'
    if stat.S_ISSOCK(pstat.st_mode):
        ret['type'] = 'socket'
    ret['target'] = os.path.realpath(path)
    return ret


def remove(path):
    if not os.path.isabs(path):
        raise SaltInvocationError('File path must be absolute.')

    try:
        if os.path.isfile(path) or os.path.islink(path):
            os.remove(path)
            return True
        elif os.path.isdir(path):
            shutil.rmtree(path)
            return True
    except (OSError, IOError):
        raise CommandExecutionError('Could not remove "{0}"'.format(path))
    return False


def directory_exists(path):
    '''
    Tests to see if path is a valid directory.  Returns True/False.

    CLI Example::

        salt '*' file.directory_exists /etc

    '''
    return os.path.isdir(path)


def file_exists(path):
    '''
    Tests to see if path is a valid file.  Returns True/False.

    CLI Example::

        salt '*' file.file_exists /etc/passwd

    '''
    return os.path.isfile(path)


def restorecon(path, recursive=False):
    '''
    Reset the SELinux context on a given path

    CLI Example::

         salt '*' selinux.restorecon /home/user/.ssh/authorized_keys
    '''
    if recursive:
        cmd = 'restorecon -FR {0}'.format(path)
    else:
        cmd = 'restorecon -F {0}'.format(path)
    return not __salt__['cmd.retcode'](cmd)


def get_selinux_context(path):
    '''
    Get an SELinux context from a given path

    CLI Example::

        salt '*' selinux.get_context /etc/hosts
    '''
    out = __salt__['cmd.run']('ls -Z {0}'.format(path))
    return out.split(' ')[4]


def set_selinux_context(path, user=None, role=None, type=None, range=None):
    '''
    Set a specific SELinux label on a given path

    CLI Example::

        salt '*' selinux.chcon path <role> <type> <range>
    '''
    if not user and not role and not type and not range:
        return False

    cmd = 'chcon '
    if user:
        cmd += '-u {0} '.format(user)
    if role:
        cmd += '-r {0} '.format(role)
    if type:
        cmd += '-t {0} '.format(type)
    if range:
        cmd += '-l {0} '.format(range)

    cmd += path
    ret = not __salt__['cmd.retcode'](cmd)
    if ret:
        return get_selinux_context(path)
    else:
        return ret


def source_list(source, source_hash, env):
    '''
    Check the source list and return the source to use
    '''
    if isinstance(source, list):
        # get the master file list
        mfiles = __salt__['cp.list_master'](env)
        mdirs = __salt__['cp.list_master_dirs'](env)
        for single in source:
            if isinstance(single, dict):
                # check the proto, if it is http or ftp then download the file
                # to check, if it is salt then check the master list
                if len(single) != 1:
                    continue
                single_src = next(iter(single))
                single_hash = single[single_src]
                proto = urlparse(single_src).scheme
                if proto == 'salt':
                    if single_src in mfiles:
                        source = single_src
                        break
                elif proto.startswith('http') or proto == 'ftp':
                    dest = salt.utils.mkstemp()
                    fn_ = __salt__['cp.get_url'](single_src, dest)
                    os.remove(fn_)
                    if fn_:
                        source = single_src
                        source_hash = single_hash
                        break
            elif isinstance(single, string_types):
                if single[7:] in mfiles or single[7:] in mdirs:
                    source = single
                    break
    return source, source_hash


def get_managed(
        name,
        template,
        source,
        source_hash,
        user,
        group,
        mode,
        env,
        context,
        defaults,
        **kwargs):
    '''
    Return the managed file data for file.managed
    '''
    # If the file is a template and the contents is managed
    # then make sure to copy it down and templatize  things.
    sfn = ''
    source_sum = {}
    if template and source:
        sfn = __salt__['cp.cache_file'](source, env)
        if not os.path.exists(sfn):
            return sfn, {}, 'File "{0}" could not be found'.format(sfn)
        if template in salt.utils.templates.TEMPLATE_REGISTRY:
            context_dict = defaults if defaults else {}
            if context:
                context_dict.update(context)
            data = salt.utils.templates.TEMPLATE_REGISTRY[template](
                    sfn,
                    name=name,
                    source=source,
                    user=user,
                    group=group,
                    mode=mode,
                    env=env,
                    context=context_dict,
                    salt=__salt__,
                    pillar=__pillar__,
                    grains=__grains__,
                    opts=__opts__,
                    **kwargs
                    )
        else:
            return sfn, {}, ('Specified template format {0} is not supported'
                      ).format(template)

        if data['result']:
            sfn = data['data']
            hsum = get_hash(sfn)
            source_sum = {'hash_type': 'md5',
                          'hsum': hsum}
        else:
            __clean_tmp(sfn)
            return sfn, {}, data['data']
    else:
        # Copy the file down if there is a source
        if source:
            if urlparse(source).scheme == 'salt':
                source_sum = __salt__['cp.hash_file'](source, env)
                if not source_sum:
                    return '', {}, 'Source file {0} not found'.format(source)
            elif source_hash:
                protos = ['salt', 'http', 'ftp']
                if urlparse(source_hash).scheme in protos:
                    # The source_hash is a file on a server
                    hash_fn = __salt__['cp.cache_file'](source_hash)
                    if not hash_fn:
                        return '', {}, 'Source hash file {0} not found'.format(
                             source_hash)
                    hash_fn_fopen = salt.utils.fopen(hash_fn, 'r')
                    for line in hash_fn_fopen.read().splitlines():
                        line = line.strip()
                        if ' ' not in line:
                            hashstr = line
                            break
                        elif line.startswith('{0} '.format(name)):
                            hashstr = line.split()[1]
                            break
                    else:
                        hashstr = ''  # NOT FOUND
                    comps = hashstr.split('=')
                    if len(comps) < 2:
                        return '', {}, ('Source hash file {0} contains an '
                                  'invalid hash format, it must be in '
                                  'the format <hash type>=<hash>'
                                  ).format(source_hash)
                    source_sum['hsum'] = comps[1].strip()
                    source_sum['hash_type'] = comps[0].strip()
                else:
                    # The source_hash is a hash string
                    comps = source_hash.split('=')
                    if len(comps) < 2:
                        return '', {}, ('Source hash file {0} contains an '
                                  'invalid hash format, it must be in '
                                  'the format <hash type>=<hash>'
                                  ).format(source_hash)
                    source_sum['hsum'] = comps[1].strip()
                    source_sum['hash_type'] = comps[0].strip()
            else:
                return '', {}, ('Unable to determine upstream hash of'
                          ' source file {0}').format(source)
    return sfn, source_sum, ''


def check_perms(name, ret, user, group, mode):
    '''
    Check the permissions on files and chown if needed

    Note: 'mode' here is expected to be either a string or an integer,
          in which case it will be converted into a base-10 string.

          What this means is that in your YAML salt file, you can specify
          mode as an integer(eg, 644) or as a string(eg, '644'). But, to
          specify mode 0777, for example, it must be specified as the string,
          '0777' otherwise, 0777 will be parsed as an octal and you'd get 511
          instead.
    '''
    if not ret:
        ret = {'name': name,
               'changes': {},
               'comment': [],
               'result': True}
        orig_comment = ''
    else:
        orig_comment = ret['comment']
        ret['comment'] = []

    # Check permissions
    perms = {}
    perms['luser'] = __salt__['file.get_user'](name)
    perms['lgroup'] = __salt__['file.get_group'](name)
    perms['lmode'] = str(__salt__['file.get_mode'](name)).lstrip('0')

    # Mode changes if needed
    if mode:
        if str(mode) != perms['lmode']:
            if not __opts__['test']:
                __salt__['file.set_mode'](name, mode)
            if str(mode) != __salt__['file.get_mode'](name).lstrip('0'):
                ret['result'] = False
                ret['comment'].append(
                    'Failed to change mode to {0}'.format(mode)
                )
            else:
                ret['changes']['mode'] = mode
    # user/group changes if needed, then check if it worked
    if user:
        if user != perms['luser']:
            perms['cuser'] = user
    if group:
        if group != perms['lgroup']:
            perms['cgroup'] = group
    if 'cuser' in perms or 'cgroup' in perms:
        if not __opts__['test']:
            if user is None:
                user = perms['luser']
            if group is None:
                group = perms['lgroup']
            try:
                __salt__['file.chown'](name, user, group)
            except OSError:
                ret['result'] = False

    if user:
        if user != __salt__['file.get_user'](name):
            ret['result'] = False
            ret['comment'].append('Failed to change user to {0}'.format(user))
        elif 'cuser' in perms:
            ret['changes']['user'] = user
    if group:
        if group != __salt__['file.get_group'](name):
            ret['result'] = False
            ret['comment'].append('Failed to change group to {0}'
                               .format(group))
        elif 'cgroup' in perms:
            ret['changes']['group'] = group

    if isinstance(orig_comment, basestring):
        if orig_comment:
            ret['comment'].insert(0, orig_comment)
        ret['comment'] = '; '.join(ret['comment'])
    return ret, perms


def check_managed(
        name,
        source,
        source_hash,
        user,
        group,
        mode,
        template,
        makedirs,
        context,
        defaults,
        env,
        **kwargs):
    '''
    Check to see what changes need to be made for a file
    '''
    # If the source is a list then find which file exists
    source, source_hash = source_list(source, source_hash, env)

    # Gather the source file from the server
    sfn, source_sum, comment = get_managed(
            name,
            template,
            source,
            source_hash,
            user,
            group,
            mode,
            env,
            context,
            defaults,
            **kwargs
            )
    if comment:
        __clean_tmp(sfn)
        return False, comment
    changes = check_file_meta(name, sfn, source, source_sum, user,
                              group, mode, env)
    __clean_tmp(sfn)
    if changes:
        comment = 'The following values are set to be changed:\n'
        for key, val in changes.items():
            comment += '{0}: {1}\n'.format(key, val)
        return None, comment
    return True, 'The file {0} is in the correct state'.format(name)


def check_file_meta(
        name,
        sfn,
        source,
        source_sum,
        user,
        group,
        mode,
        env):
    '''
    Check for the changes in the file metadata
    '''
    changes = {}
    stats = __salt__['file.stats'](
            name,
            source_sum.get('hash_type'), 'md5')
    if not stats:
        changes['newfile'] = name
        return changes
    if 'hsum' in source_sum:
        if source_sum['hsum'] != stats['sum']:
            if not sfn and source:
                sfn = __salt__['cp.cache_file'](source, env)
            if sfn:
                with nested(salt.utils.fopen(sfn, 'rb'),
                            salt.utils.fopen(name, 'rb')) as (src, name_):
                    slines = src.readlines()
                    nlines = name_.readlines()
                changes['diff'] = (
                        ''.join(difflib.unified_diff(nlines, slines))
                        )
            else:
                changes['sum'] = 'Checksum differs'
    if not user is None and user != stats['user']:
        changes['user'] = user
    if not group is None and group != stats['group']:
        changes['group'] = group
    # Normalize the file mode
    smode = __salt__['config.manage_mode'](stats['mode'])
    mode = __salt__['config.manage_mode'](mode)
    if not mode is None and mode != smode:
        changes['mode'] = mode
    return changes


def get_diff(
        minionfile,
        masterfile,
        env='base'):
    '''
    Return unified diff of file compared to file on master

    Example:

        salt \* file.get_diff /home/fred/.vimrc salt://users/fred/.vimrc
    '''
    ret = ''

    if not os.path.exists(minionfile):
        ret = 'File {0} does not exist on the minion'.format(minionfile)
        return ret

    sfn = __salt__['cp.cache_file'](masterfile, env)
    if sfn:
        with nested(salt.utils.fopen(sfn, 'r'),
                    salt.utils.fopen(minionfile, 'r')) as (src, name_):
            slines = src.readlines()
            nlines = name_.readlines()
        diff = difflib.unified_diff(nlines, slines, minionfile, masterfile)
        if diff:
            for line in diff:
                ret = ret + line
    else:
        ret = 'Failed to copy file from master'

    return ret


def manage_file(name,
        sfn,
        ret,
        source,
        source_sum,
        user,
        group,
        mode,
        env,
        backup):
    '''
    Checks the destination against what was retrieved with get_managed and
    makes the appropriate modifications (if necessary).
    '''
    if not ret:
        ret = {'name': name,
               'changes': {},
               'comment': '',
               'result': True}
    # Check changes if the target file exists
    if os.path.isfile(name):
        # Only test the checksums on files with managed contents
        if source:
            name_sum = get_hash(name, source_sum['hash_type'])

        # Check if file needs to be replaced
        if source and source_sum['hsum'] != name_sum:
            if not sfn:
                sfn = __salt__['cp.cache_file'](source, env)
            if not sfn:
                return _error(
                    ret, 'Source file {0} not found'.format(source))
            # If the downloaded file came from a non salt server source verify
            # that it matches the intended sum value
            if urlparse(source).scheme != 'salt':
                with salt.utils.fopen(sfn, 'rb') as dlfile:
                    dl_sum = get_hash(sfn, source_sum['hash_type'])
                if dl_sum != source_sum['hsum']:
                    ret['comment'] = ('File sum set for file {0} of {1} does '
                                      'not match real sum of {2}'
                                      ).format(
                                              name,
                                              source_sum['hsum'],
                                              dl_sum
                                              )
                    ret['result'] = False
                    return ret

            # Check to see if the files are bins
            if _is_bin(sfn) or _is_bin(name):
                ret['changes']['diff'] = 'Replace binary file'
            else:
                with nested(salt.utils.fopen(sfn, 'rb'),
                            salt.utils.fopen(name, 'rb')) as (src, name_):
                    slines = src.readlines()
                    nlines = name_.readlines()
                # Print a diff equivalent to diff -u old new
                    ret['changes']['diff'] = (''.join(difflib
                                                      .unified_diff(nlines,
                                                                    slines)))
            # Pre requisites are met, and the file needs to be replaced, do it
            try:
                salt.utils.copyfile(
                        sfn,
                        name,
                        __salt__['config.backup_mode'](backup),
                        __opts__['cachedir'])
            except IOError:
                __clean_tmp(sfn)
                return _error(
                    ret, 'Failed to commit change, permission error')

        ret, perms = check_perms(name, ret, user, group, mode)

        if ret['changes']:
            ret['comment'] = 'File {0} updated'.format(name)

        elif not ret['changes'] and ret['result']:
            ret['comment'] = 'File {0} is in the correct state'.format(name)
        __clean_tmp(sfn)
        return ret
    else:
        # Only set the diff if the file contents is managed
        if source:
            # It is a new file, set the diff accordingly
            ret['changes']['diff'] = 'New file'
            # Apply the new file
            if not sfn:
                sfn = __salt__['cp.cache_file'](source, env)
            if not sfn:
                return ret.error(
                    ret, 'Source file {0} not found'.format(source))
            # If the downloaded file came from a non salt server source verify
            # that it matches the intended sum value
            if urlparse(source).scheme != 'salt':
                dl_sum = get_hash(name, source_sum['hash_type'])
                if dl_sum != source_sum['hsum']:
                    ret['comment'] = ('File sum set for file {0} of {1} does '
                                      'not match real sum of {2}'
                                      ).format(
                                              name,
                                              source_sum['hsum'],
                                              dl_sum
                                              )
                    ret['result'] = False
                    return ret

            if not os.path.isdir(os.path.dirname(name)):
                if makedirs:
                    makedirs(name, user=user, group=group, mode=mode)
                else:
                    __clean_tmp(sfn)
                    return _error(ret, 'Parent directory not present')
        else:
            if not os.path.isdir(os.path.dirname(name)):
                if makedirs:
                    makedirs(name, user=user, group=group, mode=mode)
                else:
                    __clean_tmp(sfn)
                    return _error(ret, 'Parent directory not present')

            # Create the file, user rw-only if mode will be set to prevent
            # a small security race problem before the permissions are set
            if mode:
                current_umask = os.umask(63)

            # Create a new file when test is False and source is None
            if not __opts__['test']:
                if __salt__['file.touch'](name):
                    ret['changes']['new'] = 'file {0} created'.format(name)
                    ret['comment'] = 'Empty file'
                else:
                    return _error(
                        ret, 'Empty file {0} not created'.format(name)
                    )

            if mode:
                os.umask(current_umask)

        # Now copy the file contents if there is a source file
        if sfn:
            salt.utils.copyfile(
                    sfn,
                    name,
                    __salt__['config.backup_mode'](backup),
                    __opts__['cachedir'])
            __clean_tmp(sfn)

        # Check and set the permissions if necessary
        ret, perms = check_perms(name, ret, user, group, mode)

        if not ret['comment']:
            ret['comment'] = 'File ' + name + ' updated'

        if __opts__['test']:
            ret['comment'] = 'File ' + name + ' not updated'
        elif not ret['changes'] and ret['result']:
            ret['comment'] = 'File ' + name + ' is in the correct state'
        __clean_tmp(sfn)
        return ret


def makedirs(path, user=None, group=None, mode=None):
    '''
    Ensure that the directory containing this path is available.
    '''
    directory = os.path.dirname(path)

    if not os.path.isdir(directory):
        # turn on the executable bits for user, group and others.
        # Note: the special bits are set to 0.
        if mode:
            mode = int(str(mode)[-3:], 8) | 0111

        makedirs_perms(directory, user, group, mode)
        # If a caller such as managed() is invoked  with
        # makedirs=True, make sure that any created dirs
        # are created with the same user  and  group  to
        # follow the principal of least surprise method.


def makedirs_perms(name, user=None, group=None, mode=0755):
    '''
    Taken and modified from os.makedirs to set user, group and mode for each
    directory created.
    '''
    path = os.path
    mkdir = os.mkdir
    head, tail = path.split(name)
    if not tail:
        head, tail = path.split(head)
    if head and tail and not path.exists(head):
        try:
            makedirs_perms(head, user, group, mode)
        except OSError as exc:
            # be happy if someone already created the path
            if exc.errno != errno.EEXIST:
                raise
        if tail == os.curdir:  # xxx/newdir/. exists if xxx/newdir exists
            return
    mkdir(name)
    check_perms(
            name,
            None,
            user,
            group,
            int('{0}'.format(mode)) if mode else None)
