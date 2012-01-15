'''
Approximate the Unix find(1) command and return a list of paths that
meet the specified criteria.

The options include match criteria:
    name    = file-glob                 # case sensitive
    iname   = file-glob                 # case insensitive
    regex   = file-regex                # case sensitive
    iregex  = file-regex                # case insensitive
    type    = file-types                # match any listed type
    user    = users                     # match any listed user
    group   = groups                    # match any listed group
    size    = [+-]number[size-unit]     # default unit = byte
    mtime   = interval                  # modified since date
    grep    = regex                     # search file contents
and/or actions:
    delete [= file-types]               # default type = 'f'
    exec    = command [arg ...]         # where {} is replaced by pathname
    print  [= print-opts]

The default action is 'print=path'.

file-glob:
    *                = match zero or more chars
    ?                = match any char
    [abc]            = match a, b, or c
    [!abc] or [^abc] = match anything except a, b, and c
    [x-y]            = match chars x through y
    [!x-y] or [^x-y] = match anything except chars x through y
    {a,b,c}          = match a or b or c

file-regex:
    a Python re (regular expression) pattern

file-types: a string of one or more of the following:
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

size-unit:
    b: bytes
    k: kilobytes
    m: megabytes
    g: gigabytes
    t: terabytes

interval:
    [<num>w] [<num>[d]] [<num>h] [<num>m] [<num>s]

    where:
        w: week
        d: day
        h: hour
        m: minute
        s: second

print-opts: a comma and/or space separated list of one or more of the following:
    group: group name
    md5:   MD5 digest of file contents
    mode:  file permissions (as integer)
    mtime: last modification time (as time_t)
    name:  file basename
    path:  file absolute path
    size:  file size in bytes
    type:  file type
    user:  user name
'''

import grp
import hashlib
import logging
import os
import pwd
import re
import stat
import sys
import time


# Set up logger
log = logging.getLogger(__name__)

_REQUIRES_PATH = 1
_REQUIRES_STAT = 2
_REQUIRES_CONTENTS = 4

_FILE_TYPES = {'b': stat.S_IFBLK,
               'c': stat.S_IFCHR,
               'd': stat.S_IFDIR,
               'f': stat.S_IFREG,
               'l': stat.S_IFLNK,
               'p': stat.S_IFIFO,
               's': stat.S_IFSOCK,
               stat.S_IFBLK: 'b',
               stat.S_IFCHR: 'c',
               stat.S_IFDIR: 'd',
               stat.S_IFREG: 'f',
               stat.S_IFLNK: 'l',
               stat.S_IFIFO: 'p',
               stat.S_IFSOCK: 's'}

_INTERVAL_REGEX = re.compile(r'''
                            ^\s*
                            (?: (?P<week>   \d+ (?:\.\d*)? ) \s* [wW]  )? \s*
                            (?: (?P<day>    \d+ (?:\.\d*)? ) \s* [dD]? )? \s*
                            (?: (?P<hour>   \d+ (?:\.\d*)? ) \s* [hH]  )? \s*
                            (?: (?P<minute> \d+ (?:\.\d*)? ) \s* [mM]  )? \s*
                            (?: (?P<second> \d+ (?:\.\d*)? ) \s* [sS]  )? \s*
                            $
                            ''',
                            flags=re.VERBOSE)


def _parse_interval(value):
    '''
    Convert an interval string like 1w3d6h into the number of seconds and the
    time resolution (1 unit of the smallest specified time unit).
        w = week
        d = day
        h = hour
        m = minute
        s = second
    '''
    m = _INTERVAL_REGEX.match(value)
    if m is None:
        raise ValueError('invalid time interval: "{0}"'.format(value))

    result = 0
    resolution = None
    for name, multiplier in [('second', 1),
                             ('minute', 60),
                             ('hour',   60 * 60),
                             ('day',    60 * 60 * 24),
                             ('week',   60 * 60 * 24 * 7)]:
        if m.group(name) is not None:
            result += float(m.group(name)) * multiplier
            if resolution is None:
                resolution = multiplier

    return result, resolution


