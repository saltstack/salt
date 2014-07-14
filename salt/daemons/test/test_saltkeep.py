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

        self.tempDirpath = tempfile.mkdtemp(prefix="salt", suffix='keep', dir='/tmp')

    def tearDown(self):
        if os.path.exists(self.tempDirpath):
            shutil.rmtree(self.tempDirpath)

    def createOpts(self, name, dirpath, openMode=False, autoAccept=True):
        '''
        Create associated pki directories for stack and return opts
        '''

        pkiDirpath = os.path.join(dirpath, 'pki', name, 'raet')
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

        cacheDirpath = os.path.join(dirpath, 'cache', name)
        sockDirpath = os.path.join(dirpath, 'sock', name)

        opts = dict(
                     pki_dir=pkiDirpath,
                     sock_dir=sockDirpath,
                     cachedir=cacheDirpath,
                     open_mode=openMode,
                     auto_accept=autoAccept,
                     transport='raet',
                     )
        return opts

    def createRoadData(self, name, cachedirpath):
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
        data['basedirpath'] = os.path.join(cachedirpath, 'raet')
        signer = nacling.Signer()
        data['sighex'] = signer.keyhex
        data['verhex'] = signer.verhex
        privateer = nacling.Privateer()
        data['prihex'] = privateer.keyhex
        data['pubhex'] = privateer.pubhex

        return data

    def createRoadStack(self, data, keep,  eid=0, main=None, ha=None):
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
                                   store=self.store,
                                   keep=keep)

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

        opts = self.createOpts(name='main',
                               dirpath=self.tempDirpath,
                               openMode=True,
                               autoAccept=True)
        mainData = self.createRoadData(name='main', cachedirpath=opts['cachedir'] )
        mainKeep = salting.SaltKeep(opts=opts,
                                    basedirpath=mainData['basedirpath'],
                                    stackname=mainData['name'])

        self.assertEqual(mainKeep.loadLocalData(), None)
        self.assertEqual(mainKeep.loadAllRemoteData(), {})

        main = self.createRoadStack(data=mainData,
                                     eid=1,
                                     main=True,
                                     ha=None, #default ha is ("", raeting.RAET_PORT)
                                     keep=mainKeep)

        console.terse("{0}\nkeep dirpath = {1}\n".format(
                main.name, main.keep.dirpath))
        self.assertTrue(main.keep.dirpath.endswith('main/raet/main'))
        self.assertTrue(main.local.ha, ("0.0.0.0", raeting.RAET_PORT))
        self.assertTrue(main.keep.auto)
        self.assertDictEqual(main.keep.loadLocalData(), {'uid': 1,
                                                         'name': 'main',
                                                         'ha': ['0.0.0.0', 7530],
                                                         'main': True,
                                                         'sid': 0,
                                                         'neid': 1,
                                                         'sighex': mainData['sighex'],
                                                         'prihex': mainData['prihex'],
                                                         'auto': True,
                                                         })

        data1 = self.createRoadData(name='remote1', cachedirpath=opts['cachedir'])
        main.addRemote(estating.RemoteEstate(stack=main,
                                             eid=3,
                                             name=data1['name'],
                                             ha=('127.0.0.1', 7532),
                                             verkey=data1['verhex'],
                                             pubkey=data1['pubhex'],
                                             period=main.period,
                                             offset=main.offset, ))

        data2 = self.createRoadData(name='remote2', cachedirpath=opts['cachedir'])
        main.addRemote(estating.RemoteEstate(stack=main,
                                             eid=4,
                                             name=data2['name'],
                                             ha=('127.0.0.1', 7533),
                                             verkey=data2['verhex'],
                                             pubkey=data2['pubhex'],
                                             period=main.period,
                                             offset=main.offset,))

        main.dumpRemotes()

        self.assertDictEqual(main.keep.loadAllRemoteData(),
            {'3':
                {'uid': 3,
                 'name': data1['name'],
                 'ha': ['127.0.0.1', 7532],
                 'sid': 0,
                 'joined': None,
                 'acceptance': 1,
                 'verhex': data1['verhex'],
                 'pubhex': data1['pubhex']},
            '4':
                {'uid': 4,
                 'name': data2['name'],
                 'ha': ['127.0.0.1', 7533],
                 'sid': 0,
                 'joined': None,
                 'acceptance': 1,
                 'verhex': data2['verhex'],
                 'pubhex': data2['pubhex']}})

        # now recreate with saved data
        main.server.close()
        mainKeep = salting.SaltKeep(opts=opts,
                                     basedirpath=mainData['basedirpath'],
                                     stackname=mainData['name'])
        main = stacking.RoadStack(name=mainData['name'],
                                  store=self.store,
                                  keep=mainKeep)

        self.assertEqual(main.local.priver.keyhex, mainData['prihex'])
        self.assertEqual(main.local.signer.keyhex, mainData['sighex'])

        self.assertEqual(len(main.remotes.values()), 2)

        # other stack
        opts = self.createOpts(name='other',
                               dirpath=self.tempDirpath,
                               openMode=True,
                               autoAccept=True)
        otherData = self.createRoadData(name='other', cachedirpath=opts['cachedir'] )
        otherKeep = salting.SaltKeep(opts=opts,
                                      basedirpath=otherData['basedirpath'],
                                      stackname=otherData['name'])

        self.assertEqual(otherKeep.loadLocalData(), None)
        self.assertEqual(otherKeep.loadAllRemoteData(), {})

        other = self.createRoadStack(data=otherData,
                                     eid=0,
                                     main=None,
                                     ha=("", raeting.RAET_TEST_PORT),
                                     keep=otherKeep)

        console.terse("{0} keep dirpath = {1}\n".format(
                other.name, other.keep.dirpath))
        self.assertTrue(other.keep.dirpath.endswith('other/raet/other'))
        self.assertEqual(other.local.ha, ("0.0.0.0", raeting.RAET_TEST_PORT))

        self.assertDictEqual(other.keep.loadLocalData(),
                            {
                                'uid': 0,
                                'name': 'other',
                                'ha': ['0.0.0.0', 7531],
                                'main': None,
                                'sid': 0,
                                'neid': 1,
                                'sighex': otherData['sighex'],
                                'prihex': otherData['prihex'],
                                'auto': True,
                            })

        data3 = self.createRoadData(name='remote3', cachedirpath=opts['cachedir'])
        other.addRemote(estating.RemoteEstate(stack=other,
                                              eid=3,
                                              name=data3['name'],
                                              ha=('127.0.0.1', 7534),
                                              verkey=data3['verhex'],
                                              pubkey=data3['pubhex'],
                                              period=main.period,
                                              offset=main.offset,))

        data4 = self.createRoadData(name='remote4', cachedirpath=opts['cachedir'])
        other.addRemote(estating.RemoteEstate(stack=other,
                                              eid=4,
                                              name=data4['name'],
                                              ha=('127.0.0.1', 7535),
                                              verkey=data4['verhex'],
                                              pubkey=data4['pubhex'],
                                             period=main.period,
                                             offset=main.offset,))

        other.dumpRemotes()
        self.assertDictEqual(other.keep.loadAllRemoteData(),
            {
                '3':
                {
                    'uid': 3,
                    'name': data3['name'],
                    'ha': ['127.0.0.1', 7534],
                    'sid': 0,
                    'joined': None,
                    'acceptance': 1,
                    'verhex': data3['verhex'],
                    'pubhex': data3['pubhex']
                },
                '4':
                {
                    'uid': 4,
                    'name': data4['name'],
                    'ha': ['127.0.0.1', 7535],
                    'sid': 0,
                    'joined': None,
                    'acceptance': 1,
                    'verhex': data4['verhex'],
                    'pubhex': data4['pubhex']
                }
            })

        main.server.close()
        other.server.close()

    def testBootstrapClean(self):
        '''
        Basic keep setup for stack keep and safe persistence load and dump
        '''
        console.terse("{0}\n".format(self.testBootstrapClean.__doc__))

        opts = self.createOpts(name='main',
                               dirpath=self.tempDirpath,
                               openMode=True,
                               autoAccept=True)
        mainData = self.createRoadData(name='main', cachedirpath=opts['cachedir'] )
        mainKeep = salting.SaltKeep(opts=opts,
                                    basedirpath=mainData['basedirpath'],
                                    stackname=mainData['name'])

        self.assertEqual(mainKeep.loadLocalData(), None)
        self.assertEqual(mainKeep.loadAllRemoteData(), {})

        main = self.createRoadStack(data=mainData,
                                     eid=1,
                                     main=True,
                                     ha=None, #default ha is ("", raeting.RAET_PORT)
                                     keep=mainKeep)

        console.terse("{0}\nkeep dirpath = {1}\n".format(
                main.name, main.keep.dirpath))
        self.assertTrue(main.keep.dirpath.endswith('main/raet/main'))
        self.assertTrue(main.local.ha, ("0.0.0.0", raeting.RAET_PORT))
        self.assertTrue(main.keep.auto)
        self.assertDictEqual(main.keep.loadLocalData(), {'uid': 1,
                                                         'name': 'main',
                                                         'ha': ['0.0.0.0', 7530],
                                                         'main': True,
                                                         'sid': 0,
                                                         'neid': 1,
                                                         'sighex': mainData['sighex'],
                                                         'prihex': mainData['prihex'],
                                                         'auto': True,
                                                         })

        opts = self.createOpts(name='other',
                               dirpath=self.tempDirpath,
                               openMode=True,
                               autoAccept=True)
        otherData = self.createRoadData(name='other', cachedirpath=opts['cachedir'] )
        otherKeep = salting.SaltKeep(opts=opts,
                                      basedirpath=otherData['basedirpath'],
                                      stackname=otherData['name'])

        self.assertEqual(otherKeep.loadLocalData(), None)
        self.assertEqual(otherKeep.loadAllRemoteData(), {})

        other = self.createRoadStack(data=otherData,
                                     eid=0,
                                     main=None,
                                     ha=("", raeting.RAET_TEST_PORT),
                                     keep=otherKeep)

        console.terse("{0} keep dirpath = {1}\n".format(
                other.name, other.keep.dirpath))
        self.assertTrue(other.keep.dirpath.endswith('other/raet/other'))
        self.assertEqual(other.local.ha, ("0.0.0.0", raeting.RAET_TEST_PORT))
        self.assertDictEqual(other.keep.loadLocalData(),
                            {
                                'uid': 0,
                                'name': 'other',
                                'ha': ['0.0.0.0', 7531],
                                'main': None,
                                'sid': 0,
                                'neid': 1,
                                'sighex': otherData['sighex'],
                                'prihex': otherData['prihex'],
                                'auto': True,
                            })

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
    names = ['testBasic',
             'testBootstrapClean', ]

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

    runSome()#only run some

    #runOne('testBootstrapClean')
