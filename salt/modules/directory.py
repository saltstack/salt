# -*- coding: utf-8 -*-
'''
Manage information about directories, set/read user,
group, mode, and data.
'''

from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import datetime
import errno
import fnmatch
import io
import itertools
import logging
import operator
import os
import re
import shutil
import stat
import string
import sys
import tempfile
import time
import glob
import hashlib
import mmap
from collections import Iterable, Mapping, namedtuple
from functools import reduce  # pylint: disable=redefined-builtin

# pylint: disable=import-error,no-name-in-module,redefined-builtin
from salt.ext import six
from salt.ext.six.moves import range, zip
from salt.ext.six.moves.urllib.parse import urlparse as _urlparse
# pylint: enable=import-error,no-name-in-module,redefined-builtin

# Import salt libs
import salt.utils.args
import salt.utils.atomicfile
import salt.utils.data
import salt.utils.filebuffer
import salt.utils.files
import salt.utils.find
import salt.utils.functools
import salt.utils.hashutils
import salt.utils.itertools
import salt.utils.path
import salt.utils.platform
import salt.utils.stringutils
import salt.utils.templates
import salt.utils.url
import salt.utils.user
import salt.utils.data
import salt.utils.versions
from salt.exceptions import CommandExecutionError, MinionError, SaltInvocationError, get_error_message as _get_error_message
from salt.utils.files import HASHES, HASHES_REVMAP

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only work on POSIX-like systems
    '''
    # win_file takes care of windows
    if salt.utils.platform.is_windows():
        return (
            False,
            'The file execution module cannot be loaded: only available on '
            'non-Windows systems - use win_file instead.'
        )
    return True


def mode_normalized(mode):
    return salt.utils.path.mode_normalized(mode)


def get_mode(path):
    return salt.utils.path.get_mode(path)


def set_mode(path, mode):
    return salt.utils.path.set_mode(path, str(mode))


def remove(path, recursive=False, follow_symlinks=False):
    return salt.utils.path.remove(path, recursive, follow_symlinks)


def copy(src, path, recursive=False, remove_existing=False):
    return salt.utils.path.copy(src, path, recursive, remove_existing)


def move(src, path, remove_existing=False):
    return salt.utils.path.move(src, path, remove_existing)
