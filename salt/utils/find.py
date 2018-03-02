# -*- coding: utf-8 -*-
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
and/or depth criteria:
   maxdepth = maximum depth to transverse in path
   mindepth = minimum depth to transverse before checking files or directories

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

print-opts: a comma and/or space separated list of one or more of
the following:

    group: group name
    md5:   MD5 digest of file contents
    mode:  file permissions (as as integer)
    mtime: last modification time (as time_t)
    name:  file basename
    path:  file absolute path
    size:  file size in bytes
    type:  file type
    user:  user name
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import os
import re
import stat
import shutil
import sys
import time
from subprocess import Popen, PIPE
try:
    import grp
    import pwd
    # TODO: grp and pwd are both used in the code, we better make sure that
    # that code never gets run if importing them does not succeed
except ImportError:
    pass

# Import 3rd-party libs
from salt.ext import six

# Import salt libs
import salt.utils.args
import salt.utils.hashutils
import salt.utils.path
import salt.utils.stringutils
import salt.defaults.exitcodes
from salt.utils.filebuffer import BufferedReader

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
                             (?P<modifier>[+-]?)
                             (?: (?P<week>   \d+ (?:\.\d*)? ) \s* [wW]  )? \s*
                             (?: (?P<day>    \d+ (?:\.\d*)? ) \s* [dD]  )? \s*
                             (?: (?P<hour>   \d+ (?:\.\d*)? ) \s* [hH]  )? \s*
                             (?: (?P<minute> \d+ (?:\.\d*)? ) \s* [mM]  )? \s*
                             (?: (?P<second> \d+ (?:\.\d*)? ) \s* [sS]  )? \s*
                             $
                             ''',
                             flags=re.VERBOSE)

_PATH_DEPTH_IGNORED = (os.path.sep, os.path.curdir, os.path.pardir)


def _parse_interval(value):
    '''
    Convert an interval string like 1w3d6h into the number of seconds, time
    resolution (1 unit of the smallest specified time unit) and the modifier(
    '+', '-', or '').
        w = week
        d = day
        h = hour
        m = minute
        s = second
    '''
    match = _INTERVAL_REGEX.match(six.text_type(value))
    if match is None:
        raise ValueError('invalid time interval: \'{0}\''.format(value))

    result = 0
    resolution = None
    for name, multiplier in [('second', 1),
                             ('minute', 60),
                             ('hour', 60 * 60),
                             ('day', 60 * 60 * 24),
                             ('week', 60 * 60 * 24 * 7)]:
        if match.group(name) is not None:
            result += float(match.group(name)) * multiplier
            if resolution is None:
                resolution = multiplier

    return result, resolution, match.group('modifier')


def _parse_size(value):
    scalar = value.strip()

    if scalar.startswith(('-', '+')):
        style = scalar[0]
        scalar = scalar[1:]
    else:
        style = '='

    if len(scalar) > 0:
        multiplier = {'b': 2 ** 0,
                      'k': 2 ** 10,
                      'm': 2 ** 20,
                      'g': 2 ** 30,
                      't': 2 ** 40}.get(scalar[-1].lower())
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
        max_size = six.MAXSIZE
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
        self.regex = re.compile(value.replace('.', '\\.')
                                     .replace('?', '.?')
                                     .replace('*', '.*') + '$')

    def match(self, dirname, filename, fstat):
        return self.regex.match(filename)


class InameOption(Option):
    '''
    Match files with a case-insensitive glob filename pattern.
    Note: this is the 'basename' portion of a pathname.
    The option name is 'iname', e.g. {'iname' : '*.TXT'}.
    '''
    def __init__(self, key, value):
        self.regex = re.compile(value.replace('.', '\\.')
                                     .replace('?', '.?')
                                     .replace('*', '.*') + '$',
                                re.IGNORECASE)

    def match(self, dirname, filename, fstat):
        return self.regex.match(filename)


class RegexOption(Option):
    '''
    Match files with a case-sensitive regular expression.
    Note: this is the 'basename' portion of a pathname.
    The option name is 'regex', e.g. {'regex' : '.*\\.txt'}.
    '''
    def __init__(self, key, value):
        try:
            self.regex = re.compile(value)
        except re.error:
            raise ValueError('invalid regular expression: "{0}"'.format(value))

    def match(self, dirname, filename, fstat):
        return self.regex.match(filename)


class IregexOption(Option):
    '''
    Match files with a case-insensitive regular expression.
    Note: this is the 'basename' portion of a pathname.
    The option name is 'iregex', e.g. {'iregex' : '.*\\.txt'}.
    '''
    def __init__(self, key, value):
        try:
            self.regex = re.compile(value, re.IGNORECASE)
        except re.error:
            raise ValueError('invalid regular expression: "{0}"'.format(value))

    def match(self, dirname, filename, fstat):
        return self.regex.match(filename)


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
        for ftype in value:
            try:
                self.ftypes.add(_FILE_TYPES[ftype])
            except KeyError:
                raise ValueError('invalid file type "{0}"'.format(ftype))

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
                    self.uids.add(pwd.getpwnam(value).pw_uid)
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
                    self.gids.add(grp.getgrnam(name).gr_gid)
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
    where num is an integer or float and the case-insensitive suffixes are:
        w = week
        d = day
        h = hour
        m = minute
        s = second
    Whitespace is ignored in the value.
    '''
    def __init__(self, key, value):
        secs, resolution, modifier = _parse_interval(value)
        self.mtime = time.time() - int(secs / resolution) * resolution
        self.modifier = modifier

    def requires(self):
        return _REQUIRES_STAT

    def match(self, dirname, filename, fstat):
        if self.modifier == '-':
            return fstat[stat.ST_MTIME] >= self.mtime
        else:
            return fstat[stat.ST_MTIME] <= self.mtime


