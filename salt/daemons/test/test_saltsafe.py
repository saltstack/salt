# -*- coding: utf-8 -*-
'''
Tests to try out salt key.RaetKey Potentially ephemeral

'''
# pylint: skip-file
# pylint: disable=C0103
import sys
if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

import os
import stat
import time
import tempfile
import shutil

from ioflo.base.odicting import odict
from ioflo.base.aiding import Timer, StoreTimer
from ioflo.base import storing
from ioflo.base.consoling import getConsole
console = getConsole()

from raet import raeting, nacling
from raet.road import estating, keeping, stacking

from salt.key import RaetKey
from salt.daemons import salting

def setUpModule():
    console.reinit(verbosity=console.Wordage.concise)

def tearDownModule():
    pass


def test():
    '''
    Test keeping.
    '''
    pkiDirpath = os.path.join('/tmp', 'raet', 'keyo', 'master', 'pki')
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
        os.chmod(localFilepath, mode | stat.S_IWUSR | stat.S_IRUSR)
        mode = os.stat(localFilepath).st_mode
        print mode

    cacheDirpath = os.path.join('/tmp/raet', 'cache', 'master')
    if not os.path.exists(cacheDirpath):
        os.makedirs(cacheDirpath)

    sockDirpath = os.path.join('/tmp/raet', 'sock', 'master')
    if not os.path.exists(sockDirpath):
            os.makedirs(sockDirpath)

    opts = dict(
                pki_dir=pkiDirpath,
                sock_dir=sockDirpath,
                cachedir=cacheDirpath,
                open_mode=True,
                auto_accept=True,
                transport='raet',
                )

    masterSafe = salting.SaltSafe(opts=opts)
    print("masterSafe local =\n{0}".format(masterSafe.loadLocalData()))
    print("masterSafe remote =\n{0}".format(masterSafe.loadAllRemoteData()))

    pkiDirpath = os.path.join('/tmp', 'raet', 'keyo', 'minion', 'pki')
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
        os.chmod(localFilepath, mode | stat.S_IWUSR | stat.S_IRUSR)



    cacheDirpath = os.path.join('/tmp/raet', 'cache', 'minion')
    sockDirpath = os.path.join('/tmp/raet', 'sock', 'minion')

    opts = dict(
                pki_dir=pkiDirpath,
                sock_dir=sockDirpath,
                cachedir=cacheDirpath,
                open_mode=True,
                auto_accept=True,
                transport='raet',
                )

    minionSafe = salting.SaltSafe(opts=opts)
    print("minionSafe local =\n{0}".format(minionSafe.loadLocalData()))
    print("minionSafe remote =\n{0}".format(minionSafe.loadAllRemoteData()))

    masterName = 'master'
    masterDirpath = os.path.join('/tmp', 'raet', 'keep', masterName )
    signer = nacling.Signer()
    masterSignKeyHex = signer.keyhex
    masterVerKeyHex = signer.verhex
    privateer = nacling.Privateer()
    masterPriKeyHex = privateer.keyhex
    masterPubKeyHex = privateer.pubhex

    m1Name = 'minion1'
    m1Dirpath = os.path.join('/tmp', 'raet', 'keep', m1Name)
    signer = nacling.Signer()
    m1SignKeyHex = signer.keyhex
    m1VerKeyHex = signer.verhex
    privateer = nacling.Privateer()
    m1PriKeyHex = privateer.keyhex
    m1PubKeyHex = privateer.pubhex

    m2Name = 'minion2'
    signer = nacling.Signer()
    m2SignKeyHex = signer.keyhex
    m2VerKeyHex = signer.verhex
    privateer = nacling.Privateer()
    m2PriKeyHex = privateer.keyhex
    m2PubKeyHex = privateer.pubhex

    m3Name = 'minion3'
    signer = nacling.Signer()
    m3SignKeyHex = signer.keyhex
    m3VerKeyHex = signer.verhex
    privateer = nacling.Privateer()
    m3PriKeyHex = privateer.keyhex
    m3PubKeyHex = privateer.pubhex

    keeping.clearAllKeepSafe(masterDirpath)
    keeping.clearAllKeepSafe(m1Dirpath)

    #saltsafe = salting.SaltSafe(opts=opts)
    #print saltsafe.loadLocalData()
    #print saltsafe.loadAllRemoteData()

    #master stack
    local = estating.LocalEstate(  eid=1,
                                    name=masterName,
                                    sigkey=masterSignKeyHex,
                                    prikey=masterPriKeyHex,)
    stack0 = stacking.RoadStack(local=local,
                               dirpath=masterDirpath,
                               safe=masterSafe)

    stack0.addRemote(estating.RemoteEstate(eid=2,
                                    name=m1Name,
                                    ha=('127.0.0.1', 7532),
                                    verkey=m1VerKeyHex,
                                    pubkey=m1PubKeyHex,))

    stack0.addRemote(estating.RemoteEstate(eid=3,
                                    name=m2Name,
                                    ha=('127.0.0.1', 7533),
                                    verkey=m2VerKeyHex,
                                    pubkey=m2PubKeyHex,))

    #minion stack
    local = estating.LocalEstate(   eid=2,
                                     name=m1Name,
                                     ha=("", raeting.RAET_TEST_PORT),
                                     sigkey=m1SignKeyHex,
                                     prikey=m1PriKeyHex,)
    stack1 = stacking.RoadStack(local=local,
                               dirpath=m1Dirpath,
                               safe=minionSafe)


    stack1.addRemote(estating.RemoteEstate(eid=1,
                                    name=masterName,
                                    ha=('127.0.0.1', 7532),
                                    verkey=masterVerKeyHex,
                                    pubkey=masterPubKeyHex,))

    stack1.addRemote(estating.RemoteEstate(eid=4,
                                    name=m3Name,
                                    ha=('127.0.0.1', 7534),
                                    verkey=m3VerKeyHex,
                                    pubkey=m3PubKeyHex,))

    #stack0.clearLocal()
    stack0.clearRemoteKeeps()
    #stack1.clearLocal()
    stack1.clearRemoteKeeps()

    stack0.dumpLocal()
    stack0.dumpRemotes()

    stack1.dumpLocal()
    stack1.dumpRemotes()

    print "Road {0}".format(stack0.name)
    print stack0.keep.loadLocalData()
    print stack0.keep.loadAllRemoteData()
    print "Safe {0}".format(stack0.name)
    print stack0.safe.loadLocalData()
    print stack0.safe.loadAllRemoteData()
    print

    print "Road {0}".format(stack1.name)
    print stack1.keep.loadLocalData()
    print stack1.keep.loadAllRemoteData()
    print "Safe {0}".format(stack1.name)
    print stack1.safe.loadLocalData()
    print stack1.safe.loadAllRemoteData()

    stack0.server.close()
    stack1.server.close()

    #master stack
    dirpath = os.path.join('/tmp/raet', 'keep', 'master')
    local = estating.LocalEstate(  eid=1,
                                    name='master',
                                    sigkey=masterSignKeyHex,
                                    prikey=masterPriKeyHex,)
    stack0 = stacking.RoadStack(local=local,
                               dirpath=masterDirpath,
                               safe=masterSafe)

    #minion stack
    dirpath = os.path.join('/tmp/raet', 'keep', 'minion1')
    local = estating.LocalEstate(   eid=2,
                                     name='minion1',
                                     ha=("", raeting.RAET_TEST_PORT),
                                     sigkey=m1SignKeyHex,
                                     prikey=m1PriKeyHex,)
    stack1 = stacking.RoadStack(local=local,
                               dirpath=m1Dirpath,
                               safe=minionSafe)


    stack0.loadLocal()
    print stack0.local.name, stack0.local.eid, stack0.local.sid, stack0.local.ha, stack0.local.signer, stack0.local.priver
    stack1.loadLocal()
    print stack1.local.name, stack1.local.eid, stack1.local.sid, stack1.local.ha, stack1.local.signer, stack1.local.priver

    stack0.clearLocal()
    stack0.clearRemoteKeeps()
    stack1.clearLocal()
    stack1.clearRemoteKeeps()


