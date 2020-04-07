# -*- coding: utf-8 -*-
"""
Utility functions for SMB connections

:depends: impacket
"""

from __future__ import absolute_import, print_function, unicode_literals

import logging
import socket
import uuid

# Import python libs
import salt.utils.files
import salt.utils.stringutils
import salt.utils.versions
from salt.exceptions import MissingSmb

log = logging.getLogger(__name__)


try:
    import impacket.smbconnection
    from impacket.smbconnection import SessionError as smbSessionError
    from impacket.smb3 import SessionError as smb3SessionError

    HAS_IMPACKET = True
except ImportError:
    HAS_IMPACKET = False

try:
    from smbprotocol.connection import Connection
    from smbprotocol.session import Session
    from smbprotocol.tree import TreeConnect
    from smbprotocol.open import (
        Open,
        ImpersonationLevel,
        FilePipePrinterAccessMask,
        FileAttributes,
        CreateDisposition,
        CreateOptions,
        ShareAccess,
        DirectoryAccessMask,
        FileInformationClass,
    )
    from smbprotocol.create_contexts import (
        CreateContextName,
        SMB2CreateContextRequest,
        SMB2CreateQueryMaximalAccessRequest,
    )
    from smbprotocol.security_descriptor import (
        AccessAllowedAce,
        AccessMask,
        AclPacket,
        SDControl,
        SIDPacket,
        SMB2CreateSDBuffer,
    )

    logging.getLogger("smbprotocol").setLevel(logging.WARNING)
    HAS_SMBPROTOCOL = True
except ImportError:
    HAS_SMBPROTOCOL = False


class SMBProto(object):
    def __init__(self, server, username, password, port=445):
        connection_id = uuid.uuid4()
        addr = socket.gethostbyname(server)
        self.server = server
        connection = Connection(connection_id, addr, port, require_signing=True)
        self.session = Session(connection, username, password, require_encryption=False)

    def connect(self):
        self.connection.connect()
        self.session.connect()

    def close(self):
        self.session.connection.disconnect(True)

    @property
    def connection(self):
        return self.session.connection

    def tree_connect(self, share):
        if share.endswith("$"):
            share = r"\\{}\{}".format(self.server, share)
        tree = TreeConnect(self.session, share)
        tree.connect()
        return tree

    @staticmethod
    def normalize_filename(file):
        return file.lstrip("\\")

    @classmethod
    def open_file(cls, tree, file):
        file = cls.normalize_filename(file)
        # ensure file is created, get maximal access, and set everybody read access
        max_req = SMB2CreateContextRequest()
        max_req[
            "buffer_name"
        ] = CreateContextName.SMB2_CREATE_QUERY_MAXIMAL_ACCESS_REQUEST
        max_req["buffer_data"] = SMB2CreateQueryMaximalAccessRequest()

        # create security buffer that sets the ACL for everyone to have read access
        everyone_sid = SIDPacket()
        everyone_sid.from_string("S-1-1-0")
        ace = AccessAllowedAce()
        ace["mask"] = AccessMask.GENERIC_ALL
        ace["sid"] = everyone_sid
        acl = AclPacket()
        acl["aces"] = [ace]
        sec_desc = SMB2CreateSDBuffer()
        sec_desc["control"].set_flag(SDControl.SELF_RELATIVE)
        sec_desc.set_dacl(acl)
        sd_buffer = SMB2CreateContextRequest()
        sd_buffer["buffer_name"] = CreateContextName.SMB2_CREATE_SD_BUFFER
        sd_buffer["buffer_data"] = sec_desc

        create_contexts = [max_req, sd_buffer]
        file_open = Open(tree, file)
        open_info = file_open.create(
            ImpersonationLevel.Impersonation,
            FilePipePrinterAccessMask.GENERIC_READ
            | FilePipePrinterAccessMask.GENERIC_WRITE,
            FileAttributes.FILE_ATTRIBUTE_NORMAL,
            ShareAccess.FILE_SHARE_READ | ShareAccess.FILE_SHARE_WRITE,
            CreateDisposition.FILE_OVERWRITE_IF,
            CreateOptions.FILE_NON_DIRECTORY_FILE,
        )
        return file_open

    @staticmethod
    def open_directory(tree, name, create=False):
        # ensure directory is created
        dir_open = Open(tree, name)
        if create:
            dir_open.create(
                ImpersonationLevel.Impersonation,
                DirectoryAccessMask.GENERIC_READ | DirectoryAccessMask.GENERIC_WRITE,
                FileAttributes.FILE_ATTRIBUTE_DIRECTORY,
                ShareAccess.FILE_SHARE_READ | ShareAccess.FILE_SHARE_WRITE,
                CreateDisposition.FILE_OPEN_IF,
                CreateOptions.FILE_DIRECTORY_FILE,
            )
        return dir_open


