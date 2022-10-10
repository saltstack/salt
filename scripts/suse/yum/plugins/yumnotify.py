# Copyright (c) 2016 SUSE Linux LLC
# All Rights Reserved.
#
# Author: Bo Maryniuk <bo@suse.de>

import hashlib
import os

from yum.plugins import TYPE_CORE

CK_PATH = "/var/cache/salt/minion/rpmdb.cookie"
RPM_PATH = "/var/lib/rpm/Packages"

requires_api_version = "2.5"
plugin_type = TYPE_CORE


def _get_mtime():
    """
    Get the modified time of the RPM Database.

    Returns:
        Unix ticks
    """
    return os.path.exists(RPM_PATH) and int(os.path.getmtime(RPM_PATH)) or 0


def _get_checksum():
    """
    Get the checksum of the RPM Database.

    Returns:
        hexdigest
    """
    digest = hashlib.sha256()
    with open(RPM_PATH, "rb") as rpm_db_fh:
        while True:
            buff = rpm_db_fh.read(0x1000)
            if not buff:
                break
            digest.update(buff)
    return digest.hexdigest()


def posttrans_hook(conduit):
    """
    Hook after the package installation transaction.

    :param conduit:
    :return:
    """
    # Integrate Yum with Salt
    if "SALT_RUNNING" not in os.environ:
        with open(CK_PATH, "w") as ck_fh:
            ck_fh.write(
                "{chksum} {mtime}\n".format(chksum=_get_checksum(), mtime=_get_mtime())
            )
