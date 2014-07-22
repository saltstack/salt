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
        self.maxDiff = None

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
                     id=name,
                     pki_dir=pkiDirpath,
                     sock_dir=sockDirpath,
                     cachedir=cacheDirpath,
                     open_mode=openMode,
                     auto_accept=autoAccept,
                     transport='raet',
                     )
        return opts

    def createRoadData(self, name, cachedirpath, role=None):
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
        data['role'] = role or name

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
                                     prikey=data['prihex'],
                                     role=data['role'])

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
        Basic keep setup for stack keep persistence load and dump in normal mode
        '''
        console.terse("{0}\n".format(self.testBasic.__doc__))

        opts = self.createOpts(name='main',
                               dirpath=self.tempDirpath,
                               openMode=False,
                               autoAccept=False)
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
        self.assertFalse(main.keep.auto)
        self.assertDictEqual(main.keep.loadLocalData(), {'uid': 1,
                                                         'name': mainData['name'],
                                                         'ha': ['0.0.0.0', 7530],
                                                         'main': True,
                                                         'sid': 0,
                                                         'neid': 1,
                                                         'sighex': mainData['sighex'],
                                                         'prihex': mainData['prihex'],
                                                         'auto': False,
                                                         'role': mainData['role'],
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

        # acceptance will be pended

        self.assertDictEqual(main.keep.loadAllRemoteData(),
            {
                'remote1':
                    {'uid': 3,
                     'name': data1['name'],
                     'ha': ['127.0.0.1', 7532],
                     'sid': 0,
                     'joined': None,
                     'acceptance': 0,
                     'verhex': data1['verhex'],
                     'pubhex': data1['pubhex'],
                     'role': data1['role'],},
                'remote2':
                    {'uid': 4,
                     'name': data2['name'],
                     'ha': ['127.0.0.1', 7533],
                     'sid': 0,
                     'joined': None,
                     'acceptance': 0,
                     'verhex': data2['verhex'],
                     'pubhex': data2['pubhex'],
                     'role': data2['role'],}
            })

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
                               openMode=False,
                               autoAccept=False)
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
        self.assertFalse(other.keep.auto)

        self.assertDictEqual(other.keep.loadLocalData(),
                            {
                                'uid': 0,
                                'name': otherData['name'],
                                'ha': ['0.0.0.0', 7531],
                                'main': None,
                                'sid': 0,
                                'neid': 1,
                                'sighex': otherData['sighex'],
                                'prihex': otherData['prihex'],
                                'auto': False,
                                'role': otherData['role'],
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
                'remote3':
                {
                    'uid': 3,
                    'name': data3['name'],
                    'ha': ['127.0.0.1', 7534],
                    'sid': 0,
                    'joined': None,
                    'acceptance': 0,
                    'verhex': data3['verhex'],
                    'pubhex': data3['pubhex'],
                    'role': data3['role'],
                },
                'remote4':
                {
                    'uid': 4,
                    'name': data4['name'],
                    'ha': ['127.0.0.1', 7535],
                    'sid': 0,
                    'joined': None,
                    'acceptance': 0,
                    'verhex': data4['verhex'],
                    'pubhex': data4['pubhex'],
                    'role': data4['role'],
                }
            })

        main.server.close()
        other.server.close()

    def testBasicOpen(self):
        '''
        Basic keep setup for stack keep persistence load and dump in open mode
        '''
        console.terse("{0}\n".format(self.testBasicOpen.__doc__))

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
                                                         'name': mainData['name'],
                                                         'ha': ['0.0.0.0', 7530],
                                                         'main': True,
                                                         'sid': 0,
                                                         'neid': 1,
                                                         'sighex': mainData['sighex'],
                                                         'prihex': mainData['prihex'],
                                                         'auto': True,
                                                         'role': mainData['role'],
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
            {
                'remote1':
                    {'uid': 3,
                     'name': data1['name'],
                     'ha': ['127.0.0.1', 7532],
                     'sid': 0,
                     'joined': None,
                     'acceptance': 1,
                     'verhex': data1['verhex'],
                     'pubhex': data1['pubhex'],
                     'role': data1['role'],},
                'remote2':
                    {'uid': 4,
                     'name': data2['name'],
                     'ha': ['127.0.0.1', 7533],
                     'sid': 0,
                     'joined': None,
                     'acceptance': 1,
                     'verhex': data2['verhex'],
                     'pubhex': data2['pubhex'],
                     'role': data2['role'],}
            })

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
        self.assertTrue(other.keep.auto)

        self.assertDictEqual(other.keep.loadLocalData(),
                            {
                                'uid': 0,
                                'name': otherData['name'],
                                'ha': ['0.0.0.0', 7531],
                                'main': None,
                                'sid': 0,
                                'neid': 1,
                                'sighex': otherData['sighex'],
                                'prihex': otherData['prihex'],
                                'auto': True,
                                'role': otherData['role'],
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
                'remote3':
                {
                    'uid': 3,
                    'name': data3['name'],
                    'ha': ['127.0.0.1', 7534],
                    'sid': 0,
                    'joined': None,
                    'acceptance': 1,
                    'verhex': data3['verhex'],
                    'pubhex': data3['pubhex'],
                    'role': data3['role'],
                },
                'remote4':
                {
                    'uid': 4,
                    'name': data4['name'],
                    'ha': ['127.0.0.1', 7535],
                    'sid': 0,
                    'joined': None,
                    'acceptance': 1,
                    'verhex': data4['verhex'],
                    'pubhex': data4['pubhex'],
                    'role': data4['role'],
                }
            })

        main.server.close()
        other.server.close()

    def testBasicAuto(self):
        '''
        Basic keep setup for stack keep persistence load and dump with auto accept
        '''
        console.terse("{0}\n".format(self.testBasicAuto.__doc__))

        opts = self.createOpts(name='main',
                               dirpath=self.tempDirpath,
                               openMode=False,
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
                                                         'name': mainData['name'],
                                                         'ha': ['0.0.0.0', 7530],
                                                         'main': True,
                                                         'sid': 0,
                                                         'neid': 1,
                                                         'sighex': mainData['sighex'],
                                                         'prihex': mainData['prihex'],
                                                         'auto': True,
                                                         'role': mainData['role'],
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
            {
                'remote1':
                    {'uid': 3,
                     'name': data1['name'],
                     'ha': ['127.0.0.1', 7532],
                     'sid': 0,
                     'joined': None,
                     'acceptance': 1,
                     'verhex': data1['verhex'],
                     'pubhex': data1['pubhex'],
                     'role': data1['role'],},
                'remote2':
                    {'uid': 4,
                     'name': data2['name'],
                     'ha': ['127.0.0.1', 7533],
                     'sid': 0,
                     'joined': None,
                     'acceptance': 1,
                     'verhex': data2['verhex'],
                     'pubhex': data2['pubhex'],
                     'role': data2['role'],}
            })

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
                               openMode=False,
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
        self.assertTrue(other.keep.auto)

        self.assertDictEqual(other.keep.loadLocalData(),
                            {
                                'uid': 0,
                                'name': otherData['name'],
                                'ha': ['0.0.0.0', 7531],
                                'main': None,
                                'sid': 0,
                                'neid': 1,
                                'sighex': otherData['sighex'],
                                'prihex': otherData['prihex'],
                                'auto': True,
                                'role': otherData['role'],
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
                'remote3':
                {
                    'uid': 3,
                    'name': data3['name'],
                    'ha': ['127.0.0.1', 7534],
                    'sid': 0,
                    'joined': None,
                    'acceptance': 1,
                    'verhex': data3['verhex'],
                    'pubhex': data3['pubhex'],
                    'role': data3['role'],
                },
                'remote4':
                {
                    'uid': 4,
                    'name': data4['name'],
                    'ha': ['127.0.0.1', 7535],
                    'sid': 0,
                    'joined': None,
                    'acceptance': 1,
                    'verhex': data4['verhex'],
                    'pubhex': data4['pubhex'],
                    'role': data4['role'],
                }
            })

        main.server.close()
        other.server.close()

    def testBasicRole(self):
        '''
        Basic keep setup for stack keep persistence load and dump with shared role
        '''
        console.terse("{0}\n".format(self.testBasicRole.__doc__))

        opts = self.createOpts(name='main',
                               dirpath=self.tempDirpath,
                               openMode=False,
                               autoAccept=False)
        mainData = self.createRoadData(name='main',
                                       cachedirpath=opts['cachedir'],
                                       role='serious')
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
        self.assertFalse(main.keep.auto)
        self.assertDictEqual(main.keep.loadLocalData(), {'uid': 1,
                                                         'name': mainData['name'],
                                                         'ha': ['0.0.0.0', 7530],
                                                         'main': True,
                                                         'sid': 0,
                                                         'neid': 1,
                                                         'sighex': mainData['sighex'],
                                                         'prihex': mainData['prihex'],
                                                         'auto': False,
                                                         'role': mainData['role'],
                                                         })

        # add multiple remotes all with same role
        data1 = self.createRoadData(name='remote1',
                                    cachedirpath=opts['cachedir'],
                                    role='primary')
        main.addRemote(estating.RemoteEstate(stack=main,
                                             eid=3,
                                             name=data1['name'],
                                             ha=('127.0.0.1', 7532),
                                             verkey=data1['verhex'],
                                             pubkey=data1['pubhex'],
                                             period=main.period,
                                             offset=main.offset,
                                             role=data1['role']) )

        data2 = self.createRoadData(name='remote2',
                                    cachedirpath=opts['cachedir'],
                                    role='primary')
        main.addRemote(estating.RemoteEstate(stack=main,
                                             eid=4,
                                             name=data2['name'],
                                             ha=('127.0.0.1', 7533),
                                             verkey=data2['verhex'],
                                             pubkey=data2['pubhex'],
                                             period=main.period,
                                             offset=main.offset,
                                             role=data2['role']) )

        main.dumpRemotes()

        # will save remote1 keys and reuse for remote2

        self.assertDictEqual(main.keep.loadAllRemoteData(),
            {
                'remote1':
                    {'uid': 3,
                     'name': data1['name'],
                     'ha': ['127.0.0.1', 7532],
                     'sid': 0,
                     'joined': None,
                     'acceptance': 0,
                     'verhex': data1['verhex'],
                     'pubhex': data1['pubhex'],
                     'role': data1['role'],},
                'remote2':
                    {'uid': 4,
                     'name': data2['name'],
                     'ha': ['127.0.0.1', 7533],
                     'sid': 0,
                     'joined': None,
                     'acceptance': 0,
                     'verhex': data1['verhex'],
                     'pubhex': data1['pubhex'],
                     'role': data2['role'],}
            })

        # now recreate with saved data
        main.server.close()
        mainKeep = salting.SaltKeep(opts=opts,
                                     basedirpath=mainData['basedirpath'],
                                     stackname=mainData['name'])
        main = stacking.RoadStack(name=mainData['name'],
                                  store=self.store,
                                  keep=mainKeep)

        self.assertEqual(main.local.name, mainData['name'])
        self.assertEqual(main.local.uid, 1)
        self.assertEqual(main.local.main, True)
        self.assertEqual(main.local.role, mainData['role'])
        self.assertFalse(main.keep.auto)
        self.assertTrue(main.local.ha, ("0.0.0.0", raeting.RAET_PORT))
        self.assertEqual(main.local.priver.keyhex, mainData['prihex'])
        self.assertEqual(main.local.signer.keyhex, mainData['sighex'])

        self.assertEqual(len(main.remotes.values()), 2)
        for data in [data1, data2]:
            remote = main.nameRemotes[data['name']]
            self.assertEqual(remote.name, data['name'])
            self.assertEqual(remote.role, data['role'])
            self.assertEqual(remote.pubber.keyhex, data1['pubhex'])
            self.assertEqual(remote.verfer.keyhex, data1['verhex'])

        main.server.close()

    def testBasicRoleOpen(self):
        '''
        Basic keep setup for stack keep persistence load and dump with shared role
        '''
        console.terse("{0}\n".format(self.testBasicRoleOpen.__doc__))

        opts = self.createOpts(name='main',
                               dirpath=self.tempDirpath,
                               openMode=True,
                               autoAccept=True)
        mainData = self.createRoadData(name='main',
                                       cachedirpath=opts['cachedir'],
                                       role='serious')
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
                                                         'name': mainData['name'],
                                                         'ha': ['0.0.0.0', 7530],
                                                         'main': True,
                                                         'sid': 0,
                                                         'neid': 1,
                                                         'sighex': mainData['sighex'],
                                                         'prihex': mainData['prihex'],
                                                         'auto': True,
                                                         'role': mainData['role'],
                                                         })

        # add multiple remotes all with same role
        data1 = self.createRoadData(name='remote1',
                                    cachedirpath=opts['cachedir'],
                                    role='primary')
        main.addRemote(estating.RemoteEstate(stack=main,
                                             eid=3,
                                             name=data1['name'],
                                             ha=('127.0.0.1', 7532),
                                             verkey=data1['verhex'],
                                             pubkey=data1['pubhex'],
                                             period=main.period,
                                             offset=main.offset,
                                             role=data1['role']) )

        data2 = self.createRoadData(name='remote2',
                                    cachedirpath=opts['cachedir'],
                                    role='primary')
        main.addRemote(estating.RemoteEstate(stack=main,
                                             eid=4,
                                             name=data2['name'],
                                             ha=('127.0.0.1', 7533),
                                             verkey=data2['verhex'],
                                             pubkey=data2['pubhex'],
                                             period=main.period,
                                             offset=main.offset,
                                             role=data2['role']) )

        main.dumpRemotes()

        self.assertDictEqual(main.keep.loadAllRemoteData(),
            {
                'remote1':
                    {'uid': 3,
                     'name': data1['name'],
                     'ha': ['127.0.0.1', 7532],
                     'sid': 0,
                     'joined': None,
                     'acceptance': 1,
                     'verhex': data2['verhex'],
                     'pubhex': data2['pubhex'],
                     'role': data1['role'],},
                'remote2':
                    {'uid': 4,
                     'name': data2['name'],
                     'ha': ['127.0.0.1', 7533],
                     'sid': 0,
                     'joined': None,
                     'acceptance': 1,
                     'verhex': data2['verhex'],
                     'pubhex': data2['pubhex'],
                     'role': data2['role'],}
            })

        # now recreate with saved data
        main.server.close()
        mainKeep = salting.SaltKeep(opts=opts,
                                     basedirpath=mainData['basedirpath'],
                                     stackname=mainData['name'])
        main = stacking.RoadStack(name=mainData['name'],
                                  store=self.store,
                                  keep=mainKeep)

        self.assertEqual(main.local.name, mainData['name'])
        self.assertEqual(main.local.uid, 1)
        self.assertEqual(main.local.main, True)
        self.assertEqual(main.local.role, mainData['role'])
        self.assertTrue(main.keep.auto)
        self.assertTrue(main.local.ha, ("0.0.0.0", raeting.RAET_PORT))
        self.assertEqual(main.local.priver.keyhex, mainData['prihex'])
        self.assertEqual(main.local.signer.keyhex, mainData['sighex'])

        self.assertEqual(len(main.remotes.values()), 2)
        for data in [data1, data2]:
            remote = main.nameRemotes[data['name']]
            self.assertEqual(remote.name, data['name'])
            self.assertEqual(remote.role, data['role'])
            self.assertEqual(remote.pubber.keyhex, data2['pubhex'])
            self.assertEqual(remote.verfer.keyhex, data2['verhex'])

        main.server.close()

    def testBasicRoleAuto(self):
        '''
        Basic keep setup for stack keep persistence load and dump with shared role
        '''
        console.terse("{0}\n".format(self.testBasicRoleAuto.__doc__))
        self.maxDiff = None

        opts = self.createOpts(name='main',
                               dirpath=self.tempDirpath,
                               openMode=False,
                               autoAccept=True)
        mainData = self.createRoadData(name='main',
                                       cachedirpath=opts['cachedir'],
                                       role='serious')
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
                                                         'name': mainData['name'],
                                                         'ha': ['0.0.0.0', 7530],
                                                         'main': True,
                                                         'sid': 0,
                                                         'neid': 1,
                                                         'sighex': mainData['sighex'],
                                                         'prihex': mainData['prihex'],
                                                         'auto': True,
                                                         'role': mainData['role'],
                                                         })

        # add multiple remotes all with same role
        data1 = self.createRoadData(name='remote1',
                                    cachedirpath=opts['cachedir'],
                                    role='primary')
        main.addRemote(estating.RemoteEstate(stack=main,
                                             eid=3,
                                             name=data1['name'],
                                             ha=('127.0.0.1', 7532),
                                             verkey=data1['verhex'],
                                             pubkey=data1['pubhex'],
                                             period=main.period,
                                             offset=main.offset,
                                             role=data1['role']) )

        data2 = self.createRoadData(name='remote2',
                                    cachedirpath=opts['cachedir'],
                                    role='primary')
        main.addRemote(estating.RemoteEstate(stack=main,
                                             eid=4,
                                             name=data2['name'],
                                             ha=('127.0.0.1', 7533),
                                             verkey=data2['verhex'],
                                             pubkey=data2['pubhex'],
                                             period=main.period,
                                             offset=main.offset,
                                             role=data2['role']) )

        main.dumpRemotes()

        # remote2 keys will be rejected since keys do not match remote1 but same role
        # upon reloading the keys for remote2 will be those from remote1

        self.assertDictEqual(main.keep.loadAllRemoteData(),
            {
                'remote1':
                    {'uid': 3,
                     'name': data1['name'],
                     'ha': ['127.0.0.1', 7532],
                     'sid': 0,
                     'joined': None,
                     'acceptance': 1,
                     'verhex': data1['verhex'],
                     'pubhex': data1['pubhex'],
                     'role': data1['role'],},
                'remote2':
                    {'uid': 4,
                     'name': data2['name'],
                     'ha': ['127.0.0.1', 7533],
                     'sid': 0,
                     'joined': None,
                     'acceptance': 1,
                     'verhex': data1['verhex'],
                     'pubhex': data1['pubhex'],
                     'role': data2['role'],}
            })

        # now recreate with saved data
        main.server.close()
        mainKeep = salting.SaltKeep(opts=opts,
                                     basedirpath=mainData['basedirpath'],
                                     stackname=mainData['name'])
        main = stacking.RoadStack(name=mainData['name'],
                                  store=self.store,
                                  keep=mainKeep)

        self.assertEqual(main.local.name, mainData['name'])
        self.assertEqual(main.local.uid, 1)
        self.assertEqual(main.local.main, True)
        self.assertEqual(main.local.role, mainData['role'])
        self.assertTrue(main.keep.auto)
        self.assertTrue(main.local.ha, ("0.0.0.0", raeting.RAET_PORT))
        self.assertEqual(main.local.priver.keyhex, mainData['prihex'])
        self.assertEqual(main.local.signer.keyhex, mainData['sighex'])

        self.assertEqual(len(main.remotes.values()), 2)
        for data in [data1, data2]:
            remote = main.nameRemotes[data['name']]
            self.assertEqual(remote.name, data['name'])
            self.assertEqual(remote.role, data['role'])
            self.assertEqual(remote.acceptance, 1)
            self.assertEqual(remote.pubber.keyhex, data1['pubhex'])
            self.assertEqual(remote.verfer.keyhex, data1['verhex'])


        main.server.close()

    def testBootstrapClean(self):
        '''
        Bootstap to allowed
        '''
        console.terse("{0}\n".format(self.testBootstrapClean.__doc__))

        opts = self.createOpts(name='main',
                               dirpath=self.tempDirpath,
                               openMode=False,
                               autoAccept=False)
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
        self.assertFalse(main.keep.auto)
        self.assertDictEqual(main.keep.loadLocalData(), {'uid': 1,
                                                         'name': mainData['name'],
                                                         'ha': ['0.0.0.0', 7530],
                                                         'main': True,
                                                         'sid': 0,
                                                         'neid': 1,
                                                         'sighex': mainData['sighex'],
                                                         'prihex': mainData['prihex'],
                                                         'auto': False,
                                                         'role': mainData['role'],
                                                         })

        opts = self.createOpts(name='other',
                               dirpath=self.tempDirpath,
                               openMode=False,
                               autoAccept=False)
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
        self.assertFalse(other.keep.auto)
        self.assertDictEqual(other.keep.loadLocalData(),
                            {
                                'uid': 0,
                                'name': otherData['name'],
                                'ha': ['0.0.0.0', 7531],
                                'main': None,
                                'sid': 0,
                                'neid': 1,
                                'sighex': otherData['sighex'],
                                'prihex': otherData['prihex'],
                                'auto': False,
                                'role': otherData['role'],
                            })

        self.join(other, main)
        self.assertEqual(len(main.transactions), 1) # pending
        main.keep.acceptRemote(main.nameRemotes[other.local.name])
        self.service(main, other, duration=1.0)

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

        for remote in main.remotes.values():
            path = os.path.join(main.keep.remotedirpath,
                    "{0}.{1}.{2}".format(main.keep.prefix, remote.name, main.keep.ext))
            self.assertTrue(os.path.exists(path))


        # now delete a key and see if road keep file is also deleted
        main.keep.saltRaetKey.delete_key(match=other.local.role)
        remote = main.remotes[other.local.uid]
        path = os.path.join(main.keep.remotedirpath,
                "{0}.{1}.{2}".format(main.keep.prefix, remote.name, main.keep.ext))
        self.assertFalse(os.path.exists(path))

        main.server.close()
        other.server.close()

    def testBootstrapOpen(self):
        '''
        Bootstap to allowed
        '''
        console.terse("{0}\n".format(self.testBootstrapOpen.__doc__))

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
                                                         'name': mainData['name'],
                                                         'ha': ['0.0.0.0', 7530],
                                                         'main': True,
                                                         'sid': 0,
                                                         'neid': 1,
                                                         'sighex': mainData['sighex'],
                                                         'prihex': mainData['prihex'],
                                                         'auto': True,
                                                         'role': mainData['role'],
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
        self.assertTrue(other.keep.auto)
        self.assertDictEqual(other.keep.loadLocalData(),
                            {
                                'uid': 0,
                                'name': otherData['name'],
                                'ha': ['0.0.0.0', 7531],
                                'main': None,
                                'sid': 0,
                                'neid': 1,
                                'sighex': otherData['sighex'],
                                'prihex': otherData['prihex'],
                                'auto': True,
                                'role': otherData['role'],
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

        for remote in main.remotes.values():
            path = os.path.join(main.keep.remotedirpath,
                    "{0}.{1}.{2}".format(main.keep.prefix, remote.name, main.keep.ext))
            self.assertTrue(os.path.exists(path))


        # now delete a key and see if road keep file is also deleted
        main.keep.saltRaetKey.delete_key(match=other.local.role)
        remote = main.remotes[other.local.uid]
        path = os.path.join(main.keep.remotedirpath,
                "{0}.{1}.{2}".format(main.keep.prefix, remote.name, main.keep.ext))
        self.assertFalse(os.path.exists(path))

        main.server.close()
        other.server.close()

    def testBootstrapAuto(self):
        '''
        Bootstap to allowed
        '''
        console.terse("{0}\n".format(self.testBootstrapAuto.__doc__))

        opts = self.createOpts(name='main',
                               dirpath=self.tempDirpath,
                               openMode=False,
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
                                                         'name': mainData['name'],
                                                         'ha': ['0.0.0.0', 7530],
                                                         'main': True,
                                                         'sid': 0,
                                                         'neid': 1,
                                                         'sighex': mainData['sighex'],
                                                         'prihex': mainData['prihex'],
                                                         'auto': True,
                                                         'role': mainData['role'],
                                                         })

        opts = self.createOpts(name='other',
                               dirpath=self.tempDirpath,
                               openMode=False,
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
                                'name': otherData['name'],
                                'ha': ['0.0.0.0', 7531],
                                'main': None,
                                'sid': 0,
                                'neid': 1,
                                'sighex': otherData['sighex'],
                                'prihex': otherData['prihex'],
                                'auto': True,
                                'role': otherData['role'],
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

        for remote in main.remotes.values():
            path = os.path.join(main.keep.remotedirpath,
                    "{0}.{1}.{2}".format(main.keep.prefix, remote.name, main.keep.ext))
            self.assertTrue(os.path.exists(path))


        # now delete a key and see if road keep file is also deleted
        main.keep.saltRaetKey.delete_key(match=other.local.role)
        remote = main.remotes[other.local.uid]
        path = os.path.join(main.keep.remotedirpath,
                "{0}.{1}.{2}".format(main.keep.prefix, remote.name, main.keep.ext))
        self.assertFalse(os.path.exists(path))

        main.server.close()
        other.server.close()

    def testBootstrapRole(self):
        '''
        Bootstap to allowed with multiple remotes using same role
        '''
        console.terse("{0}\n".format(self.testBootstrapRole.__doc__))

        opts = self.createOpts(name='main',
                               dirpath=self.tempDirpath,
                               openMode=False,
                               autoAccept=False)
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
        self.assertFalse(main.keep.auto)
        self.assertDictEqual(main.keep.loadLocalData(), {'uid': 1,
                                                         'name': mainData['name'],
                                                         'ha': ['0.0.0.0', 7530],
                                                         'main': True,
                                                         'sid': 0,
                                                         'neid': 1,
                                                         'sighex': mainData['sighex'],
                                                         'prihex': mainData['prihex'],
                                                         'auto': False,
                                                         'role': mainData['role'],
                                                         })

        opts = self.createOpts(name='other1',
                               dirpath=self.tempDirpath,
                               openMode=False,
                               autoAccept=False)
        other1Data = self.createRoadData(name='other1',
                                         cachedirpath=opts['cachedir'],
                                         role='primary')
        other1Keep = salting.SaltKeep(opts=opts,
                                      basedirpath=other1Data['basedirpath'],
                                      stackname=other1Data['name'])

        self.assertEqual(other1Keep.loadLocalData(), None)
        self.assertEqual(other1Keep.loadAllRemoteData(), {})

        other1 = self.createRoadStack(data=other1Data,
                                     eid=0,
                                     main=None,
                                     ha=("", raeting.RAET_TEST_PORT),
                                     keep=other1Keep)

        console.terse("{0} keep dirpath = {1}\n".format(
                other1.name, other1.keep.dirpath))
        self.assertTrue(other1.keep.dirpath.endswith('other1/raet/other1'))
        self.assertEqual(other1.local.ha, ("0.0.0.0", raeting.RAET_TEST_PORT))
        self.assertFalse(other1.keep.auto)
        self.assertDictEqual(other1.keep.loadLocalData(),
                            {
                                'uid': 0,
                                'name': other1Data['name'],
                                'ha': ['0.0.0.0', 7531],
                                'main': None,
                                'sid': 0,
                                'neid': 1,
                                'sighex': other1Data['sighex'],
                                'prihex': other1Data['prihex'],
                                'auto': False,
                                'role': other1Data['role'],
                            })

        self.join(other1, main)
        self.assertEqual(len(main.transactions), 1) # pending
        main.keep.acceptRemote(main.nameRemotes[other1.local.name])
        self.service(main, other1, duration=1.0)

        self.assertEqual(len(main.transactions), 0)
        remote = main.remotes.values()[0]
        self.assertTrue(remote.joined)
        self.assertEqual(len(other1.transactions), 0)
        remote = other1.remotes.values()[0]
        self.assertTrue(remote.joined)

        self.allow(other1, main)
        self.assertEqual(len(main.transactions), 0)
        remote = main.remotes.values()[0]
        self.assertTrue(remote.allowed)
        self.assertEqual(len(other1.transactions), 0)
        remote = other1.remotes.values()[0]
        self.assertTrue(remote.allowed)

        for remote in main.remotes.values():
            path = os.path.join(main.keep.remotedirpath,
                    "{0}.{1}.{2}".format(main.keep.prefix, remote.name, main.keep.ext))
            self.assertTrue(os.path.exists(path))

        # create other2 stack but use same role but different keys as other1
        opts = self.createOpts(name='other2',
                               dirpath=self.tempDirpath,
                               openMode=False,
                               autoAccept=False)
        other2Data = self.createRoadData(name='other2',
                                         cachedirpath=opts['cachedir'],
                                         role='primary')
        other2Keep = salting.SaltKeep(opts=opts,
                                      basedirpath=other2Data['basedirpath'],
                                      stackname=other2Data['name'])

        self.assertEqual(other2Keep.loadLocalData(), None)
        self.assertEqual(other2Keep.loadAllRemoteData(), {})

        other2 = self.createRoadStack(data=other2Data,
                                     eid=0,
                                     main=None,
                                     ha=("", 7532),
                                     keep=other2Keep)

        console.terse("{0} keep dirpath = {1}\n".format(
                other2.name, other2.keep.dirpath))
        self.assertTrue(other2.keep.dirpath.endswith('other2/raet/other2'))
        self.assertEqual(other2.local.ha, ("0.0.0.0", 7532))
        self.assertFalse(other2.keep.auto)
        self.assertDictEqual(other2.keep.loadLocalData(),
                            {
                                'uid': 0,
                                'name': other2Data['name'],
                                'ha': ['0.0.0.0', 7532],
                                'main': None,
                                'sid': 0,
                                'neid': 1,
                                'sighex': other2Data['sighex'],
                                'prihex': other2Data['prihex'],
                                'auto': False,
                                'role': other2Data['role'],
                            })

        # should not join since role same but keys different
        self.join(other2, main)
        self.assertEqual(len(main.transactions), 0) # rejected since not same keys
        self.assertEqual(other2.remotes.values()[0].joined, False)
        self.assertEqual(len(main.remotes), 2)
        main.removeRemote(main.nameRemotes[other2.local.name], clear=True)
        other2.server.close()
        other2.keep.clearAllDir()
        path = os.path.join(main.keep.remotedirpath,
                                "{0}.{1}.{2}".format(main.keep.prefix, other2.local.name, main.keep.ext))
        self.assertFalse(os.path.exists(path))
        shutil.rmtree(opts['pki_dir'])



        # recreate other2 stack but use same role and same keys as other1
        opts = self.createOpts(name='other2',
                               dirpath=self.tempDirpath,
                               openMode=False,
                               autoAccept=False)
        other2Data = self.createRoadData(name='other2',
                                         cachedirpath=opts['cachedir'],
                                         role='primary')
        other2Data['sighex'] = other1Data['sighex']
        other2Data['prihex'] = other1Data['prihex']
        other2Keep = salting.SaltKeep(opts=opts,
                                      basedirpath=other2Data['basedirpath'],
                                      stackname=other2Data['name'])

        self.assertEqual(other2Keep.loadLocalData(), None)
        self.assertEqual(other2Keep.loadAllRemoteData(), {})

        other2 = self.createRoadStack(data=other2Data,
                                     eid=0,
                                     main=None,
                                     ha=("", 7532),
                                     keep=other2Keep)

        console.terse("{0} keep dirpath = {1}\n".format(
                other2.name, other2.keep.dirpath))
        self.assertTrue(other2.keep.dirpath.endswith('other2/raet/other2'))
        self.assertEqual(other2.local.ha, ("0.0.0.0", 7532))
        self.assertFalse(other2.keep.auto)
        self.assertDictEqual(other2.keep.loadLocalData(),
                            {
                                'uid': 0,
                                'name': other2Data['name'],
                                'ha': ['0.0.0.0', 7532],
                                'main': None,
                                'sid': 0,
                                'neid': 1,
                                'sighex': other1Data['sighex'],
                                'prihex': other1Data['prihex'],
                                'auto': False,
                                'role': other2Data['role'],
                            })

        # should join since same role and keys
        self.join(other2, main)

        self.assertEqual(len(main.transactions), 0)
        remote = main.remotes.values()[0]
        self.assertTrue(remote.joined)
        self.assertEqual(len(other2.transactions), 0)
        remote = other2.remotes.values()[0]
        self.assertTrue(remote.joined)

        self.allow(other2, main)
        self.assertEqual(len(main.transactions), 0)
        remote = main.remotes.values()[0]
        self.assertTrue(remote.allowed)
        self.assertEqual(len(other2.transactions), 0)
        remote = other2.remotes.values()[0]
        self.assertTrue(remote.allowed)

        for remote in main.remotes.values():
            path = os.path.join(main.keep.remotedirpath,
                    "{0}.{1}.{2}".format(main.keep.prefix, remote.name, main.keep.ext))
            self.assertTrue(os.path.exists(path))


        # now delete a key and see if both road keep file are also deleted
        main.keep.saltRaetKey.delete_key(match=other1.local.role)
        remote = main.remotes[other1.local.uid]
        path = os.path.join(main.keep.remotedirpath,
                "{0}.{1}.{2}".format(main.keep.prefix, remote.name, main.keep.ext))
        self.assertFalse(os.path.exists(path))
        remote = main.remotes[other2.local.uid]
        path = os.path.join(main.keep.remotedirpath,
                        "{0}.{1}.{2}".format(main.keep.prefix, remote.name, main.keep.ext))
        self.assertFalse(os.path.exists(path))

        main.server.close()
        other1.server.close()
        other2.server.close()

    def testBootstrapRoleAuto(self):
        '''
        Bootstap to allowed with multiple remotes using same role
        '''
        console.terse("{0}\n".format(self.testBootstrapRoleAuto.__doc__))

        opts = self.createOpts(name='main',
                               dirpath=self.tempDirpath,
                               openMode=False,
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
                                                         'name': mainData['name'],
                                                         'ha': ['0.0.0.0', 7530],
                                                         'main': True,
                                                         'sid': 0,
                                                         'neid': 1,
                                                         'sighex': mainData['sighex'],
                                                         'prihex': mainData['prihex'],
                                                         'auto': True,
                                                         'role': mainData['role'],
                                                         })

        opts = self.createOpts(name='other1',
                               dirpath=self.tempDirpath,
                               openMode=False,
                               autoAccept=True)
        other1Data = self.createRoadData(name='other1',
                                         cachedirpath=opts['cachedir'],
                                         role='primary')
        other1Keep = salting.SaltKeep(opts=opts,
                                      basedirpath=other1Data['basedirpath'],
                                      stackname=other1Data['name'])

        self.assertEqual(other1Keep.loadLocalData(), None)
        self.assertEqual(other1Keep.loadAllRemoteData(), {})

        other1 = self.createRoadStack(data=other1Data,
                                     eid=0,
                                     main=None,
                                     ha=("", raeting.RAET_TEST_PORT),
                                     keep=other1Keep)

        console.terse("{0} keep dirpath = {1}\n".format(
                other1.name, other1.keep.dirpath))
        self.assertTrue(other1.keep.dirpath.endswith('other1/raet/other1'))
        self.assertEqual(other1.local.ha, ("0.0.0.0", raeting.RAET_TEST_PORT))
        self.assertTrue(other1.keep.auto)
        self.assertDictEqual(other1.keep.loadLocalData(),
                            {
                                'uid': 0,
                                'name': other1Data['name'],
                                'ha': ['0.0.0.0', 7531],
                                'main': None,
                                'sid': 0,
                                'neid': 1,
                                'sighex': other1Data['sighex'],
                                'prihex': other1Data['prihex'],
                                'auto': True,
                                'role': other1Data['role'],
                            })

        self.join(other1, main)
        self.assertEqual(len(main.transactions), 0)
        remote = main.remotes.values()[0]
        self.assertTrue(remote.joined)
        self.assertEqual(len(other1.transactions), 0)
        remote = other1.remotes.values()[0]
        self.assertTrue(remote.joined)

        self.allow(other1, main)
        self.assertEqual(len(main.transactions), 0)
        remote = main.remotes.values()[0]
        self.assertTrue(remote.allowed)
        self.assertEqual(len(other1.transactions), 0)
        remote = other1.remotes.values()[0]
        self.assertTrue(remote.allowed)

        for remote in main.remotes.values():
            path = os.path.join(main.keep.remotedirpath,
                    "{0}.{1}.{2}".format(main.keep.prefix, remote.name, main.keep.ext))
            self.assertTrue(os.path.exists(path))

        # create other2 stack but use same role and different keys as other1
        opts = self.createOpts(name='other2',
                               dirpath=self.tempDirpath,
                               openMode=False,
                               autoAccept=False)
        other2Data = self.createRoadData(name='other2',
                                         cachedirpath=opts['cachedir'],
                                         role='primary')
        other2Data['sighex'] = other1Data['sighex']
        other2Data['prihex'] = other1Data['prihex']

        other2Keep = salting.SaltKeep(opts=opts,
                                      basedirpath=other2Data['basedirpath'],
                                      stackname=other2Data['name'])

        self.assertEqual(other2Keep.loadLocalData(), None)
        self.assertEqual(other2Keep.loadAllRemoteData(), {})

        other2 = self.createRoadStack(data=other2Data,
                                     eid=0,
                                     main=None,
                                     ha=("", 7532),
                                     keep=other2Keep)

        console.terse("{0} keep dirpath = {1}\n".format(
                other2.name, other2.keep.dirpath))
        self.assertTrue(other2.keep.dirpath.endswith('other2/raet/other2'))
        self.assertEqual(other2.local.ha, ("0.0.0.0", 7532))
        self.assertFalse(other2.keep.auto)
        self.assertDictEqual(other2.keep.loadLocalData(),
                            {
                                'uid': 0,
                                'name': other2Data['name'],
                                'ha': ['0.0.0.0', 7532],
                                'main': None,
                                'sid': 0,
                                'neid': 1,
                                'sighex': other2Data['sighex'],
                                'prihex': other2Data['prihex'],
                                'auto': False,
                                'role': other2Data['role'],
                            })

        # should join since same role and keys
        self.join(other2, main)

        self.assertEqual(len(main.transactions), 0)
        remote = main.remotes.values()[0]
        self.assertTrue(remote.joined)
        self.assertEqual(len(other2.transactions), 0)
        remote = other2.remotes.values()[0]
        self.assertTrue(remote.joined)

        self.allow(other2, main)
        self.assertEqual(len(main.transactions), 0)
        remote = main.remotes.values()[0]
        self.assertTrue(remote.allowed)
        self.assertEqual(len(other2.transactions), 0)
        remote = other2.remotes.values()[0]
        self.assertTrue(remote.allowed)

        for remote in main.remotes.values():
            path = os.path.join(main.keep.remotedirpath,
                    "{0}.{1}.{2}".format(main.keep.prefix, remote.name, main.keep.ext))
            self.assertTrue(os.path.exists(path))


        # now delete a key and see if both road keep file are also deleted
        main.keep.saltRaetKey.delete_key(match=other1.local.role)
        remote = main.remotes[other1.local.uid]
        path = os.path.join(main.keep.remotedirpath,
                "{0}.{1}.{2}".format(main.keep.prefix, remote.name, main.keep.ext))
        self.assertFalse(os.path.exists(path))
        remote = main.remotes[other2.local.uid]
        path = os.path.join(main.keep.remotedirpath,
                        "{0}.{1}.{2}".format(main.keep.prefix, remote.name, main.keep.ext))
        self.assertFalse(os.path.exists(path))

        main.server.close()
        other1.server.close()
        other2.server.close()

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
             'testBasicOpen',
             'testBasicAuto',
             'testBasicRole',
             'testBasicRoleOpen',
             'testBasicRoleAuto',
             'testBootstrapClean',
             'testBootstrapOpen',
             'testBootstrapAuto',
             'testBootstrapRole',
             'testBootstrapRoleAuto',
             ]

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

    #runOne('testBootstrapRoleAuto')