class StrHandle(object):
    """
    Fakes a file handle, so that raw strings may be uploaded instead of having
    to write files first. Used by put_str()
    """

    def __init__(self, content):
        """
        Init
        """
        self.content = content
        self.finished = False

    def string(self, writesize=None):
        """
        Looks like a file handle
        """
        if not self.finished:
            self.finished = True
            return self.content
        return ""


def _get_conn_impacket(
    host=None, username=None, password=None, client_name=None, port=445
):
    conn = impacket.smbconnection.SMBConnection(
        remoteName=host, remoteHost=host, myName=client_name,
    )
    conn.login(user=username, password=password)
    return conn


def _get_conn_smbprotocol(host="", username="", password="", client_name="", port=445):
    conn = SMBProto(host, username, password, port)
    conn.connect()
    return conn


def get_conn(host="", username=None, password=None, port=445):
    """
    Get an SMB connection
    """
    if HAS_IMPACKET and not HAS_SMBPROTOCOL:
        salt.utils.versions.warn_until(
            "Sodium",
            "Support of impacket has been depricated and will be "
            "removed in Sodium. Please install smbprotocol instead.",
        )
    if HAS_SMBPROTOCOL:
        log.info("Get connection smbprotocol")
        return _get_conn_smbprotocol(host, username, password, port=port)
    elif HAS_IMPACKET:
        log.info("Get connection impacket")
        return _get_conn_impacket(host, username, password, port=port)
    return False


def _mkdirs_impacket(
    path, share="C$", conn=None, host=None, username=None, password=None
):
    """
    Recursively create a directory structure on an SMB share

    Paths should be passed in with forward-slash delimiters, and should not
    start with a forward-slash.
    """
    if conn is None:
        conn = get_conn(host, username, password)

    if conn is False:
        return False

    comps = path.split("/")
    pos = 1
    for comp in comps:
        cwd = "\\".join(comps[0:pos])
        try:
            conn.listPath(share, cwd)
        except (smbSessionError, smb3SessionError):
            log.exception("Encountered error running conn.listPath")
            conn.createDirectory(share, cwd)
        pos += 1


def _mkdirs_smbprotocol(
    path, share="C$", conn=None, host=None, username=None, password=None
):
    if conn is None:
        conn = get_conn(host, username, password)

    if conn is False:
        return False

    tree = conn.tree_connect(share)
    comps = path.split("/")
    pos = 1
    for comp in comps:
        cwd = "\\".join(comps[0:pos])
        dir_open = conn.open_directory(tree, cwd, create=True)
        compound_messages = [
            dir_open.query_directory(
                "*", FileInformationClass.FILE_NAMES_INFORMATION, send=False
            ),
            dir_open.close(False, send=False),
        ]
        requests = conn.session.connection.send_compound(
            [x[0] for x in compound_messages],
            conn.session.session_id,
            tree.tree_connect_id,
        )
        for i, request in enumerate(requests):
            response = compound_messages[i][1](request)
        pos += 1


