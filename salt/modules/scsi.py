# -*- coding: utf-8 -*-
'''
SCSI administration module
'''

import os.path
import logging

log = logging.getLogger(__name__)


def lsscsi():
    '''
    List SCSI devices

    CLI Example:

    .. code-block:: bash

        salt '*' scsi.lsscsi
    '''
    cmd = 'lsscsi'
    return __salt__['cmd.run'](cmd).splitlines()


def rescan_all(host):
    '''
    List scsi devices

    CLI Example:

    .. code-block:: bash

        salt '*' scsi.rescan_all(0)
    '''
    if os.path.isdir('/sys/class/scsi_host/host{0}'.format(host)):
        cmd = 'echo "- - -" > /sys/class/scsi_host/host{0}/scan'.format(host)
    else:
        return 'Host {0} does not exist'.format(host)
    return __salt__['cmd.run'](cmd).splitlines()