def _parse_size(value):
    scalar = value.strip()

    if scalar.startswith(('-', '+')):
        style = scalar[0]
        scalar = scalar[1:]
    else:
        style = '='

    if len(scalar) > 0:
        multiplier = {'k': 2 ** 10,
                      'm': 2 ** 20,
                      'g': 2 ** 30,
                      't': 2 ** 40}.get(scalar[-1])
        if multiplier:
            scalar = scalar[:-1].strip()
        else:
            multiplier = 1
    else:
        multiplier = 1

    try:
        num = int(scalar) * multiplier
    except ValueError:
        try:
            num = int(float(scalar) * multiplier)
        except ValueError:
            raise ValueError('invalid size: "{0}"'.format(value))

    if style == '-':
        min_size = 0
        max_size = num
    elif style == '+':
        min_size = num
        max_size = sys.maxint
    else:
        min_size = num
        max_size = num + multiplier - 1

    return min_size, max_size


class Option(object):
    '''
    Abstract base class for all find options.
    '''
    def requires(self):
        return _REQUIRES_PATH


class NameOption(Option):
    '''
    Match files with a case-sensitive glob filename pattern.
    Note: this is the 'basename' portion of a pathname.
    The option name is 'name', e.g. {'name' : '*.txt'}.
    '''
    def __init__(self, key, value):
        self.re = re.compile(value.replace('.', '\\.')
                                  .replace('?', '.?')
                                  .replace('*', '.*') + '$')

    def match(self, dirname, filename, fstat):
        return self.re.match(filename)


class InameOption(Option):
    '''
    Match files with a case-insensitive glob filename pattern.
    Note: this is the 'basename' portion of a pathname.
    The option name is 'iname', e.g. {'iname' : '*.TXT'}.
    '''
    def __init__(self, key, value):
        self.re = re.compile(value.replace('.', '\\.')
                                  .replace('?', '.?')
                                  .replace('*', '.*') + '$',
                             re.IGNORECASE)

    def match(self, dirname, filename, fstat):
        return self.re.match(filename)


class RegexOption(Option):
    '''Match files with a case-sensitive regular expression.
    Note: this is the 'basename' portion of a pathname.
    The option name is 'regex', e.g. {'regex' : '.*\.txt'}.
    '''
    def __init__(self, key, value):
        try:
            self.re = re.compile(value)
        except re.error:
            raise ValueError('invalid regular expression: "{0}"'.format(value))

    def match(self, dirname, filename, fstat):
        return self.re.match(filename)


class IregexOption(Option):
    '''Match files with a case-insensitive regular expression.
    Note: this is the 'basename' portion of a pathname.
    The option name is 'iregex', e.g. {'iregex' : '.*\.txt'}.
    '''
    def __init__(self, key, value):
        try:
            self.re = re.compile(value, re.IGNORECASE)
        except re.error:
            raise ValueError('invalid regular expression: "{0}"'.format(value))

    def match(self, dirname, filename, fstat):
        return self.re.match(filename)


class TypeOption(Option):
    '''
    Match files by their file type(s).
    The file type(s) are specified as an optionally comma and/or space
    separated list of letters.
        b = block device
        c = character device
        d = directory
        f = regular (plain) file
        l = symbolic link
        p = FIFO (named pipe)
        s = socket
    The option name is 'type', e.g. {'type' : 'd'} or {'type' : 'bc'}.
    '''
    def __init__(self, key, value):
        # remove whitespace and commas
        value = "".join(value.strip().replace(',', '').split())
        self.ftypes = set()
        for ch in value:
            try:
                self.ftypes.add(_FILE_TYPES[ch])
            except KeyError:
                raise ValueError('invalid file type "{0}"'.format(ch))

    def requires(self):
        return _REQUIRES_STAT

    def match(self, dirname, filename, fstat):
        return stat.S_IFMT(fstat[stat.ST_MODE]) in self.ftypes


