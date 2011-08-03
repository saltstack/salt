#!/usr/bin/env python
'''
Simulate the Unix find(1) command and return a list of paths that
meet the specified critera.

Critera include:
    name  = filename-glob
    iname = case-insensitive-filename-glob
    type  = b|c|d|p|f|l|s
    user  = user-name
    group = group-name
    size  = number[b|c|w|k|m|g]
    mmin  = [+-]minutes
    mtime = [+-]days
'''

import grp
import logging
import os
import pwd
import re
import stat
import sys

# Set up logger
log = logging.getLogger(__name__)

class NameCriterion(object):
    '''
    Match files with a case-sensitive glob filename pattern.
    Note: this is the 'basename' portion of a pathname.
    The criterion name is 'name', e.g. {'name' : '*.txt'}.
    '''
    def __init__(self, key, value):
        self.re = re.compile(value.replace('.', '\\.')
                                  .replace('?', '.?')
                                  .replace('*', '.*') + '$')

    def name_satisfied(self, dirname, filename):
        return self.re.match(filename)

class InameCriterion(object):
    '''
    Match files with a case-insensitive glob filename pattern.
    Note: this is the 'basename' portion of a pathname.
    The criterion name is 'iname', e.g. {'iname' : '*.TXT'}.
    '''
    def __init__(self, key, value):
        self.re = re.compile(value.replace('.', '\\.')
                                  .replace('?', '.?')
                                  .replace('*', '.*') + '$',
                             re.IGNORECASE)

    def name_satisfied(self, dirname, filename):
        return self.re.match(filename)

class TypeCriterion(object):
    '''
    Match files by their file type.
    b = block device
    c = character device
    d = directory
    f = regular (plain) file
    l = symbolic link
    p = FIFO (named pipe)
    s = socket
    The criterion name is 'type', e.g. {'type' : 'd'}.
    '''
    def __init__(self, key, value):
        value = value.strip()
        try:
            self.ftype = {'b' : stat.S_IFBLK,
                          'c' : stat.S_IFCHR,
                          'd' : stat.S_IFDIR,
                          'f' : stat.S_IFREG,
                          'l' : stat.S_IFLNK,
                          'p' : stat.S_IFIFO,
                          's' : stat.S_IFSOCK}[value]
        except KeyError:
            raise ValueError('invalid file type "{}"'.format(value))

    def stat_satisfied(self, path, fstat):
        return self.ftype == stat.S_IFMT(fstat[stat.ST_MODE])

class OwnerCriterion(object):
    '''
    Match files by their owner name, e.g. 'root'.
    The criterion name is 'owner', e.g. {'owner' : 'root'}.
    '''
    def __init__(self, key, value):
        value = value.strip()
        try:
            self.uid = pwd.getpwnam(value).pw_uid
        except KeyError:
            raise ValueError('no such user "{}"'.format(value))

    def stat_satisfied(self, path, fstat):
        return self.uid == fstat[stat.ST_UID]

class GroupCriterion(object):
    '''
    Match files by their group name, e.g. 'admin'.
    The criterion name is 'group', e.g. {'group' : 'admin'}.
    '''
    def __init__(self, key, value):
        value = value.strip()
        try:
            self.gid = grp.getgrnam(value).gr_gid
        except KeyError:
            raise ValueError('no such group "{}"'.format(value))

    def stat_satisfied(self, path, fstat):
        return self.uid == fstat[stat.ST_GID]

class SizeCriterion(object):
    '''
    Match files by their size.
    Prefix the size with '-' to find files the specified size and smaller.
    Prefix the size with '+' to find files the specified size and larger.
    Without the +/- prefix, match the exact file size.
    The size can be suffixed with (case-insensitive):
        b = bytes
        c = characters
        w = 2-byte words
        k = kilobytes
        m = megabytes
        g = gigabytes
        t = terabytes
    The criterion name is 'size', e.g. {'size' : '+1G'}.
    '''
    def __init__(self, key, value):
        value = value.strip()
        self.size_min = None
        self.size_max = None
        multiplier = 1
        if value.startswith(('-','+')):
            if value.startswith('-'):
                self.size_min = -sys.maxint - 1
            else:
                self.size_max = sys.maxint
            value = value[1:]
        if value.endswith(('b','c','w','k','m','g','t')):
            if value.endswith('w'):
                multiplier = 2
            elif value.endswith('k'):
                multiplier = 2**10
            elif value.endswith('m'):
                multiplier = 2**20
            elif value.endswith('g'):
                multiplier = 2**30
            elif value.endswith('t'):
                multiplier = 2**40
            value = value[:-1]
        try:
            size = int(value) * multiplier
        except ValueError:
            return 'error: invalid size "{}"'.format(arg[5:])
        if self.size_min is None:
            self.size_min = size
        if self.size_max is None:
            self.size_max = size

    def stat_satisfied(self, path, fstat):
        return self.size_min <= fstat[stat.ST_SIZE] <= self.size_max

class Finder(object):
    def __init__(self, criteria):
        self.name_criteria = set()
        self.stat_criteria = set()
        for key, value in criteria.iteritems():
            if value is None or len(value) == 0:
                raise ValueError('missing value for "{}" criterion'.format(key))
            try:
                obj = globals()[key.title() + "Criterion"](key, value)
            except KeyError:
                raise ValueError('invalid criteria "{}"'.format(key))
            if hasattr(obj, 'name_satisfied'):
                self.name_criteria.add(obj)
            if hasattr(obj, 'stat_satisfied'):
                self.stat_criteria.add(obj)

    def find(self, path):
        '''
        Generate filenames in path that satisfy criteria specified in
        the constructor.
        This method is a generator and should be repeatedly called
        until there are no more results.
        '''
        for dirpath, dirs, files in os.walk(path):
            for name in dirs + files:
                if self._satisfies_name_criteria(dirpath, name):
                    target = os.path.join(dirpath, name)
                    if len(self.stat_criteria) == 0:
                        yield target
                    else:
                        fstat = os.stat(target)
                        if self._satisfies_stat_criteria(target, fstat):
                            yield target

    def find_stat(self, path):
        '''
        Generate (filename,stat) tuples in path that satisfy criteria
        specified in the constructor.
        This method is a generator and should be repeatedly called
        until there are no more results.
        '''
        for dirpath, dirs, files in os.walk(path):
            for name in dirs + files:
                if self._satisfies_name_criteria(dirpath, name):
                    target = os.path.join(dirpath, name)
                    fstat = os.stat(target)
                    if self._satisfies_stat_criteria(target, fstat):
                        yield target, fstat

    def _satisfies_name_criteria(self, dirpath, name):
        for criterion in self.name_criteria:
            if not criterion.name_satisfied(dirpath, name):
                return False
        return True

    def _satisfies_stat_criteria(self, path, fstat):
        for criterion in self.stat_criteria:
            if not criterion.stat_satisfied(path, fstat):
                return False
        return True

def find(path, criteria):
    '''
    '''
    f = Finder(criteria)
    for path in f.find(path):
        yield path

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print >> sys.stderr, "usage: {} path [options]".format(sys.argv[0])
        sys.exit(1)
    path = sys.argv[1]
    criteria = {}
    for arg in sys.argv[2:]:
        key, value = arg.split('=')
        criteria[key] = value
    try:
        f = Finder(criteria)
    except ValueError, ex:
        print >> sys.stderr, 'error: {}'.format(ex)
        sys.exit(1)

    for result in f.find(path):
        print result
