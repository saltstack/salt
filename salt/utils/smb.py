# -*- coding: utf-8 -*-
'''
Utility functions for SMB connections

:depends: impacket
'''

from __future__ import absolute_import, print_function, unicode_literals
import socket
import io

# Import python libs
import salt.utils.files
import logging

log = logging.getLogger(__name__)

from salt.exceptions import SaltException
try:
    import impacket.smbconnection
    from impacket.smbconnection import SessionError as smbSessionError
    from impacket.smb3 import SessionError as smb3SessionError
    HAS_IMPACKET = True
except ImportError:
    HAS_IMPACKET = False
try:
    import smb.SMBConnection
    HAS_PYSMB = True
except ImportError:
    HAS_PYSMB = False


class MissingSmb(SaltException):
    '''
    Raised when no smb library is found.
    '''


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


def _get_conn_impacket(host=None, username=None, password=None, client_name=None, port=445):
    conn = impacket.smbconnection.SMBConnection(
        remoteName=host,
        remoteHost=host,
        myName=client_name,
    )
    conn.login(user=username, password=password)
    return conn

def _get_conn_pysmb(host='', username='', password='', client_name='', port=445, is_direct_tcp=True):
    addr = socket.gethostbyname(host)
    conn = smb.SMBConnection.SMBConnection(username, password, client_name, host, is_direct_tcp=is_direct_tcp)
    conn.connect(addr, port)
    return conn


def get_conn(host='', username=None, password=None, port=445):
    '''
    Get an SMB connection
    '''
    if HAS_PYSMB:
        log.warn("Get connection pysmb")
        return _get_conn_pysmb(host, username, password, port=port)
    elif HAS_IMPACKET:
        log.warn("Get connection impacket")
        return _get_conn_impacket(host, username, password, port=port)
    return False


def _mkdirs_impacket(path, share='C$', conn=None, host=None, username=None, password=None):
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
        except (smbSessionError, smb3SessionError):
            log.exception('Encountered error running conn.listPath')
            conn.createDirectory(share, cwd)
        pos += 1


def _mkdirs_pysmb(path, share='C$', conn=None, host=None, username=None, password=None):
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
        except Exception:  # TODO
            log.debug("Unable to list path, create it: %s %s", share, path)
            #log.exception('Encountered error running conn.listPath')
            conn.createDirectory(share, cwd)
        pos += 1


def mkdirs(path, share='C$', conn=None, host=None, username=None, password=None):
    if HAS_PYSMB:
        return _mkdirs_pysmb(path, share, conn=conn, host=host, username=username, password=password)
    elif HAS_IMPACKET:
        return _mkdirs_impacket(path, share, conn=conn, host=host, username=username, password=password)
    raise MissingException("SMB library required (impacket or pysmb)")


def _put_str_impacket(content, path, share='C$', conn=None, host=None, username=None, password=None):
    if conn is None:
        conn = get_conn(host, username, password)

    if conn is False:
        return False

    fh_ = StrHandle(content)
    conn.putFile(share, path, fh_.string)


def _put_str_pysmb(content, path, share='C$', conn=None, host=None, username=None, password=None):
    if conn is None:
        conn = get_conn(host, username, password)
    conn.storeFile(share, path, io.BytesIO(content))


def put_str(content, path, share='C$', conn=None, host=None, username=None, password=None):
    '''
    Wrapper around impacket.smbconnection.putFile() that allows a string to be
    uploaded, without first writing it as a local file
    '''
    if HAS_PYSMB:
        return _put_str_pysmb(content, path, share, conn=conn, host=host, username=username, password=password)
    elif HAS_IMPACKET:
        return _put_str_impacket(content, path, share, conn=conn, host=host, username=username, password=password)
    raise MissingException("SMB library required (impacket or pysmb)")


def _put_file_impacket(local_path, path, share='C$', conn=None, host=None, username=None, password=None):
    '''
    Wrapper around impacket.smbconnection.putFile() that allows a file to be
    uploaded

    Example usage:

        import salt.utils.smb
        smb_conn = salt.utils.smb.get_conn('10.0.0.45', 'vagrant', 'vagrant')
        salt.utils.smb.put_file('/root/test.pdf', 'temp\\myfiles\\test1.pdf', conn=smb_conn)
    '''
    if conn is None:
        conn = get_conn(host, username, password)

    if conn is False:
        return False

    if hasattr(local_path, 'read'):
        conn.putFile(share, path, local_path)
        return
    with salt.utils.fopen(local_path, 'rb') as fh_:
        conn.putFile(share, path, fh_.read)


def _put_file_pysmb(local_path, path, share='C$', conn=None, host=None, username=None, password=None):
    if conn is None:
        conn = get_conn(host, username, password)

    if conn is False:
        return False

    if hasattr(local_path, 'read'):
        conn.putFile(share, path, local_path)
        return
    with salt.utils.fopen(local_path, 'rb') as fh_:
        conn.storeFile(share, path, fh_)


def put_file(local_path, path, share='C$', conn=None, host=None, username=None, password=None):
    '''
    Wrapper around impacket.smbconnection.putFile() that allows a file to be
    uploaded

    Example usage:

        import salt.utils.smb
        smb_conn = salt.utils.smb.get_conn('10.0.0.45', 'vagrant', 'vagrant')
        salt.utils.smb.put_file('/root/test.pdf', 'temp\\myfiles\\test1.pdf', conn=smb_conn)
    '''
    if HAS_PYSMB:
        return _put_file_pysmb(local_path, path, share, conn=conn, host=host, username=username, password=password)
    elif HAS_IMPACKET:
        return _put_file_impacket(local_path, path, share, conn=conn, host=host, username=username, password=password)
    raise MissingException("SMB library required (impacket or pysmb)")


def _delete_file_impacket(path, share='C$', conn=None, host=None, username=None, password=None):
    if conn is None:
        conn = get_conn(host, username, password)
    if conn is False:
        return False
    conn.deleteFile(share, path)


def _delete_file_pysmb(path, share='C$', conn=None, host=None, username=None, password=None):
    if conn is None:
        conn = get_conn(host, username, password)
    if conn is False:
        return False
    # deleteFiles accepts a glob, we are passing the full file path
    conn.deleteFiles(share, path)


def delete_file(path, share='C$', conn=None, host=None, username=None, password=None):
    if HAS_PYSMB:
        return _delete_file_pysmb(path, share, conn=conn, host=host, username=username, password=password)
    elif HAS_IMPACKET:
        return _delete_file_impacket(path, share, conn=conn, host=host, username=username, password=password)
    raise MissingException("SMB library required (impacket or pysmb)")


def _delete_directory_impacket(path, share='C$', conn=None, host=None, username=None, password=None):
    if conn is None:
        conn = get_conn(host, username, password)
    if conn is False:
        return False
    conn.deleteDirectory(share, path)


def _delete_directory_pysmb(path, share='C$', conn=None, host=None, username=None, password=None):
    if conn is None:
        conn = get_conn(host, username, password)
    if conn is False:
        return False
    conn.deleteDirectory(share, path)

def delete_directory(path, share='C$', conn=None, host=None, username=None, password=None):
    if HAS_PYSMB:
        return _delete_directory_pysmb(path, share, conn=conn, host=host, username=username, password=password)
    elif HAS_IMPACKET:
        return _delete_directory_impacket(path, share, conn=conn, host=host, username=username, password=password)
    raise MissingException("SMB library required (impacket or pysmb)")