class OwnerOption(Option):
    '''
    Match files by their owner name(s) and/or uid(s), e.g. 'root'.
    The names are a space and/or comma separated list of names and/or integers.
    A match occurs when the file's uid matches any user specified.
    The option name is 'owner', e.g. {'owner' : 'root'}.
    '''
    def __init__(self, key, value):
        self.uids = set()
        for name in value.replace(',', ' ').split():
            if name.isdigit():
                self.uids.add(int(name))
            else:
                try:
                    self.uid = pwd.getpwnam(value).pw_uid
                except KeyError:
                    raise ValueError('no such user "{0}"'.format(name))

    def requires(self):
        return _REQUIRES_STAT

    def match(self, dirname, filename, fstat):
        return fstat[stat.ST_UID] in self.uids


class GroupOption(Option):
    '''
    Match files by their group name(s) and/or uid(s), e.g. 'admin'.
    The names are a space and/or comma separated list of names and/or integers.
    A match occurs when the file's gid matches any group specified.
    The option name is 'group', e.g. {'group' : 'admin'}.
    '''
    def __init__(self, key, value):
        self.gids = set()
        for name in value.replace(',', ' ').split():
            if name.isdigit():
                self.gids.add(int(name))
            else:
                try:
                    self.gids.add(grp.getgrnam(value).gr_gid)
                except KeyError:
                    raise ValueError('no such group "{0}"'.format(name))

    def requires(self):
        return _REQUIRES_STAT

    def match(self, dirname, filename, fstat):
        return fstat[stat.ST_GID] in self.gids


class SizeOption(Option):
    '''
    Match files by their size.
    Prefix the size with '-' to find files the specified size and smaller.
    Prefix the size with '+' to find files the specified size and larger.
    Without the +/- prefix, match the exact file size.
    The size can be suffixed with (case-insensitive) suffixes:
        b = bytes
        k = kilobytes
        m = megabytes
        g = gigabytes
        t = terabytes
    The option name is 'size', e.g. {'size' : '+1G'}.
    '''
    def __init__(self, key, value):
        self.min_size, self.max_size = _parse_size(value)

    def requires(self):
        return _REQUIRES_STAT

    def match(self, dirname, filename, fstat):
        return self.min_size <= fstat[stat.ST_SIZE] <= self.max_size


class MtimeOption(Option):
    '''
    Match files modified since the specified time.
    The option name is 'mtime', e.g. {'mtime' : '3d'}.
    The value format is [<num>w] [<num>[d]] [<num>h] [<num>m] [<num>s]
    where num is an integer or float and the case-insenstive suffixes are:
        w = week
        d = day
        h = hour
        m = minute
        s = second
    Whitespace is ignored in the value.
    '''
    def __init__(self, key, value):
        secs, resolution = _parse_interval(value)
        self.min_time = time.time() - int(secs / resolution) * resolution

    def requires(self):
        return _REQUIRES_STAT

    def match(self, dirname, filename, fstat):
        return fstat[stat.ST_MTIME] >= self.min_time


class GrepOption(Option):
    '''Match files when a pattern occurs within the file.
    The option name is 'grep', e.g. {'grep' : '(foo)|(bar}'}.
    '''
    def __init__(self, key, value):
        try:
            self.re = re.compile(value)
        except re.error:
            raise ValueError('invalid regular expression: "{0}"'.format(value))

    def requires(self):
        return _REQUIRES_CONTENTS | _REQUIRES_STAT

    def match(self, dirname, filename, fstat):
        if not stat.S_ISREG(fstat[stat.ST_MODE]):
            return None
        with open(os.path.join(dirname, filename), 'rb') as f:
            for line in f:
                if self.re.search(line):
                    return os.path.join(dirname, filename)
        return None


