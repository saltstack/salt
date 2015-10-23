#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
Runs minion floscript
'''

from __future__ import absolute_import
from __future__ import print_function
# pylint: skip-file

import os
import stat

from ioflo.aid.odicting import odict
from ioflo.base.consoling import getConsole
console = getConsole()

import salt.daemons.flo

FLO_DIR_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'flo'
)

def test():
    """ Execute run.start """

    pkiDirpath = os.path.join('/tmp', 'raet', 'testo', 'minion', 'pki')
    if not os.path.exists(pkiDirpath):
        os.makedirs(pkiDirpath)

    acceptedDirpath = os.path.join(pkiDirpath, 'accepted')
    if not os.path.exists(acceptedDirpath):
        os.makedirs(acceptedDirpath)

    pendingDirpath = os.path.join(pkiDirpath, 'pending')
    if not os.path.exists(pendingDirpath):
        os.makedirs(pendingDirpath)

    rejectedDirpath = os.path.join(pkiDirpath, 'rejected')
    if not os.path.exists(rejectedDirpath):
        os.makedirs(rejectedDirpath)

    localFilepath = os.path.join(pkiDirpath, 'local.key')
    if os.path.exists(localFilepath):
        mode = os.stat(localFilepath).st_mode
        print(mode)
        os.chmod(localFilepath, mode | stat.S_IWUSR | stat.S_IRUSR)
        mode = os.stat(localFilepath).st_mode
        print(mode)


    cacheDirpath = os.path.join('/tmp/raet', 'cache', 'minion')
    if not os.path.exists(cacheDirpath):
        os.makedirs(cacheDirpath)

    sockDirpath = os.path.join('/tmp/raet', 'sock', 'minion')
    if not os.path.exists(sockDirpath):
            os.makedirs(sockDirpath)


    #filepath = os.path.join(FLO_DIR_PATH, 'minion.flo')
    filepath = 'minion.flo'
    opts = dict(
            id="minion",
            __role='minion',
            ioflo_period=0.1,
            ioflo_realtime=True,
            minion_floscript=filepath,
            ioflo_verbose=2,
            interface="",
            raet_port=7531,
            master_port=7530,
            master='127.0.0.1',
            transport='raet',
            client_acl=dict(),
            pki_dir=pkiDirpath,
            sock_dir=sockDirpath,
            cachedir=cacheDirpath,
            open_mode=True,
            auto_accept=True)

    minion = salt.daemons.flo.IofloMinion(opts=opts)
    minion.start(behaviors=['raet.flo.behaving'])

if __name__ == '__main__':
    console.reinit(verbosity=console.Wordage.concise)
    test()