class GrepOption(Option):
    '''Match files when a pattern occurs within the file.
    The option name is 'grep', e.g. {'grep' : '(foo)|(bar}'}.
    '''
    def __init__(self, key, value):
        try:
            self.regex = re.compile(value)
        except re.error:
            raise ValueError('invalid regular expression: "{0}"'.format(value))

    def requires(self):
        return _REQUIRES_CONTENTS | _REQUIRES_STAT

    def match(self, dirname, filename, fstat):
        if not stat.S_ISREG(fstat[stat.ST_MODE]):
            return None
        dfilename = os.path.join(dirname, filename)
        with BufferedReader(dfilename, mode='rb') as bread:
            for chunk in bread:
                if self.regex.search(chunk):
                    return dfilename
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

    def execute(self, fullpath, fstat, test=False):
        result = []
        for arg in self.fmt:
            if arg == 'path':
                result.append(fullpath)
            elif arg == 'name':
                result.append(os.path.basename(fullpath))
            elif arg == 'size':
                result.append(fstat[stat.ST_SIZE])
            elif arg == 'type':
                result.append(
                    _FILE_TYPES.get(stat.S_IFMT(fstat[stat.ST_MODE]), '?')
                )
            elif arg == 'mode':
                # PY3 compatibility: Use radix value 8 on int type-cast explicitly
                result.append(int(oct(fstat[stat.ST_MODE])[-3:], 8))
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
                    md5digest = salt.utils.hashutils.get_hash(fullpath, 'md5')
                    result.append(md5digest)
                else:
                    result.append('')

        if len(result) == 1:
            return result[0]
        else:
            return result


class DeleteOption(TypeOption):
    '''
    Deletes matched file.
    Delete options are one or more of the following:
        a: all file types
        b: block device
        c: character device
        d: directory
        p: FIFO (named pipe)
        f: plain file
        l: symlink
        s: socket
    '''
    def __init__(self, key, value):
        if 'a' in value:
            value = 'bcdpfls'
        super(self.__class__, self).__init__(key, value)

    def execute(self, fullpath, fstat, test=False):
        if test:
            return fullpath
        try:
            if os.path.isfile(fullpath) or os.path.islink(fullpath):
                os.remove(fullpath)
            elif os.path.isdir(fullpath):
                shutil.rmtree(fullpath)
        except (OSError, IOError) as exc:
            return None
        return fullpath


