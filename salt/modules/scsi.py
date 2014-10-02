# -*- coding: utf-8 -*-
"""
SCSI administration module
"""
import logging
log = logging.getLogger(__name__)


def lsscsi():
    '''
    List scsi devices
    CLI Example:
    .. code-block:: bash
    salt '*' scsi.lsscsi
    '''
    cmd = 'lsscsi'
    return __salt__['cmd.run'](cmd).splitlines()