class PrintOption(Option):
    '''
    Return information about a matched file.
    Print options are specified as a comma and/or space separated list of
    one or more of the following:
        group  = group name
        md5    = MD5 digest of file contents
        mode   = file mode (as integer)
        mtime  = last modification time (as time_t)
        name   = file basename
        path   = file absolute path
        size   = file size in bytes
        type   = file type
        user   = user name
    '''
    def __init__(self, key, value):
        self.need_stat = False
        self.print_title = False
        self.fmt = []
        for arg in value.replace(',', ' ').split():
            self.fmt.append(arg)
            if arg not in ['name', 'path']:
                self.need_stat = True
        if len(self.fmt) == 0:
            self.fmt.append('path')

    def requires(self):
        return _REQUIRES_STAT if self.need_stat else _REQUIRES_PATH

    def execute(self, fullpath, fstat):
        result = []
        for arg in self.fmt:
            if arg == 'path':
                result.append(fullpath)
            elif arg == 'name':
                result.append(os.path.basename(fullpath))
            elif arg == 'size':
                result.append(fstat[stat.ST_SIZE])
            elif arg == 'type':
                result.append(_FILE_TYPES.get(stat.S_IFMT(fstat[stat.ST_MODE]), '?'))
            elif arg == 'mode':
                result.append(fstat[stat.ST_MODE])
            elif arg == 'mtime':
                result.append(fstat[stat.ST_MTIME])
            elif arg == 'user':
                uid = fstat[stat.ST_UID]
                try:
                    result.append(pwd.getpwuid(uid).pw_name)
                except KeyError:
                    result.append(uid)
            elif arg == 'group':
                gid = fstat[stat.ST_GID]
                try:
                    result.append(grp.getgrgid(gid).gr_name)
                except KeyError:
                    result.append(gid)
            elif arg == 'md5':
                if stat.S_ISREG(fstat[stat.ST_MODE]):
                    with open(fullpath, 'rb') as f:
                        buf = f.read(8192)
                        h = hashlib.md5()
                        while buf:
                            h.update(buf)
                            buf = f.read(8192)
                    result.append(h.hexdigest())
                else:
                    result.append('')

        if len(result) == 1:
            return result[0]
        else:
            return result


class Finder(object):
    def __init__(self, options):
        self.actions = []
        criteria = {_REQUIRES_PATH: list(),
                    _REQUIRES_STAT: list(),
                    _REQUIRES_CONTENTS: list()}
        for key, value in options.iteritems():
            if value is None or len(value) == 0:
                raise ValueError('missing value for "{0}" option'.format(key))
            try:
                obj = globals()[key.title() + "Option"](key, value)
            except KeyError:
                raise ValueError('invalid option "{0}"'.format(key))
            if hasattr(obj, 'match'):
                requires = obj.requires()
                if requires & _REQUIRES_CONTENTS:
                    criteria[_REQUIRES_CONTENTS].append(obj)
                elif requires & _REQUIRES_STAT:
                    criteria[_REQUIRES_STAT].append(obj)
                else:
                    criteria[_REQUIRES_PATH].append(obj)
            if hasattr(obj, 'execute'):
                self.actions.append(obj)
        if len(self.actions) == 0:
            self.actions.append(PrintOption('print', ''))
        # order criteria so that least expensive checks are done first
        self.criteria = criteria[_REQUIRES_PATH] + \
                        criteria[_REQUIRES_STAT] + \
                        criteria[_REQUIRES_CONTENTS]

    def find(self, path):
        '''
        Generate filenames in path that satisfy criteria specified in
        the constructor.
        This method is a generator and should be repeatedly called
        until there are no more results.
        '''
        for dirpath, dirs, files in os.walk(path):
            for name in dirs + files:
                fstat = None
                matches = True
                fullpath = None
                for criterion in self.criteria:
                    if fstat is None and criterion.requires() & _REQUIRES_STAT:
                        fullpath = os.path.join(dirpath, name)
                        fstat = os.stat(fullpath)
                    if not criterion.match(dirpath, name, fstat):
                        matches = False
                        break
                if matches:
                    if fullpath is None:
                        fullpath = os.path.join(dirpath, name)
                    for action in self.actions:
                        if (fstat is None and
                            action.requires() & _REQUIRES_STAT):
                            fstat = os.stat(fullpath)
                        result = action.execute(fullpath, fstat)
                        if result is not None:
                            yield result


def find(path, options):
    '''
    WRITEME
    '''
    f = Finder(options)
    for path in f.find(path):
        yield path

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print >> sys.stderr, "usage: {0} path [options]".format(sys.argv[0])
        sys.exit(1)

    path = sys.argv[1]
    criteria = {}

    for arg in sys.argv[2:]:
        key, value = arg.split('=')
        criteria[key] = value
    try:
        f = Finder(criteria)
    except ValueError, ex:
        print >> sys.stderr, 'error: {0}'.format(ex)
        sys.exit(1)

    for result in f.find(path):
        print result
