'''
File server pluggable modules and generic backend functions
'''

# Import python libs
import re
import fnmatch
import logging


log = logging.getLogger(__name__)


def is_file_ignored(opts, fn):
    '''
    If file_ignore_regex or file_ignore_glob were given in config,
    compare the given file path against all of them and return True
    on the first match.
    '''
    if opts['file_ignore_regex']:
        for r in opts['file_ignore_regex']:
            if re.search(r, fn):
                log.debug('File matching file_ignore_regex. Skipping: {0}'.format(fn))
                return True

    if opts['file_ignore_glob']:
        for g in opts['file_ignore_glob']:
            if fnmatch.fnmatch(fn, g):
                log.debug('File matching file_ignore_glob. Skipping: {0}'.format(fn))
                return True
    return False

