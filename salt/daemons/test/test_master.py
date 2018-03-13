#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
Runs minion floscript

'''
from __future__ import absolute_import, print_function, unicode_literals
# pylint: skip-file
import os
import stat

from ioflo.aid.odicting import odict
from ioflo.base.consoling import getConsole
console = getConsole()

import salt.daemons.flo

def test():
    """ Execute run.start """

    pkiDirpath = os.path.join('/tmp', 'raet', 'testo', 'master', 'pki')
    if not os.path.exists(pkiDirpath):
        os.makedirs(pkiDirpath)

    keyDirpath = os.path.join('/tmp', 'raet', 'testo', 'key')
    if not os.path.exists(keyDirpath):
        os.makedirs(keyDirpath)

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

    cacheDirpath = os.path.join('/tmp/raet', 'cache', 'master')
    if not os.path.exists(cacheDirpath):
        os.makedirs(cacheDirpath)

    sockDirpath = os.path.join('/tmp/raet', 'sock', 'master')
    if not os.path.exists(sockDirpath):
            os.makedirs(sockDirpath)

    filepath = 'master.flo'
    opts = dict(
            id='master',
            __role='master',
            ioflo_period=0.1,
            ioflo_realtime=True,
            master_floscript=filepath,
            ioflo_verbose=2,
            interface="",
            raet_port=7530,
            transport='raet',
            client_acl=dict(),
            publisher_acl=dict(),
            pki_dir=pkiDirpath,
            key_dir=keyDirpath,
            sock_dir=sockDirpath,
            cachedir=cacheDirpath,
            open_mode=True,
            auto_accept=True,
            client_acl_verify=True,
            )

    master = salt.daemons.flo.IofloMaster(opts=opts)
    master.start(behaviors=['raet.flo.behaving'])

if __name__ == '__main__':
    console.reinit(verbosity=console.Wordage.concise)
    test()
