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

    def createOpts(self, dirpath, openMode=False, autoAccept=True):
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

        dataMain = self.createRoadData(name='main', base=self.baseDirpath)
        main = self.createRoadStack(data=dataMain,
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
        self.assertDictEqual(main.keep.loadLocalData(), {'uid': 1,
                                                         'name': 'main',
                                                         'ha': ['0.0.0.0', 7530],
                                                         'main': True,
                                                         'sid': 0,
                                                         'neid': 1,})
        self.assertDictEqual(main.safe.loadLocalData(), {'prihex': dataMain['prihex'],
                                                     'sighex': dataMain['sighex'],
                                                     'auto': True})


        data1 = self.createRoadData(name='remote1', base=self.baseDirpath)
        main.addRemote(estating.RemoteEstate(stack=main,
                                             eid=3,
                                             name=data1['name'],
                                             ha=('127.0.0.1', 7532),
                                             verkey=data1['verhex'],
                                             pubkey=data1['pubhex'],
                                             period=main.period,
                                             offset=main.offset, ))

        data2 = self.createRoadData(name='remote2', base=self.baseDirpath)
        main.addRemote(estating.RemoteEstate(stack=main,
                                             eid=4,
                                             name=data2['name'],
                                             ha=('127.0.0.1', 7533),
                                             verkey=data2['verhex'],
                                             pubkey=data2['pubhex'],
                                             period=main.period,
                                             offset=main.offset,))

        main.dumpRemotes()

        self.assertDictEqual(main.safe.loadAllRemoteData(),
            {'3':
                {'uid': 3,
                 'name': data1['name'],
                 'acceptance': 1,
                 'verhex': data1['verhex'],
                 'pubhex': data1['pubhex']},
            '4':
                {'uid': 4,
                 'name': data2['name'],
                 'acceptance': 1,
                 'verhex': data2['verhex'],
                 'pubhex': data2['pubhex']}})

        self.assertDictEqual(main.keep.loadAllRemoteData(),
            {'3':
                {'uid': 3,
                 'name': 'remote1',
                 'ha': ['127.0.0.1', 7532],
                 'sid': 0,
                 'rsid': 0},
            '4':
                {'uid': 4,
                 'name': 'remote2',
                 'ha': ['127.0.0.1', 7533],
                 'sid': 0,
                 'rsid': 0}})

        # now recreate with saved data
        main.server.close()
        main = stacking.RoadStack(name='main',
                                  dirpath=dataMain['dirpath'],
                                  store=self.store,
                                  safe=self.mainSafe)

        self.assertEqual(main.local.priver.keyhex, dataMain['prihex'])
        self.assertEqual(main.local.signer.keyhex, dataMain['sighex'])

        self.assertEqual(len(main.remotes.values()), 2)

        self.assertEqual(self.otherSafe.loadLocalData(), None)
        self.assertEqual(self.otherSafe.loadAllRemoteData(), {})

        # other stack

        dataOther = self.createRoadData(name='other', base=self.baseDirpath)
        other = self.createRoadStack(data=dataOther,
                                     eid=0,
                                     main=None,
                                     ha=("", raeting.RAET_TEST_PORT),
                                     safe=self.otherSafe)

        console.terse("{0} keep dirpath = {1} safe dirpath = {2}\n".format(
                other.name, other.keep.dirpath, other.safe.dirpath))
        self.assertTrue(other.keep.dirpath.endswith('road/keep/other'))
        self.assertTrue(other.safe.dirpath.endswith('pki'))
        self.assertEqual(other.local.ha, ("0.0.0.0", raeting.RAET_TEST_PORT))

        self.assertDictEqual(other.safe.loadLocalData(), {'prihex': dataOther['prihex'],
                                                        'sighex': dataOther['sighex'],
                                                        'auto': True,})

        data3 = self.createRoadData(name='remote3', base=self.baseDirpath)
        other.addRemote(estating.RemoteEstate(stack=other,
                                              eid=3,
                                              name=data3['name'],
                                              ha=('127.0.0.1', 7534),
                                              verkey=data3['verhex'],
                                              pubkey=data3['pubhex'],
                                              period=main.period,
                                              offset=main.offset,))

        data4 = self.createRoadData(name='remote4', base=self.baseDirpath)
        other.addRemote(estating.RemoteEstate(stack=other,
                                              eid=4,
                                              name=data4['name'],
                                              ha=('127.0.0.1', 7535),
                                              verkey=data4['verhex'],
                                              pubkey=data4['pubhex'],
                                             period=main.period,
                                             offset=main.offset,))

        other.dumpRemotes()
        self.assertDictEqual(other.safe.loadAllRemoteData(),
            {'3':
                {'uid': 3,
                 'name': data3['name'],
                 'acceptance': 1,
                 'verhex': data3['verhex'],
                 'pubhex': data3['pubhex']},
            '4':
                {'uid': 4,
                 'name': data4['name'],
                 'acceptance': 1,
                 'verhex': data4['verhex'],
                 'pubhex': data4['pubhex']}})
        other.server.close()

        self.assertDictEqual(other.keep.loadAllRemoteData(),
            {'3':
                {'uid': 3,
                 'name': 'remote3',
                 'ha': ['127.0.0.1', 7534],
                 'sid': 0,
                 'rsid': 0},
            '4':
                {'uid': 4,
                 'name': 'remote4',
                 'ha': ['127.0.0.1', 7535],
                 'sid': 0,
                 'rsid': 0}})

        main.server.close()
        other.server.close()

    def testBootstrapClean(self):
        '''
        Basic keep setup for stack keep and safe persistence load and dump
        '''
        console.terse("{0}\n".format(self.testBasic.__doc__))

        self.assertEqual(self.mainSafe.loadLocalData(), None)
        self.assertEqual(self.mainSafe.loadAllRemoteData(), {})

        dataMain = self.createRoadData(name='main', base=self.baseDirpath)
        main = self.createRoadStack(data=dataMain,
                                     eid=1,
                                     main=True,
                                     ha=None, #default ha is ("", raeting.RAET_PORT)
                                     safe=self.mainSafe)

        self.assertTrue(main.keep.dirpath.endswith('road/keep/main'))
        self.assertTrue(main.safe.dirpath.endswith('pki'))
        self.assertTrue(main.local.ha, ("0.0.0.0", raeting.RAET_PORT))
        self.assertTrue(main.safe.auto)
        self.assertDictEqual(main.keep.loadLocalData(), {'uid': 1,
                                                         'name': 'main',
                                                         'ha': ['0.0.0.0', 7530],
                                                         'main': True,
                                                         'sid': 0,
                                                         'neid': 1,})
        self.assertDictEqual(main.safe.loadLocalData(), {'prihex': dataMain['prihex'],
                                                     'sighex': dataMain['sighex'],
                                                     'auto': True,})

        self.assertEqual(self.otherSafe.loadLocalData(), None)
        self.assertEqual(self.otherSafe.loadAllRemoteData(), {})

        dataOther = self.createRoadData(name='other', base=self.baseDirpath)
        other = self.createRoadStack(data=dataOther,
                                     eid=0,
                                     main=None,
                                     ha=("", raeting.RAET_TEST_PORT),
                                     safe=self.otherSafe)

        console.terse("{0} keep dirpath = {1} safe dirpath = {2}\n".format(
                other.name, other.keep.dirpath, other.safe.dirpath))
        self.assertTrue(other.keep.dirpath.endswith('road/keep/other'))
        self.assertTrue(other.safe.dirpath.endswith('pki'))
        self.assertEqual(other.local.ha, ("0.0.0.0", raeting.RAET_TEST_PORT))
        self.assertTrue(other.safe.auto)

        self.assertDictEqual(other.safe.loadLocalData(), {'prihex': dataOther['prihex'],
                                                        'sighex': dataOther['sighex'],
                                                        'auto': True,})

        self.join(other, main)
        self.assertEqual(len(main.transactions), 0)
        remote = main.remotes.values()[0]
        self.assertTrue(remote.joined)
        self.assertEqual(len(other.transactions), 0)
        remote = other.remotes.values()[0]
        self.assertTrue(remote.joined)

        self.allow(other, main)
        self.assertEqual(len(main.transactions), 0)
        remote = main.remotes.values()[0]
        self.assertTrue(remote.allowed)
        self.assertEqual(len(other.transactions), 0)
        remote = other.remotes.values()[0]
        self.assertTrue(remote.allowed)

        main.server.close()
        other.server.close()



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

    runAll() #run all unittests

    #runSome()#only run some

    #runOne('testBootstrap')
