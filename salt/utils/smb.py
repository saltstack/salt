# -*- coding: utf-8 -*-
'''
Utility functions for SMB connections

:depends: impacket
'''

from __future__ import absolute_import

try:
    import impacket.smbconnection
    from impacket.smbconnection import SessionError
    HAS_IMPACKET = True
except ImportError:
    HAS_IMPACKET = False


def get_conn(host=None, username=None, password=None):
    '''
    Get an SMB connection
    '''
    conn = impacket.smbconnection.SMBConnection(
        remoteName='*SMBSERVER',
        remoteHost=host,
    )
    conn.login(user=username, password=password)
    return conn


def mkdirs_smb(path, share='C$', conn=None, host=None, username=None, password=None):
    '''
    Recursively create a directory structure on an SMB share

    Paths should be passed in with forward-slash delimiters, and should not
    start with a forward-slash.
    '''
    if conn is None:
        conn = get_conn(host, username, password)

    comps = path.split('/')
    pos = 1
    for comp in comps:
        cwd = '\\'.join(comps[0:pos])
        try:
            conn.listPath(share, cwd)
        except SessionError:
            conn.createDirectory(share, cwd)
        pos += 1