class ExecOption(Option):
    '''
    Execute the given command, {} replaced by filename.
    Quote the {} if commands might include whitespace.
    '''
    def __init__(self, key, value):
        self.command = value

    def execute(self, fullpath, fstat, test=False):
        try:
            command = self.command.replace('{}', fullpath)
            print(salt.utils.args.shlex_split(command))
            p = Popen(salt.utils.args.shlex_split(command),
                      stdout=PIPE,
                      stderr=PIPE)
            (out, err) = p.communicate()
            if err:
                log.error(
                    'Error running command: %s\n\n%s',
                    command,
                    salt.utils.stringutils.to_str(err))
            return "{0}:\n{1}\n".format(command, salt.utils.stringutils.to_str(out))

        except Exception as e:
            log.error(
                'Exception while executing command "%s":\n\n%s',
                command,
                e)
            return '{0}: Failed'.format(fullpath)


class Finder(object):
    def __init__(self, options):
        self.actions = []
        self.maxdepth = None
        self.mindepth = 0
        self.test = False
        criteria = {_REQUIRES_PATH: list(),
                    _REQUIRES_STAT: list(),
                    _REQUIRES_CONTENTS: list()}
        if 'mindepth' in options:
            self.mindepth = options['mindepth']
            del options['mindepth']
        if 'maxdepth' in options:
            self.maxdepth = options['maxdepth']
            del options['maxdepth']
        if 'test' in options:
            self.test = options['test']
            del options['test']
        for key, value in six.iteritems(options):
            if key.startswith('_'):
                # this is a passthrough object, continue
                continue
            if value is None or len(str(value)) == 0:
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
        if self.mindepth < 1:
            dirpath, name = os.path.split(path)
            match, fstat = self._check_criteria(dirpath, name, path)
            if match:
                for result in self._perform_actions(path, fstat=fstat):
                    yield result

        for dirpath, dirs, files in salt.utils.path.os_walk(path):
            relpath = os.path.relpath(dirpath, path)
            depth = path_depth(relpath) + 1
            if depth >= self.mindepth and (self.maxdepth is None or self.maxdepth >= depth):
                for name in dirs + files:
                    fullpath = os.path.join(dirpath, name)
                    match, fstat = self._check_criteria(dirpath, name, fullpath)
                    if match:
                        for result in self._perform_actions(fullpath, fstat=fstat):
                            yield result

            if self.maxdepth is not None and depth > self.maxdepth:
                dirs[:] = []

    def _check_criteria(self, dirpath, name, fullpath, fstat=None):
        match = True
        for criterion in self.criteria:
            if fstat is None and criterion.requires() & _REQUIRES_STAT:
                try:
                    fstat = os.stat(fullpath)
                except OSError:
                    fstat = os.lstat(fullpath)
            if not criterion.match(dirpath, name, fstat):
                match = False
                break
        return match, fstat

    def _perform_actions(self, fullpath, fstat=None):
        for action in self.actions:
            if fstat is None and action.requires() & _REQUIRES_STAT:
                try:
                    fstat = os.stat(fullpath)
                except OSError:
                    fstat = os.lstat(fullpath)
            result = action.execute(fullpath, fstat, test=self.test)
            if result is not None:
                yield result


def path_depth(path):
    depth = 0
    head = path
    while True:
        head, tail = os.path.split(head)
        if not tail and (not head or head in _PATH_DEPTH_IGNORED):
            break
        if tail and tail not in _PATH_DEPTH_IGNORED:
            depth += 1
    return depth


def find(path, options):
    '''
    WRITEME
    '''
    finder = Finder(options)
    for path in finder.find(path):
        yield path


def _main():
    if len(sys.argv) < 2:
        sys.stderr.write('usage: {0} path [options]\n'.format(sys.argv[0]))
        sys.exit(salt.defaults.exitcodes.EX_USAGE)

    path = sys.argv[1]
    criteria = {}

    for arg in sys.argv[2:]:
        key, value = arg.split('=')
        criteria[key] = value
    try:
        finder = Finder(criteria)
    except ValueError as ex:
        sys.stderr.write('error: {0}\n'.format(ex))
        sys.exit(salt.defaults.exitcodes.EX_GENERIC)

    for result in finder.find(path):
        print(result)

if __name__ == '__main__':
    _main()