def mkdirs(path, share="C$", conn=None, host=None, username=None, password=None):
    if HAS_SMBPROTOCOL:
        return _mkdirs_smbprotocol(
            path, share, conn=conn, host=host, username=username, password=password
        )
    elif HAS_IMPACKET:
        return _mkdirs_impacket(
            path, share, conn=conn, host=host, username=username, password=password
        )
    raise MissingSmb("SMB library required (impacket or smbprotocol)")


def _put_str_impacket(
    content, path, share="C$", conn=None, host=None, username=None, password=None
):
    if conn is None:
        conn = get_conn(host, username, password)

    if conn is False:
        return False

    fh_ = StrHandle(content)
    conn.putFile(share, path, fh_.string)


def _put_str_smbprotocol(
    content, path, share="C$", conn=None, host=None, username=None, password=None
):
    if conn is None:
        conn = get_conn(host, username, password)
    if conn is False:
        return False
    tree = conn.tree_connect(share)
    try:
        file_open = conn.open_file(tree, path)
        file_open.write(salt.utils.stringutils.to_bytes(content), 0)
    finally:
        file_open.close()


def put_str(
    content, path, share="C$", conn=None, host=None, username=None, password=None
):
    """
    Wrapper around impacket.smbconnection.putFile() that allows a string to be
    uploaded, without first writing it as a local file
    """
    if HAS_SMBPROTOCOL:
        return _put_str_smbprotocol(
            content,
            path,
            share,
            conn=conn,
            host=host,
            username=username,
            password=password,
        )
    elif HAS_IMPACKET:
        return _put_str_impacket(
            content,
            path,
            share,
            conn=conn,
            host=host,
            username=username,
            password=password,
        )
    raise MissingSmb("SMB library required (impacket or smbprotocol)")


def _put_file_impacket(
    local_path, path, share="C$", conn=None, host=None, username=None, password=None
):
    """
    Wrapper around impacket.smbconnection.putFile() that allows a file to be
    uploaded

    Example usage:

        import salt.utils.smb
        smb_conn = salt.utils.smb.get_conn('10.0.0.45', 'vagrant', 'vagrant')
        salt.utils.smb.put_file('/root/test.pdf', 'temp\\myfiles\\test1.pdf', conn=smb_conn)
    """
    if conn is None:
        conn = get_conn(host, username, password)

    if conn is False:
        return False

    if hasattr(local_path, "read"):
        conn.putFile(share, path, local_path)
        return
    with salt.utils.files.fopen(local_path, "rb") as fh_:
        conn.putFile(share, path, fh_.read)


def _put_file_smbprotocol(
    local_path,
    path,
    share="C$",
    conn=None,
    host=None,
    username=None,
    password=None,
    chunk_size=1024 * 1024,
):
    if conn is None:
        conn = get_conn(host, username, password)
    if conn is False:
        return False

    tree = conn.tree_connect(share)
    file_open = conn.open_file(tree, path)
    with salt.utils.files.fopen(local_path, "rb") as fh_:
        try:
            position = 0
            while True:
                chunk = fh_.read(chunk_size)
                if not chunk:
                    break
                file_open.write(chunk, position)
                position += len(chunk)
        finally:
            file_open.close(False)


def put_file(
    local_path, path, share="C$", conn=None, host=None, username=None, password=None
):
    """
    Wrapper around impacket.smbconnection.putFile() that allows a file to be
    uploaded

    Example usage:

        import salt.utils.smb
        smb_conn = salt.utils.smb.get_conn('10.0.0.45', 'vagrant', 'vagrant')
        salt.utils.smb.put_file('/root/test.pdf', 'temp\\myfiles\\test1.pdf', conn=smb_conn)
    """
    if HAS_SMBPROTOCOL:
        return _put_file_smbprotocol(
            local_path,
            path,
            share,
            conn=conn,
            host=host,
            username=username,
            password=password,
        )
    elif HAS_IMPACKET:
        return _put_file_impacket(
            local_path,
            path,
            share,
            conn=conn,
            host=host,
            username=username,
            password=password,
        )
    raise MissingSmb("SMB library required (impacket or smbprotocol)")