#if __name__ == "__main__":
    #test()


class BasicTestCase(unittest.TestCase):
    """"""

    def setUp(self):
        self.store = storing.Store(stamp=0.0)
        self.timer = StoreTimer(store=self.store, duration=1.0)

        self.mainDirpath = tempfile.mkdtemp(prefix="salt", suffix='main', dir='/tmp')
        opts = self.createOpts(self.mainDirpath, openMode=True, autoAccept=True)
        self.mainSafe = salting.SaltSafe(opts=opts)

        self.otherDirpath = tempfile.mkdtemp(prefix="salt", suffix='other', dir='/tmp')
        opts = self.createOpts(self.otherDirpath, openMode=True, autoAccept=True)
        self.otherSafe = salting.SaltSafe(opts=opts)

        self.baseDirpath = tempfile.mkdtemp(prefix="raet",  suffix="base", dir='/tmp')

    def tearDown(self):
        if os.path.exists(self.mainDirpath):
            shutil.rmtree(self.mainDirpath)

        if os.path.exists(self.otherDirpath):
            shutil.rmtree(self.otherDirpath)

        if os.path.exists(self.baseDirpath):
            shutil.rmtree(self.baseDirpath)

    def createOpts(self, dirpath, openMode=True, autoAccept=True):
        '''
        Create associated pki directories for stack and return opts
        '''

        pkiDirpath = os.path.join(dirpath, 'pki')
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

        cacheDirpath = os.path.join(dirpath, 'cache')
        sockDirpath = os.path.join(dirpath, 'sock')

        opts = dict(
                     pki_dir=pkiDirpath,
                     sock_dir=sockDirpath,
                     cachedir=cacheDirpath,
                     open_mode=openMode,
                     auto_accept=autoAccept,
                     transport='raet',
                     )
        return opts

    def createRoadData(self, name, base):
        '''
        Creates odict and populates with data to setup road stack
        {
            name: stack name local estate name
            dirpath: dirpath for keep files
            sighex: signing key
            verhex: verify key
            prihex: private key
            pubhex: public key
        }
        '''
        data = odict()
        data['name'] = name
        data['dirpath'] = os.path.join(base, 'road', 'keep', name)
        signer = nacling.Signer()
        data['sighex'] = signer.keyhex
        data['verhex'] = signer.verhex
        privateer = nacling.Privateer()
        data['prihex'] = privateer.keyhex
        data['pubhex'] = privateer.pubhex

        return data

    def createRoadStack(self, data, eid=0, main=None, auto=None, ha=None, safe=None):
        '''
        Creates stack and local estate from data with
        local estate.eid = eid
        stack.main = main
        stack.auto = auto
        stack.name = data['name']
        local estate.name = data['name']
        local estate.ha = ha

        returns stack

        '''
        local = estating.LocalEstate(eid=eid,
                                     name=data['name'],
                                     ha=ha,
                                     sigkey=data['sighex'],
                                     prikey=data['prihex'],)

        stack = stacking.RoadStack(name=data['name'],
                                   local=local,
                                   main=main,
                                   dirpath=data['dirpath'],
                                   store=self.store,
                                   safe=safe,
                                   auto=auto,)

        return stack

    def join(self, other, main, duration=1.0):
        '''
        Utility method to do join. Call from test method.
        '''
        console.terse("\nJoin Transaction **************\n")
        other.join()
        self.service(main, other, duration=duration)

    def allow(self, other, main, duration=1.0):
        '''
        Utility method to do allow. Call from test method.
        '''
        console.terse("\nAllow Transaction **************\n")
        other.allow()
        self.service(main, other, duration=duration)

    def message(self, main,  other, mains, others, duration=2.0):
        '''
        Utility to send messages both ways
        '''
        for msg in mains:
            main.transmit(msg)
        for msg in others:
            other.transmit(msg)

        self.service(main, other, duration=duration)

    def service(self, main, other, duration=1.0):
        '''
        Utility method to service queues. Call from test method.
        '''
        self.timer.restart(duration=duration)
        while not self.timer.expired:
            other.serviceAll()
            main.serviceAll()
            if not (main.transactions or other.transactions):
                break
            self.store.advanceStamp(0.1)
            time.sleep(0.1)

    def testBasic(self):
        '''
        Basic keep setup for stack keep and safe persistence load and dump
        '''
        console.terse("{0}\n".format(self.testBasic.__doc__))

        self.assertEqual(self.mainSafe.loadLocalData(), None)
        self.assertEqual(self.mainSafe.loadAllRemoteData(), {})

        data = self.createRoadData(name='main', base=self.baseDirpath)
        main = self.createRoadStack(data=data,
                                     eid=1,
                                     main=True,
                                     ha=None, #default ha is ("", raeting.RAET_PORT)
                                     safe=self.mainSafe)

        console.terse("{0}\nkeep dirpath = {1}\nsafe dirpath = {2}\n".format(
                main.name, main.keep.dirpath, main.safe.dirpath))
        self.assertTrue(main.keep.dirpath.endswith('road/keep/main'))
        self.assertTrue(main.safe.dirpath.endswith('pki'))
        self.assertTrue(main.local.ha, ("0.0.0.0", raeting.RAET_PORT))
        self.assertTrue(main.safe.auto)

        data = self.createRoadData(name='other', base=self.baseDirpath)
        other = self.createRoadStack(data=data,
                                     eid=0,
                                     main=None,
                                     ha=("", raeting.RAET_TEST_PORT),
                                     safe=self.otherSafe)

        console.terse("{0} keep dirpath = {1} safe dirpath = {0}\n".format(
                other.name, other.keep.dirpath, other.safe.dirpath))
        self.assertTrue(other.keep.dirpath.endswith('road/keep/other'))
        self.assertTrue(other.safe.dirpath.endswith('pki'))
        self.assertEqual(other.local.ha, ("0.0.0.0", raeting.RAET_TEST_PORT))




def runOne(test):
    '''
    Unittest Runner
    '''
    test = BasicTestCase(test)
    suite = unittest.TestSuite([test])
    unittest.TextTestRunner(verbosity=2).run(suite)

def runSome():
    '''
    Unittest runner
    '''
    tests =  []
    names = ['testBasic',]

    tests.extend(map(BasicTestCase, names))

    suite = unittest.TestSuite(tests)
    unittest.TextTestRunner(verbosity=2).run(suite)

def runAll():
    '''
    Unittest runner
    '''
    suite = unittest.TestSuite()
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(BasicTestCase))

    unittest.TextTestRunner(verbosity=2).run(suite)

if __name__ == '__main__' and __package__ is None:

    #console.reinit(verbosity=console.Wordage.concise)

    #runAll() #run all unittests

    #runSome()#only run some

    runOne('testBasic')
