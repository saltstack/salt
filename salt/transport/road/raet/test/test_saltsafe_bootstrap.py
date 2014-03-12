# -*- coding: utf-8 -*-
'''
Tests to try out stacking. Potentially ephemeral

'''
# pylint: skip-file

import os
import stat

from ioflo.base.odicting import odict
from ioflo.base.aiding import Timer, StoreTimer
from ioflo.base import storing

from ioflo.base.consoling import getConsole
console = getConsole()

from salt.transport.road.raet import (raeting, nacling, packeting, keeping,
                                     estating, yarding, transacting, stacking,
                                     salting)


def test(preClearMaster=False, preClearMinion=False, postClearMaster=False, postClearMinion=False):
    '''
    initially
    master on port 7530 with eid of 1
    minion on port 7531 with eid of 0
    eventually
    master eid of 1
    minion eid of 2
    '''
    console.reinit(verbosity=console.Wordage.concise)

    pkiDirpath = os.path.join(os.getcwd(), 'keyo', 'master', 'pki')
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
        print mode
        os.chmod(localFilepath, mode | stat.S_IWUSR | stat.S_IWUSR)


    cacheDirpath = os.path.join(os.getcwd(), 'cache', 'master')
    sockDirpath = os.path.join('/tmp/raet', 'sock', 'master')

    masterOpts = dict(
                pki_dir=pkiDirpath,
                sock_dir=sockDirpath,
                cachedir=cacheDirpath,
                open_mode=False,
                auto_accept=False,
                )

    masterSafe = salting.SaltSafe(opts=masterOpts)
    print masterSafe.loadLocalData()
    print masterSafe.loadAllRemoteData()

    pkiDirpath = os.path.join(os.getcwd(), 'keyo', 'minion', 'pki')
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
        print mode
        os.chmod(localFilepath, mode | stat.S_IWUSR | stat.S_IWUSR)


    cacheDirpath = os.path.join(os.getcwd(), 'cache', 'minion')
    sockDirpath = os.path.join('/tmp/raet', 'sock', 'minion')

    minionOpts = dict(
                pki_dir=pkiDirpath,
                sock_dir=sockDirpath,
                cachedir=cacheDirpath,
                open_mode=False,
                auto_accept=True,
                )

    minionSafe = salting.SaltSafe(opts=minionOpts)
    print minionSafe.loadLocalData()
    print minionSafe.loadAllRemoteData()

    store = storing.Store(stamp=0.0)

    #master stack
    masterName = "master"
    signer = nacling.Signer()
    masterSignKeyHex = signer.keyhex
    privateer = nacling.Privateer()
    masterPriKeyHex = privateer.keyhex
    masterDirpath = os.path.join(os.getcwd(), 'keep', masterName)

    #minion0 stack
    minionName0 = "minion0"
    signer = nacling.Signer()
    minionSignKeyHex = signer.keyhex
    privateer = nacling.Privateer()
    minionPriKeyHex = privateer.keyhex
    m0Dirpath = os.path.join(os.getcwd(), 'keep', minionName0)

    if preClearMaster:
        salting.clearAllRoadSafe(masterDirpath, masterOpts)
    if preClearMinion:
        salting.clearAllRoadSafe(m0Dirpath, minionOpts)


    estate = estating.LocalEstate(  eid=1,
                                    name=masterName,
                                    sigkey=masterSignKeyHex,
                                    prikey=masterPriKeyHex,)
    stack0 = stacking.StackUdp(name=masterName,
                               estate=estate,
                               store=store,
                               main=True,
                               dirpath=masterDirpath,
                               safe=masterSafe, )


    estate = estating.LocalEstate(  eid=0,
                                    name=minionName0,
                                    ha=("", raeting.RAET_TEST_PORT),
                                    sigkey=minionSignKeyHex,
                                    prikey=minionPriKeyHex,)
    stack1 = stacking.StackUdp(name=minionName0,
                               estate=estate,
                               store=store,
                               dirpath=m0Dirpath,
                               safe=minionSafe, )

    print stack0.safe.loadLocalData()
    print stack1.safe.loadLocalData()



    print "\n********* Join Transaction **********"
    stack1.join()
    #timer = StoreTimer(store=store, duration=3.0)
    while stack1.transactions or stack0.transactions:
        stack1.serviceAll()
        stack0.serviceAll()
        if store.stamp >= 0.3:
            for estate in stack0.estates.values():
                if estate.acceptance == raeting.acceptances.pending:
                    stack0.safe.acceptRemoteEstate(estate)
        store.advanceStamp(0.1)

    for estate in stack0.estates.values():
        print "Remote Estate {0} joined= {1}".format(estate.eid, estate.joined)
    for estate in stack1.estates.values():
        print "Remote Estate {0} joined= {1}".format(estate.eid, estate.joined)


    print "{0} eid={1}".format(stack0.name, stack0.estate.eid)
    print "{0} estates=\n{1}".format(stack0.name, stack0.estates)
    print "{0} transactions=\n{1}".format(stack0.name, stack0.transactions)
    print "{0} eid={1}".format(stack1.name, stack1.estate.eid)
    print "{0} estates=\n{1}".format(stack1.name, stack1.estates)
    print "{0} transactions=\n{1}".format(stack1.name, stack1.transactions)


    print "Road {0}".format(stack0.name)
    print stack0.road.loadLocalData()
    print stack0.road.loadAllRemoteData()
    print "Safe {0}".format(stack0.name)
    print stack0.safe.loadLocalData()
    print stack0.safe.loadAllRemoteData()
    print

    print "Road {0}".format(stack1.name)
    print stack1.road.loadLocalData()
    print stack1.road.loadAllRemoteData()
    print "Safe {0}".format(stack1.name)
    print stack1.safe.loadLocalData()
    print stack1.safe.loadAllRemoteData()
    print

    stack0.server.close()
    stack1.server.close()

    if postClearMaster:
        salting.clearAllRoadSafe(masterDirpath, masterOpts)
    if postClearMinion:
        salting.clearAllRoadSafe(m0Dirpath, minionOpts)



if __name__ == "__main__":
    test(True, True, False, True)
    test(False, False, True, True)
    test(False, False, False, False)
    test(False, False, True, True)
