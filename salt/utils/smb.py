# -*- coding: utf-8 -*-
'''
Utility functions for SMB connections

:depends: impacket
'''

from __future__ import absolute_import

# Import python libs
import logging

log = logging.getLogger(__name__)

try:
    import impacket.smbconnection
    from impacket.smbconnection import SessionError as smbSessionError
    from impacket.smb3 import SessionError as smb3SessionError
    HAS_IMPACKET = True
except ImportError:
    HAS_IMPACKET = False


class StrHandle(object):
    '''
    Fakes a file handle, so that raw strings may be uploaded instead of having
    to write files first. Used by put_str()
    '''
    def __init__(self, content):
        '''
        Init
        '''
        self.content = content
        self.finished = False

    def string(self, writesize=None):
        '''
        Looks like a file handle
        '''
        if not self.finished:
            self.finished = True
            return self.content
        return ''


def get_conn(host=None, username=None, password=None):
    '''
    Get an SMB connection
    '''
    if not HAS_IMPACKET:
        return False

    conn = impacket.smbconnection.SMBConnection(
        remoteName='*SMBSERVER',
        remoteHost=host,
    )
    conn.login(user=username, password=password)
    return conn


def mkdirs(path, share='C$', conn=None, host=None, username=None, password=None):
    '''
    Recursively create a directory structure on an SMB share

    Paths should be passed in with forward-slash delimiters, and should not
    start with a forward-slash.
    '''
    if conn is None:
        conn = get_conn(host, username, password)

    if conn is False:
        return False

    comps = path.split('/')
    pos = 1
    for comp in comps:
        cwd = '\\'.join(comps[0:pos])
        try:
            conn.listPath(share, cwd)
        except (smbSessionError, smb3SessionError) as exc:
            log.debug('Exception: {0}'.format(exc))
            conn.createDirectory(share, cwd)
        pos += 1


def put_str(content, path, share='C$', conn=None, host=None, username=None, password=None):
    '''
    Wrapper around impacket.smbconnection.putFile() that allows a string to be
    uploaded, without first writing it as a local file
    '''
    if conn is None:
        conn = get_conn(host, username, password)

    if conn is False:
        return False

    fh_ = StrHandle(content)
    conn.putFile(share, path, fh_.string)