def _delete_file_impacket(
    path, share="C$", conn=None, host=None, username=None, password=None
):
    if conn is None:
        conn = get_conn(host, username, password)
    if conn is False:
        return False
    conn.deleteFile(share, path)


def _delete_file_smbprotocol(
    path, share="C$", conn=None, host=None, username=None, password=None
):
    if conn is None:
        conn = get_conn(host, username, password)
    if conn is False:
        return False
    tree = conn.tree_connect(share)
    file_open = Open(tree, path)
    delete_msgs = [
        file_open.create(
            ImpersonationLevel.Impersonation,
            FilePipePrinterAccessMask.GENERIC_READ | FilePipePrinterAccessMask.DELETE,
            FileAttributes.FILE_ATTRIBUTE_NORMAL,
            ShareAccess.FILE_SHARE_READ | ShareAccess.FILE_SHARE_WRITE,
            CreateDisposition.FILE_OPEN,
            CreateOptions.FILE_NON_DIRECTORY_FILE | CreateOptions.FILE_DELETE_ON_CLOSE,
            send=False,
        ),
        file_open.close(False, send=False),
    ]
    requests = conn.connection.send_compound(
        [x[0] for x in delete_msgs],
        conn.session.session_id,
        tree.tree_connect_id,
        related=True,
    )
    responses = []
    for i, request in enumerate(requests):
        # A SMBResponseException will be raised if something went wrong
        response = delete_msgs[i][1](request)
        responses.append(response)


def delete_file(path, share="C$", conn=None, host=None, username=None, password=None):
    if HAS_SMBPROTOCOL:
        return _delete_file_smbprotocol(
            path, share, conn=conn, host=host, username=username, password=password
        )
    elif HAS_IMPACKET:
        return _delete_file_impacket(
            path, share, conn=conn, host=host, username=username, password=password
        )
    raise MissingSmb("SMB library required (impacket or smbprotocol)")


def _delete_directory_impacket(
    path, share="C$", conn=None, host=None, username=None, password=None
):
    if conn is None:
        conn = get_conn(host, username, password)
    if conn is False:
        return False
    conn.deleteDirectory(share, path)


def _delete_directory_smbprotocol(
    path, share="C$", conn=None, host=None, username=None, password=None
):
    if conn is None:
        conn = get_conn(host, username, password)
    if conn is False:
        return False
    log.debug("_delete_directory_smbprotocol - share: %s, path: %s", share, path)
    tree = conn.tree_connect(share)

    dir_open = Open(tree, path)
    delete_msgs = [
        dir_open.create(
            ImpersonationLevel.Impersonation,
            DirectoryAccessMask.DELETE,
            FileAttributes.FILE_ATTRIBUTE_DIRECTORY,
            0,
            CreateDisposition.FILE_OPEN,
            CreateOptions.FILE_DIRECTORY_FILE | CreateOptions.FILE_DELETE_ON_CLOSE,
            send=False,
        ),
        dir_open.close(False, send=False),
    ]
    delete_reqs = conn.connection.send_compound(
        [x[0] for x in delete_msgs],
        sid=conn.session.session_id,
        tid=tree.tree_connect_id,
        related=True,
    )
    for i, request in enumerate(delete_reqs):
        # A SMBResponseException will be raised if something went wrong
        response = delete_msgs[i][1](request)


def delete_directory(
    path, share="C$", conn=None, host=None, username=None, password=None
):
    if HAS_SMBPROTOCOL:
        return _delete_directory_smbprotocol(
            path, share, conn=conn, host=host, username=username, password=password
        )
    elif HAS_IMPACKET:
        return _delete_directory_impacket(
            path, share, conn=conn, host=host, username=username, password=password
        )
    raise MissingSmb("SMB library required (impacket or smbprotocol)")
