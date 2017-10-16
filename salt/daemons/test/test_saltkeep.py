# -*- coding: utf-8 -*-
'''
Tests to try out salt key.RaetKey Potentially ephemeral

'''

from __future__ import print_function

from __future__ import absolute_import
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

from ioflo.aid.odicting import odict
from ioflo.aid.timing import Timer, StoreTimer
from ioflo.base import storing
from ioflo.base.consoling import getConsole
console = getConsole()

from raet import raeting, nacling
from raet.road import estating, keeping, stacking

from salt.key import RaetKey
from salt.daemons import salting
from salt import daemons
from salt.utils import kinds

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

    def createOpts(self,
                   role,
                   kind=kinds.APPL_KIND_NAMES[kinds.applKinds.master],
                   dirpath='/tmp',
                   openMode=False,
                   autoAccept=True):
        '''
        Create associated pki directories for stack and return opts

        os.path.join(cache, 'raet', name, 'remote')
        '''
        pkiDirpath = os.path.join(dirpath, 'pki', role, 'raet')
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
            os.chmod(localFilepath, mode | stat.S_IWUSR | stat.S_IWUSR)

        cacheDirpath = os.path.join(dirpath, 'cache', role)
        sockDirpath = os.path.join(dirpath, 'sock', role)

        opts = dict(
                     id=role,
                     pki_dir=pkiDirpath,
                     sock_dir=sockDirpath,
                     cachedir=cacheDirpath,
                     open_mode=openMode,
                     auto_accept=autoAccept,
                     transport='raet',
                     __role=kind,
                     )
        return opts

    def createRoadData(self, role, kind=kinds.APPL_KIND_NAMES[kinds.applKinds.master],  cachedirpath=''):
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
        data['name'] = "{0}_{1}".format(role, kind )
        data['role'] = role
        data['kind'] = kinds.APPL_KINDS[kind] # convert to integer from kind name
        data['basedirpath'] = os.path.join(cachedirpath, 'raet')
        signer = nacling.Signer()
        data['sighex'] = signer.keyhex
        data['verhex'] = signer.verhex
        privateer = nacling.Privateer()
        data['prihex'] = privateer.keyhex
        data['pubhex'] = privateer.pubhex


        return data

    def createRoadStack(self, data, keep,  uid=None, main=None, ha=None, mutable=None):
        '''
        Creates stack and local estate from data with
        local estate.uid = uid
        stack.main = main
        stack.mutable = mutable
        stack.auto = auto
        stack.name = data['name']
        local estate.name = data['name']
        local estate.ha = ha

        returns stack

        '''

        stack = stacking.RoadStack(store=self.store,
                                   name=data['name'],
                                   keep=keep,
                                   uid=uid,
                                   ha=ha,
                                   main=main,
                                   mutable=mutable,
                                   role=data['role'],
                                   kind=data['kind'],
                                   sigkey=data['sighex'],
                                   prikey=data['prihex'],)

        return stack

    def join(self, initiator, correspondent, deid=None, duration=1.0):
        '''
        Utility method to do join. Call from test method.
        '''
        console.terse("\nJoin Transaction **************\n")
        if not initiator.remotes:
            remote = initiator.addRemote(estating.RemoteEstate(stack=initiator,
                                                      fuid=0, # vacuous join
                                                      sid=0, # always 0 for join
                                                      ha=correspondent.local.ha))
            deid = remote.uid
        initiator.join(uid=deid)
        self.service(correspondent, initiator, duration=duration)

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
            self.store.advanceStamp(0.05)
            time.sleep(0.05)

    def testBasic(self):
        '''
        Basic keep setup for stack keep persistence load and dump in normal mode
        '''
        console.terse("{0}\n".format(self.testBasic.__doc__))

        opts = self.createOpts(role='main',
                               kind=kinds.APPL_KIND_NAMES[kinds.applKinds.master],
                               dirpath=self.tempDirpath,
                               openMode=False,
                               autoAccept=False)
        mainData = self.createRoadData(cachedirpath=opts['cachedir'],
                                       role=opts['id'],
                                       kind=opts['__role'] )
        mainKeep = salting.SaltKeep(opts=opts,
                                    basedirpath=mainData['basedirpath'],
                                    stackname=mainData['name'])

        self.assertEqual(mainKeep.loadLocalData(), None)
        self.assertEqual(mainKeep.loadAllRemoteData(), {})

        main = self.createRoadStack(data=mainData,
                                     main=True,
                                     ha=None, #default ha is ("", raeting.RAET_PORT)
                                     keep=mainKeep)

        console.terse("{0}\nkeep dirpath = {1}\n".format(
                main.name, main.keep.dirpath))
        self.assertTrue(main.keep.dirpath.endswith(
                os.path.join('main', 'raet', 'main_master')))
        self.assertTrue(main.ha, ("0.0.0.0", raeting.RAET_PORT))
        self.assertIs(main.keep.auto, raeting.AutoMode.never.value)
        self.assertDictEqual(main.keep.loadLocalData(), {'name': mainData['name'],
                                                         'uid': 1,
                                                         'ha': ['127.0.0.1', 7530],
                                                         'iha': None,
                                                         'natted': None,
                                                         'fqdn': '1.0.0.127.in-addr.arpa',
                                                         'dyned': None,
                                                         'sid': 0,
                                                         'puid': 1,
                                                         'aha': ['0.0.0.0', 7530],
                                                         'role': mainData['role'],
                                                         'sighex': mainData['sighex'],
                                                         'prihex': mainData['prihex'],
                                                         })

        data1 = self.createRoadData(role='remote1',
                                    kind=kinds.APPL_KIND_NAMES[kinds.applKinds.minion],
                                    cachedirpath=opts['cachedir'])
        main.addRemote(estating.RemoteEstate(stack=main,
                                             name=data1['name'],
                                             kind=data1['kind'],
                                             ha=('127.0.0.1', 7532),
                                             role=data1['role'],
                                             verkey=data1['verhex'],
                                             pubkey=data1['pubhex'],))

        data2 = self.createRoadData(role='remote2',
                                    kind=kinds.APPL_KIND_NAMES[kinds.applKinds.minion],
                                    cachedirpath=opts['cachedir'])
        main.addRemote(estating.RemoteEstate(stack=main,
                                             name=data2['name'],
                                             kind=data2['kind'],
                                             ha=('127.0.0.1', 7533),
                                             role=data2['role'],
                                             verkey=data2['verhex'],
                                             pubkey=data2['pubhex'],))

        main.dumpRemotes()

        # acceptance will be pended

        self.assertDictEqual(main.keep.loadAllRemoteData(),
            {
                'remote1_minion':
                    {'name': data1['name'],
                     'uid': 2,
                     'fuid': 0,
                     'ha': ['127.0.0.1', 7532],
                     'iha': None,
                     'natted': None,
                     'fqdn': '1.0.0.127.in-addr.arpa',
                     'dyned': None,
                     'main': False,
                     'kind': data1['kind'],
                     'sid': 0,
                     'joined': None,
                     'role': data1['role'],
                     'acceptance': 0,
                     'verhex': data1['verhex'],
                     'pubhex': data1['pubhex'],
                     },
                'remote2_minion':
                    {'name': data2['name'],
                     'uid': 3,
                     'fuid': 0,
                     'ha': ['127.0.0.1', 7533],
                     'iha': None,
                     'natted': None,
                     'fqdn': '1.0.0.127.in-addr.arpa',
                     'dyned': None,
                     'main': False,
                     'kind': data2['kind'],
                     'sid': 0,
                     'joined': None,
                     'role': data2['role'],
                     'acceptance': 0,
                     'verhex': data2['verhex'],
                     'pubhex': data2['pubhex'],
                     }
            })

        # now recreate with saved data
        main.server.close()
        mainKeep = salting.SaltKeep(opts=opts,
                                     basedirpath=mainData['basedirpath'],
                                     stackname=mainData['name'])
        main = stacking.RoadStack(name=mainData['name'],
                                  store=self.store,
                                  keep=mainKeep,
                                  main=True)

        self.assertEqual(main.local.priver.keyhex, mainData['prihex'])
        self.assertEqual(main.local.signer.keyhex, mainData['sighex'])

        self.assertEqual(len(main.remotes), 2)

        # other stack
        opts = self.createOpts(role='other',
                               kind=kinds.APPL_KIND_NAMES[kinds.applKinds.minion],
                               dirpath=self.tempDirpath,
                               openMode=False,
                               autoAccept=False)
        otherData = self.createRoadData(role=opts['id'],
                                        kind=opts['__role'],
                                        cachedirpath=opts['cachedir'] )
        otherKeep = salting.SaltKeep(opts=opts,
                                      basedirpath=otherData['basedirpath'],
                                      stackname=otherData['name'])

        self.assertEqual(otherKeep.loadLocalData(), None)
        self.assertEqual(otherKeep.loadAllRemoteData(), {})

        other = self.createRoadStack(data=otherData,
                                     main=None,
                                     ha=("", raeting.RAET_TEST_PORT),
                                     keep=otherKeep)

        console.terse("{0} keep dirpath = {1}\n".format(
                other.name, other.keep.dirpath))
        self.assertTrue(other.keep.dirpath.endswith(os.path.join('other', 'raet', 'other_minion')))
        self.assertEqual(other.ha, ("0.0.0.0", raeting.RAET_TEST_PORT))
        self.assertIs(other.keep.auto, raeting.AutoMode.never.value)

        self.assertDictEqual(other.keep.loadLocalData(),
                            {
                                'name': otherData['name'],
                                'uid': 1,
                                'ha': ['127.0.0.1', 7531],
                                'iha': None,
                                'natted': None,
                                'fqdn': '1.0.0.127.in-addr.arpa',
                                'dyned': None,
                                'sid': 0,
                                'puid': 1,
                                'aha': ['0.0.0.0', 7531],
                                'role': otherData['role'],
                                'sighex': otherData['sighex'],
                                'prihex': otherData['prihex'],
                            })

        data3 = self.createRoadData(role='remote3',
                                    kind=kinds.APPL_KIND_NAMES[kinds.applKinds.minion],
                                    cachedirpath=opts['cachedir'])
        other.addRemote(estating.RemoteEstate(stack=other,
                                              name=data3['name'],
                                              kind=data3['kind'],
                                              ha=('127.0.0.1', 7534),
                                              role=data3['role'],
                                              verkey=data3['verhex'],
                                              pubkey=data3['pubhex'],))

        data4 = self.createRoadData(role='remote4',
                                    kind=kinds.APPL_KIND_NAMES[kinds.applKinds.minion],
                                    cachedirpath=opts['cachedir'])
        other.addRemote(estating.RemoteEstate(stack=other,
                                              name=data4['name'],
                                              kind=data4['kind'],
                                              ha=('127.0.0.1', 7535),
                                              role=data4['role'],
                                              verkey=data4['verhex'],
                                              pubkey=data4['pubhex'],))

        other.dumpRemotes()
        self.assertDictEqual(other.keep.loadAllRemoteData(),
            {
                'remote3_minion':
                {
                    'name': data3['name'],
                    'uid': 2,
                    'fuid': 0,
                    'ha': ['127.0.0.1', 7534],
                    'iha': None,
                    'natted': None,
                    'fqdn': '1.0.0.127.in-addr.arpa',
                    'dyned': None,
                    'main': False,
                    'kind': data3['kind'],
                    'sid': 0,
                    'joined': None,
                    'role': data3['role'],
                    'acceptance': 0,
                    'verhex': data3['verhex'],
                    'pubhex': data3['pubhex'],
                },
                'remote4_minion':
                {
                    'name': data4['name'],
                    'uid': 3,
                    'fuid': 0,
                    'ha': ['127.0.0.1', 7535],
                    'iha': None,
                    'natted': None,
                    'fqdn': '1.0.0.127.in-addr.arpa',
                    'dyned': None,
                    'main': False,
                    'kind': data4['kind'],
                    'sid': 0,
                    'joined': None,
                    'role': data4['role'],
                    'acceptance': 0,
                    'verhex': data4['verhex'],
                    'pubhex': data4['pubhex'],
                }
            })

        main.server.close()
        other.server.close()

    def testBasicOpen(self):
        '''
        Basic keep setup for stack keep persistence load and dump in open mode
        '''
        console.terse("{0}\n".format(self.testBasicOpen.__doc__))

        opts = self.createOpts(role='main',
                               kind=kinds.APPL_KIND_NAMES[kinds.applKinds.master],
                               dirpath=self.tempDirpath,
                               openMode=True,
                               autoAccept=True)
        mainData = self.createRoadData(role=opts['id'],
                                       kind=opts['__role'],
                                       cachedirpath=opts['cachedir'])
        mainKeep = salting.SaltKeep(opts=opts,
                                    basedirpath=mainData['basedirpath'],
                                    stackname=mainData['name'])

        self.assertEqual(mainKeep.loadLocalData(), None)
        self.assertEqual(mainKeep.loadAllRemoteData(), {})

        main = self.createRoadStack(data=mainData,
                                     main=True,
                                     ha=None, #default ha is ("", raeting.RAET_PORT)
                                     keep=mainKeep)

        console.terse("{0}\nkeep dirpath = {1}\n".format(
                main.name, main.keep.dirpath))
        self.assertTrue(main.keep.dirpath.endswith(os.path.join('main', 'raet', 'main_master')))
        self.assertTrue(main.ha, ("0.0.0.0", raeting.RAET_PORT))
        self.assertIs(main.keep.auto, raeting.AutoMode.always.value)
        self.assertDictEqual(main.keep.loadLocalData(), {
                                                         'name': mainData['name'],
                                                         'uid': 1,
                                                         'ha': ['127.0.0.1', 7530],
                                                         'iha': None,
                                                         'natted': None,
                                                         'fqdn': '1.0.0.127.in-addr.arpa',
                                                         'dyned': None,
                                                         'sid': 0,
                                                         'puid': 1,
                                                         'aha': ['0.0.0.0', 7530],
                                                         'role': mainData['role'],
                                                         'sighex': mainData['sighex'],
                                                         'prihex': mainData['prihex'],
                                                         })

        data1 = self.createRoadData(role='remote1',
                                    kind=kinds.APPL_KIND_NAMES[kinds.applKinds.minion],
                                    cachedirpath=opts['cachedir'])
        main.addRemote(estating.RemoteEstate(stack=main,
                                             name=data1['name'],
                                             kind=data1['kind'],
                                             ha=('127.0.0.1', 7532),
                                             role=data1['role'],
                                             verkey=data1['verhex'],
                                             pubkey=data1['pubhex'],))

        data2 = self.createRoadData(role='remote2',
                                    kind=kinds.APPL_KIND_NAMES[kinds.applKinds.minion],
                                    cachedirpath=opts['cachedir'])
        main.addRemote(estating.RemoteEstate(stack=main,
                                             name=data2['name'],
                                             kind=data2['kind'],
                                             ha=('127.0.0.1', 7533),
                                             role=data2['role'],
                                             verkey=data2['verhex'],
                                             pubkey=data2['pubhex'],))

        main.dumpRemotes()

        self.assertDictEqual(main.keep.loadAllRemoteData(),
            {
                'remote1_minion':
                    {'name': data1['name'],
                     'uid': 2,
                     'fuid': 0,
                     'ha': ['127.0.0.1', 7532],
                     'iha': None,
                     'natted': None,
                     'fqdn': '1.0.0.127.in-addr.arpa',
                     'dyned': None,
                     'main': False,
                     'kind': data1['kind'],
                     'sid': 0,
                     'joined': None,
                     'role': data1['role'],
                     'acceptance': 1,
                     'verhex': data1['verhex'],
                     'pubhex': data1['pubhex'],
                     },
                'remote2_minion':
                    {'name': data2['name'],
                     'uid': 3,
                     'fuid': 0,
                     'ha': ['127.0.0.1', 7533],
                     'iha': None,
                     'natted': None,
                     'fqdn': '1.0.0.127.in-addr.arpa',
                     'dyned': None,
                     'main': False,
                     'kind': data2['kind'],
                     'sid': 0,
                     'joined': None,
                     'role': data2['role'],
                     'acceptance': 1,
                     'verhex': data2['verhex'],
                     'pubhex': data2['pubhex'],
                     }
            })

        # now recreate with saved data
        main.server.close()
        mainKeep = salting.SaltKeep(opts=opts,
                                     basedirpath=mainData['basedirpath'],
                                     stackname=mainData['name'])
        main = stacking.RoadStack(name=mainData['name'],
                                  store=self.store,
                                  keep=mainKeep,
                                  main=True)

        self.assertEqual(main.local.priver.keyhex, mainData['prihex'])
        self.assertEqual(main.local.signer.keyhex, mainData['sighex'])

        self.assertEqual(len(main.remotes), 2)

        # other stack
        opts = self.createOpts(role='other',
                               kind=kinds.APPL_KIND_NAMES[kinds.applKinds.minion],
                               dirpath=self.tempDirpath,
                               openMode=True,
                               autoAccept=True)
        otherData = self.createRoadData(role='other',
                                        kind=opts['__role'],
                                        cachedirpath=opts['cachedir'] )
        otherKeep = salting.SaltKeep(opts=opts,
                                      basedirpath=otherData['basedirpath'],
                                      stackname=otherData['name'])

        self.assertEqual(otherKeep.loadLocalData(), None)
        self.assertEqual(otherKeep.loadAllRemoteData(), {})

        other = self.createRoadStack(data=otherData,
                                     main=None,
                                     ha=("", raeting.RAET_TEST_PORT),
                                     keep=otherKeep)

        console.terse("{0} keep dirpath = {1}\n".format(
                other.name, other.keep.dirpath))
        self.assertTrue(other.keep.dirpath.endswith(os.path.join('other', 'raet', 'other_minion')))
        self.assertEqual(other.ha, ("0.0.0.0", raeting.RAET_TEST_PORT))
        self.assertIs(other.keep.auto,raeting.AutoMode.always.value)

        self.assertDictEqual(other.keep.loadLocalData(),
                            {
                                'name': otherData['name'],
                                'uid': 1,
                                'ha': ['127.0.0.1', 7531],
                                'iha': None,
                                'natted': None,
                                'fqdn': '1.0.0.127.in-addr.arpa',
                                'dyned': None,
                                'sid': 0,
                                'puid': 1,
                                'aha': ['0.0.0.0', 7531],
                                'role': otherData['role'],
                                'sighex': otherData['sighex'],
                                'prihex': otherData['prihex'],
                            })

        data3 = self.createRoadData(role='remote3',
                                    kind=kinds.APPL_KIND_NAMES[kinds.applKinds.minion],
                                    cachedirpath=opts['cachedir'])
        other.addRemote(estating.RemoteEstate(stack=other,
                                              name=data3['name'],
                                              kind=data3['kind'],
                                              ha=('127.0.0.1', 7534),
                                              role=data3['role'],
                                              verkey=data3['verhex'],
                                              pubkey=data3['pubhex'],))

        data4 = self.createRoadData(role='remote4',
                                    kind=kinds.APPL_KIND_NAMES[kinds.applKinds.minion],
                                    cachedirpath=opts['cachedir'])
        other.addRemote(estating.RemoteEstate(stack=other,
                                              name=data4['name'],
                                              kind=data4['kind'],
                                              ha=('127.0.0.1', 7535),
                                              role=data4['role'],
                                              verkey=data4['verhex'],
                                              pubkey=data4['pubhex'],))

        other.dumpRemotes()
        self.assertDictEqual(other.keep.loadAllRemoteData(),
            {
                'remote3_minion':
                {
                    'name': data3['name'],
                    'uid': 2,
                    'fuid': 0,
                    'ha': ['127.0.0.1', 7534],
                    'iha': None,
                    'natted': None,
                    'fqdn': '1.0.0.127.in-addr.arpa',
                    'dyned': None,
                    'main': False,
                    'kind': data3['kind'],
                    'sid': 0,
                    'joined': None,
                    'role': data3['role'],
                    'acceptance': 1,
                    'verhex': data3['verhex'],
                    'pubhex': data3['pubhex'],
                },
                'remote4_minion':
                {
                    'name': data4['name'],
                    'uid': 3,
                    'fuid': 0,
                    'ha': ['127.0.0.1', 7535],
                    'iha': None,
                    'natted': None,
                    'fqdn': '1.0.0.127.in-addr.arpa',
                    'dyned': None,
                    'main': False,
                    'kind': data4['kind'],
                    'sid': 0,
                    'joined': None,
                    'role': data4['role'],
                    'acceptance': 1,
                    'verhex': data4['verhex'],
                    'pubhex': data4['pubhex'],
                }
            })

        main.server.close()
        other.server.close()

    def testBasicAuto(self):
        '''
        Basic keep setup for stack keep persistence load and dump with auto accept
        '''
        console.terse("{0}\n".format(self.testBasicAuto.__doc__))

        opts = self.createOpts(role='main',
                               kind=kinds.APPL_KIND_NAMES[kinds.applKinds.master],
                               dirpath=self.tempDirpath,
                               openMode=False,
                               autoAccept=True)
        mainData = self.createRoadData(role=opts['id'],
                                       kind=opts['__role'],
                                       cachedirpath=opts['cachedir'] )
        mainKeep = salting.SaltKeep(opts=opts,
                                    basedirpath=mainData['basedirpath'],
                                    stackname=mainData['name'])

        self.assertEqual(mainKeep.loadLocalData(), None)
        self.assertEqual(mainKeep.loadAllRemoteData(), {})

        main = self.createRoadStack(data=mainData,
                                     main=True,
                                     ha=None, #default ha is ("", raeting.RAET_PORT)
                                     keep=mainKeep)

        console.terse("{0}\nkeep dirpath = {1}\n".format(
                main.name, main.keep.dirpath))
        self.assertTrue(main.keep.dirpath.endswith(os.path.join('main', 'raet', 'main_master')))
        self.assertTrue(main.ha, ("0.0.0.0", raeting.RAET_PORT))
        self.assertIs(main.keep.auto,  raeting.AutoMode.once.value)
        self.assertDictEqual(main.keep.loadLocalData(), {
                                                         'name': mainData['name'],
                                                         'uid': 1,
                                                         'ha': ['127.0.0.1', 7530],
                                                         'iha': None,
                                                         'natted': None,
                                                         'fqdn': '1.0.0.127.in-addr.arpa',
                                                         'dyned': None,
                                                         'sid': 0,
                                                         'puid': 1,
                                                         'aha': ['0.0.0.0', 7530],
                                                         'sighex': mainData['sighex'],
                                                         'prihex': mainData['prihex'],
                                                         'role': mainData['role'],
                                                         })

        data1 = self.createRoadData(role='remote1',
                                    kind=kinds.APPL_KIND_NAMES[kinds.applKinds.minion],
                                    cachedirpath=opts['cachedir'])
        main.addRemote(estating.RemoteEstate(stack=main,
                                             name=data1['name'],
                                             kind=data1['kind'],
                                             ha=('127.0.0.1', 7532),
                                             role=data1['role'],
                                             verkey=data1['verhex'],
                                             pubkey=data1['pubhex'],))

        data2 = self.createRoadData(role='remote2',
                                    kind=kinds.APPL_KIND_NAMES[kinds.applKinds.minion],
                                    cachedirpath=opts['cachedir'])
        main.addRemote(estating.RemoteEstate(stack=main,
                                             name=data2['name'],
                                             kind=data2['kind'],
                                             ha=('127.0.0.1', 7533),
                                             role=data2['role'],
                                             verkey=data2['verhex'],
                                             pubkey=data2['pubhex'],))

        main.dumpRemotes()

        self.assertDictEqual(main.keep.loadAllRemoteData(),
            {
                'remote1_minion':
                    {
                     'name': data1['name'],
                     'uid': 2,
                     'fuid': 0,
                     'ha': ['127.0.0.1', 7532],
                     'iha': None,
                     'natted': None,
                     'fqdn': '1.0.0.127.in-addr.arpa',
                     'dyned': None,
                     'main': False,
                     'kind': data1['kind'],
                     'sid': 0,
                     'joined': None,
                     'role': data1['role'],
                     'acceptance': 1,
                     'verhex': data1['verhex'],
                     'pubhex': data1['pubhex'],
                     },
                'remote2_minion':
                    {
                     'name': data2['name'],
                     'uid': 3,
                     'fuid': 0,
                     'ha': ['127.0.0.1', 7533],
                     'iha': None,
                     'natted': None,
                     'fqdn': '1.0.0.127.in-addr.arpa',
                     'dyned': None,
                     'main': False,
                     'kind': data2['kind'],
                     'sid': 0,
                     'joined': None,
                     'role': data2['role'],
                     'acceptance': 1,
                     'verhex': data2['verhex'],
                     'pubhex': data2['pubhex'],
                     }
            })

        # now recreate with saved data
        main.server.close()
        mainKeep = salting.SaltKeep(opts=opts,
                                     basedirpath=mainData['basedirpath'],
                                     stackname=mainData['name'])
        main = stacking.RoadStack(name=mainData['name'],
                                  store=self.store,
                                  keep=mainKeep,
                                  main=True)

        self.assertEqual(main.local.priver.keyhex, mainData['prihex'])
        self.assertEqual(main.local.signer.keyhex, mainData['sighex'])

        self.assertEqual(len(main.remotes), 2)

        # other stack
        opts = self.createOpts(role='other',
                               kind=kinds.APPL_KIND_NAMES[kinds.applKinds.minion],
                               dirpath=self.tempDirpath,
                               openMode=False,
                               autoAccept=True)
        otherData = self.createRoadData(role='other',
                                        kind=kinds.APPL_KIND_NAMES[kinds.applKinds.minion],
                                        cachedirpath=opts['cachedir'] )
        otherKeep = salting.SaltKeep(opts=opts,
                                      basedirpath=otherData['basedirpath'],
                                      stackname=otherData['name'])

        self.assertEqual(otherKeep.loadLocalData(), None)
        self.assertEqual(otherKeep.loadAllRemoteData(), {})

        other = self.createRoadStack(data=otherData,
                                     main=None,
                                     ha=("", raeting.RAET_TEST_PORT),
                                     keep=otherKeep)

        console.terse("{0} keep dirpath = {1}\n".format(
                other.name, other.keep.dirpath))
        self.assertTrue(other.keep.dirpath.endswith(os.path.join('other', 'raet', 'other_minion')))
        self.assertEqual(other.ha, ("0.0.0.0", raeting.RAET_TEST_PORT))
        self.assertIs(other.keep.auto, raeting.AutoMode.once.value)

        self.assertDictEqual(other.keep.loadLocalData(),
                            {
                                'name': otherData['name'],
                                'uid': 1,
                                'ha': ['127.0.0.1', 7531],
                                'iha': None,
                                'natted': None,
                                'fqdn': '1.0.0.127.in-addr.arpa',
                                'dyned': None,
                                'sid': 0,
                                'puid': 1,
                                'aha': ['0.0.0.0', 7531],
                                'role': otherData['role'],
                                'sighex': otherData['sighex'],
                                'prihex': otherData['prihex'],
                            })

        data3 = self.createRoadData(role='remote3',
                                    kind=kinds.APPL_KIND_NAMES[kinds.applKinds.minion],
                                    cachedirpath=opts['cachedir'])
        other.addRemote(estating.RemoteEstate(stack=other,
                                              name=data3['name'],
                                              kind=data3['kind'],
                                              ha=('127.0.0.1', 7534),
                                              role=data3['role'],
                                              verkey=data3['verhex'],
                                              pubkey=data3['pubhex'],))

        data4 = self.createRoadData(role='remote4',
                                    kind=kinds.APPL_KIND_NAMES[kinds.applKinds.minion],
                                    cachedirpath=opts['cachedir'])
        other.addRemote(estating.RemoteEstate(stack=other,
                                              name=data4['name'],
                                              kind=data4['kind'],
                                              ha=('127.0.0.1', 7535),
                                              role=data4['role'],
                                              verkey=data4['verhex'],
                                              pubkey=data4['pubhex'],))

        other.dumpRemotes()
        self.assertDictEqual(other.keep.loadAllRemoteData(),
            {
                'remote3_minion':
                {
                    'name': data3['name'],
                    'uid': 2,
                    'fuid': 0,
                    'ha': ['127.0.0.1', 7534],
                    'iha': None,
                    'natted': None,
                    'fqdn': '1.0.0.127.in-addr.arpa',
                    'dyned': None,
                    'main': False,
                    'kind': data3['kind'],
                    'sid': 0,
                    'joined': None,
                    'role': data3['role'],
                    'acceptance': 1,
                    'verhex': data3['verhex'],
                    'pubhex': data3['pubhex'],
                },
                'remote4_minion':
                {
                    'name': data4['name'],
                    'uid': 3,
                    'fuid': 0,
                    'ha': ['127.0.0.1', 7535],
                    'iha': None,
                    'natted': None,
                    'fqdn': '1.0.0.127.in-addr.arpa',
                    'dyned': None,
                    'main': False,
                    'kind': data4['kind'],
                    'sid': 0,
                    'joined': None,
                    'role': data4['role'],
                    'acceptance': 1,
                    'verhex': data4['verhex'],
                    'pubhex': data4['pubhex'],
                }
            })

        main.server.close()
        other.server.close()

    def testBasicRole(self):
        '''
        Basic keep setup for stack keep persistence load and dump with shared role
        '''
        console.terse("{0}\n".format(self.testBasicRole.__doc__))

        opts = self.createOpts(role='main',
                               kind=kinds.APPL_KIND_NAMES[kinds.applKinds.master],
                               dirpath=self.tempDirpath,
                               openMode=False,
                               autoAccept=False)
        mainData = self.createRoadData(role=opts['id'],
                                       kind=opts['__role'],
                                       cachedirpath=opts['cachedir'],
                                       )
        mainKeep = salting.SaltKeep(opts=opts,
                                    basedirpath=mainData['basedirpath'],
                                    stackname=mainData['name'])

        self.assertEqual(mainKeep.loadLocalData(), None)
        self.assertEqual(mainKeep.loadAllRemoteData(), {})

        main = self.createRoadStack(data=mainData,
                                     main=True,
                                     ha=None, #default ha is ("", raeting.RAET_PORT)
                                     keep=mainKeep)

        console.terse("{0}\nkeep dirpath = {1}\n".format(
                main.name, main.keep.dirpath))
        self.assertTrue(main.keep.dirpath.endswith(os.path.join('main', 'raet', 'main_master')))
        self.assertTrue(main.ha, ("0.0.0.0", raeting.RAET_PORT))
        self.assertIs(main.keep.auto, raeting.AutoMode.never.value)
        self.assertDictEqual(main.keep.loadLocalData(), {'name': mainData['name'],
                                                         'uid': 1,
                                                         'ha': ['127.0.0.1', 7530],
                                                         'iha': None,
                                                         'natted': None,
                                                         'fqdn': '1.0.0.127.in-addr.arpa',
                                                         'dyned': None,
                                                         'sid': 0,
                                                         'puid': 1,
                                                         'aha': ['0.0.0.0', 7530],
                                                         'role': mainData['role'],
                                                         'sighex': mainData['sighex'],
                                                         'prihex': mainData['prihex'],
                                                         })

        # add multiple remotes all with same role
        data1 = self.createRoadData(role='primary',
                                    kind=kinds.APPL_KIND_NAMES[kinds.applKinds.minion],
                                    cachedirpath=opts['cachedir'],
                                    )
        main.addRemote(estating.RemoteEstate(stack=main,
                                             name=data1['name'],
                                             kind=data1['kind'],
                                             ha=('127.0.0.1', 7532),
                                             role=data1['role'],
                                             verkey=data1['verhex'],
                                             pubkey=data1['pubhex'],
                                             ) )

        data2 = self.createRoadData(role='primary',
                                    kind=kinds.APPL_KIND_NAMES[kinds.applKinds.caller],
                                    cachedirpath=opts['cachedir'],
                                    )
        main.addRemote(estating.RemoteEstate(stack=main,
                                             name=data2['name'],
                                             kind=data2['kind'],
                                             ha=('127.0.0.1', 7533),
                                             role=data2['role'],
                                             verkey=data2['verhex'],
                                             pubkey=data2['pubhex'],
                                             ) )

        main.dumpRemotes()

        # will save remote1 keys and reuse for remote2

        self.assertDictEqual(main.keep.loadAllRemoteData(),
            {
                'primary_minion':
                    {
                     'name': data1['name'],
                     'uid': 2,
                     'fuid': 0,
                     'ha': ['127.0.0.1', 7532],
                     'iha': None,
                     'natted': None,
                     'fqdn': '1.0.0.127.in-addr.arpa',
                     'dyned': None,
                     'main': False,
                     'kind': data1['kind'],
                     'sid': 0,
                     'joined': None,
                     'role': data1['role'],
                     'acceptance': 0,
                     'verhex': data1['verhex'],
                     'pubhex': data1['pubhex'],
                     },
                'primary_caller':
                    {
                     'name': data2['name'],
                     'uid': 3,
                     'fuid': 0,
                     'ha': ['127.0.0.1', 7533],
                     'iha': None,
                     'natted': None,
                     'fqdn': '1.0.0.127.in-addr.arpa',
                     'dyned': None,
                     'main': False,
                     'kind': data2['kind'],
                     'sid': 0,
                     'joined': None,
                     'role': data1['role'],
                     'acceptance': 0,
                     'verhex': data1['verhex'],
                     'pubhex': data1['pubhex'],
                     }
            })

        # now recreate with saved data
        main.server.close()
        mainKeep = salting.SaltKeep(opts=opts,
                                     basedirpath=mainData['basedirpath'],
                                     stackname=mainData['name'])
        main = stacking.RoadStack(name=mainData['name'],
                                  store=self.store,
                                  keep=mainKeep,
                                  main=True)

        self.assertEqual(main.local.name, mainData['name'])
        self.assertEqual(main.local.uid, 1)
        self.assertEqual(main.main, True)
        self.assertEqual(main.local.role, mainData['role'])
        self.assertIs(main.keep.auto, raeting.AutoMode.never.value)
        self.assertTrue(main.ha, ("0.0.0.0", raeting.RAET_PORT))
        self.assertEqual(main.local.priver.keyhex, mainData['prihex'])
        self.assertEqual(main.local.signer.keyhex, mainData['sighex'])

        self.assertEqual(len(main.remotes), 2)
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

        opts = self.createOpts(role='main',
                               dirpath=self.tempDirpath,
                               openMode=True,
                               autoAccept=True)
        mainData = self.createRoadData(role=opts['id'],
                                       kind=opts['__role'],
                                       cachedirpath=opts['cachedir'],
)
        mainKeep = salting.SaltKeep(opts=opts,
                                    basedirpath=mainData['basedirpath'],
                                    stackname=mainData['name'])

        self.assertEqual(mainKeep.loadLocalData(), None)
        self.assertEqual(mainKeep.loadAllRemoteData(), {})

        main = self.createRoadStack(data=mainData,
                                     main=True,
                                     ha=None, #default ha is ("", raeting.RAET_PORT)
                                     keep=mainKeep)

        console.terse("{0}\nkeep dirpath = {1}\n".format(
                main.name, main.keep.dirpath))
        self.assertTrue(main.keep.dirpath.endswith(os.path.join('main', 'raet', 'main_master')))
        self.assertTrue(main.ha, ("0.0.0.0", raeting.RAET_PORT))
        self.assertIs(main.keep.auto, raeting.AutoMode.always.value)
        self.assertDictEqual(main.keep.loadLocalData(), {
                                                         'name': mainData['name'],
                                                         'uid': 1,
                                                         'ha': ['127.0.0.1', 7530],
                                                         'iha': None,
                                                         'natted': None,
                                                         'fqdn': '1.0.0.127.in-addr.arpa',
                                                         'dyned': None,
                                                         'sid': 0,
                                                         'puid': 1,
                                                         'aha': ['0.0.0.0', 7530],
                                                         'role': mainData['role'],
                                                         'sighex': mainData['sighex'],
                                                         'prihex': mainData['prihex'],
                                                         })

        # add multiple remotes all with same role
        data1 = self.createRoadData(role='primary',
                                    kind=kinds.APPL_KIND_NAMES[kinds.applKinds.minion],
                                    cachedirpath=opts['cachedir'],)
        main.addRemote(estating.RemoteEstate(stack=main,
                                             name=data1['name'],
                                             kind=data1['kind'],
                                             ha=('127.0.0.1', 7532),
                                             role=data1['role'],
                                             verkey=data1['verhex'],
                                             pubkey=data1['pubhex'],) )

        data2 = self.createRoadData(role='primary',
                                    kind='syndic',
                                    cachedirpath=opts['cachedir'],)
        main.addRemote(estating.RemoteEstate(stack=main,
                                             name=data2['name'],
                                             kind=data2['kind'],
                                             ha=('127.0.0.1', 7533),
                                             role=data2['role'],
                                             verkey=data2['verhex'],
                                             pubkey=data2['pubhex'],) )

        main.dumpRemotes() # second one keys will clobber first one keys

        self.assertDictEqual(main.keep.loadAllRemoteData(),
            {
                'primary_minion':
                    {
                     'name': data1['name'],
                     'uid': 2,
                     'fuid': 0,
                     'ha': ['127.0.0.1', 7532],
                     'iha': None,
                     'natted': None,
                     'fqdn': '1.0.0.127.in-addr.arpa',
                     'dyned': None,
                     'main': False,
                     'kind': data1['kind'],
                     'sid': 0,
                     'joined': None,
                     'role': data1['role'],
                     'acceptance': 1,
                     'verhex': data2['verhex'],
                     'pubhex': data2['pubhex'],
                     },
                'primary_syndic':
                    {
                     'name': data2['name'],
                     'uid': 3,
                     'fuid': 0,
                     'ha': ['127.0.0.1', 7533],
                     'iha': None,
                     'natted': None,
                     'fqdn': '1.0.0.127.in-addr.arpa',
                     'dyned': None,
                     'main': False,
                     'kind': data2['kind'],
                     'sid': 0,
                     'joined': None,
                     'role': data2['role'],
                     'acceptance': 1,
                     'verhex': data2['verhex'],
                     'pubhex': data2['pubhex'],
                     }
            })

        # now recreate with saved data
        main.server.close()
        mainKeep = salting.SaltKeep(opts=opts,
                                     basedirpath=mainData['basedirpath'],
                                     stackname=mainData['name'])
        main = stacking.RoadStack(name=mainData['name'],
                                  store=self.store,
                                  keep=mainKeep,
                                  main=True)

        self.assertEqual(main.local.name, mainData['name'])
        self.assertEqual(main.local.uid, 1)
        self.assertEqual(main.main, True)
        self.assertEqual(main.local.role, mainData['role'])
        self.assertIs(main.keep.auto, raeting.AutoMode.always.value)
        self.assertTrue(main.ha, ("0.0.0.0", raeting.RAET_PORT))
        self.assertEqual(main.local.priver.keyhex, mainData['prihex'])
        self.assertEqual(main.local.signer.keyhex, mainData['sighex'])

        self.assertEqual(len(main.remotes), 2)
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

        opts = self.createOpts(role='main',
                               dirpath=self.tempDirpath,
                               openMode=False,
                               autoAccept=True)
        mainData = self.createRoadData(role=opts['id'],
                                       kind=opts['__role'],
                                       cachedirpath=opts['cachedir'],
                                       )
        mainKeep = salting.SaltKeep(opts=opts,
                                    basedirpath=mainData['basedirpath'],
                                    stackname=mainData['name'])

        self.assertEqual(mainKeep.loadLocalData(), None)
        self.assertEqual(mainKeep.loadAllRemoteData(), {})

        main = self.createRoadStack(data=mainData,
                                     main=True,
                                     ha=None, #default ha is ("", raeting.RAET_PORT)
                                     keep=mainKeep)

        console.terse("{0}\nkeep dirpath = {1}\n".format(
                main.name, main.keep.dirpath))
        self.assertTrue(main.keep.dirpath.endswith(os.path.join('main', 'raet', 'main_master')))
        self.assertTrue(main.ha, ("0.0.0.0", raeting.RAET_PORT))
        self.assertIs(main.keep.auto, raeting.AutoMode.once.value)
        self.assertDictEqual(main.keep.loadLocalData(), {
                                                         'name': mainData['name'],
                                                         'uid': 1,
                                                         'ha': ['127.0.0.1', 7530],
                                                         'iha': None,
                                                         'natted': None,
                                                         'fqdn': '1.0.0.127.in-addr.arpa',
                                                         'dyned': None,
                                                         'sid': 0,
                                                         'puid': 1,
                                                         'aha': ['0.0.0.0', 7530],
                                                         'role': mainData['role'],
                                                         'sighex': mainData['sighex'],
                                                         'prihex': mainData['prihex'],
                                                         })

        # add multiple remotes all with same role but different keys
        data1 = self.createRoadData(role='primary',
                                    kind=kinds.APPL_KIND_NAMES[kinds.applKinds.minion],
                                    cachedirpath=opts['cachedir'],
                                    )
        main.addRemote(estating.RemoteEstate(stack=main,
                                             name=data1['name'],
                                             kind=data1['kind'],
                                             ha=('127.0.0.1', 7532),
                                             role=data1['role'],
                                             verkey=data1['verhex'],
                                             pubkey=data1['pubhex'],
                                             ) )

        data2 = self.createRoadData(role='primary',
                                    kind='syndic',
                                    cachedirpath=opts['cachedir'],
                                    )
        main.addRemote(estating.RemoteEstate(stack=main,
                                             name=data2['name'],
                                             kind=data2['kind'],
                                             ha=('127.0.0.1', 7533),
                                             role=data2['role'],
                                             verkey=data2['verhex'],
                                             pubkey=data2['pubhex'],
                                             ) )

        main.dumpRemotes()

        # remote2 keys will be rejected since keys do not match remote1 but same role
        # upon reloading the keys for remote2 will be those from remote1

        self.assertDictEqual(main.keep.loadAllRemoteData(),
            {
                'primary_minion':
                    {
                     'name': data1['name'],
                     'uid': 2,
                     'fuid': 0,
                     'ha': ['127.0.0.1', 7532],
                     'iha': None,
                     'natted': None,
                     'fqdn': '1.0.0.127.in-addr.arpa',
                     'dyned': None,
                     'main': False,
                     'kind': data1['kind'],
                     'sid': 0,
                     'joined': None,
                     'role': data1['role'],
                     'acceptance': 1,
                     'verhex': data1['verhex'],
                     'pubhex': data1['pubhex'],
                     },
                'primary_syndic':
                    {
                     'name': data2['name'],
                     'uid': 3,
                     'fuid': 0,
                     'ha': ['127.0.0.1', 7533],
                     'iha': None,
                     'natted': None,
                     'fqdn': '1.0.0.127.in-addr.arpa',
                     'dyned': None,
                     'main': False,
                     'kind': data2['kind'],
                     'sid': 0,
                     'joined': None,
                     'role': data2['role'],
                     'acceptance': 1,
                     'verhex': data1['verhex'],
                     'pubhex': data1['pubhex'],
                     }
            })

        # now recreate with saved data
        main.server.close()
        mainKeep = salting.SaltKeep(opts=opts,
                                     basedirpath=mainData['basedirpath'],
                                     stackname=mainData['name'])
        main = stacking.RoadStack(name=mainData['name'],
                                  store=self.store,
                                  keep=mainKeep,
                                  main=True)

        self.assertEqual(main.local.name, mainData['name'])
        self.assertEqual(main.local.uid, 1)
        self.assertEqual(main.main, True)
        self.assertEqual(main.local.role, mainData['role'])
        self.assertIs(main.keep.auto, raeting.AutoMode.once.value)
        self.assertTrue(main.ha, ("0.0.0.0", raeting.RAET_PORT))
        self.assertEqual(main.local.priver.keyhex, mainData['prihex'])
        self.assertEqual(main.local.signer.keyhex, mainData['sighex'])

        self.assertEqual(len(main.remotes), 2)
        for data in [data1, data2]:
            remote = main.nameRemotes[data['name']]
            self.assertEqual(remote.name, data['name'])
            self.assertEqual(remote.role, data['role'])
            self.assertEqual(remote.acceptance, 1)
            self.assertEqual(remote.pubber.keyhex, data1['pubhex'])
            self.assertEqual(remote.verfer.keyhex, data1['verhex'])


        main.server.close()

    def testBootstrapNever(self):
        '''
        Bootstap to allowed with never mode on main
        '''
        console.terse("{0}\n".format(self.testBootstrapNever.__doc__))

        opts = self.createOpts(role='main',
                               kind=kinds.APPL_KIND_NAMES[kinds.applKinds.master],
                               dirpath=self.tempDirpath,
                               openMode=False,
                               autoAccept=False)
        mainData = self.createRoadData(role=opts['id'],
                                       kind=opts['__role'],
                                       cachedirpath=opts['cachedir'] )
        mainKeep = salting.SaltKeep(opts=opts,
                                    basedirpath=mainData['basedirpath'],
                                    stackname=mainData['name'])

        self.assertEqual(mainKeep.loadLocalData(), None)
        self.assertEqual(mainKeep.loadAllRemoteData(), {})

        main = self.createRoadStack(data=mainData,
                                     main=True,
                                     ha=None, #default ha is ("", raeting.RAET_PORT)
                                     keep=mainKeep)

        console.terse("{0}\nkeep dirpath = {1}\n".format(
                main.name, main.keep.dirpath))
        self.assertTrue(main.keep.dirpath.endswith(os.path.join('main', 'raet', 'main_master')))
        self.assertTrue(main.ha, ("0.0.0.0", raeting.RAET_PORT))
        self.assertIs(main.keep.auto, raeting.AutoMode.never.value)
        self.assertDictEqual(main.keep.loadLocalData(), {
                                                         'name': mainData['name'],
                                                         'uid': 1,
                                                         'ha': ['127.0.0.1', 7530],
                                                         'iha': None,
                                                         'natted': None,
                                                         'fqdn': '1.0.0.127.in-addr.arpa',
                                                         'dyned': None,
                                                         'sid': 0,
                                                         'puid': 1,
                                                         'aha': ['0.0.0.0', 7530],
                                                         'role': mainData['role'],
                                                         'sighex': mainData['sighex'],
                                                         'prihex': mainData['prihex'],
                                                         })

        opts = self.createOpts(role='other',
                               kind=kinds.APPL_KIND_NAMES[kinds.applKinds.minion],
                               dirpath=self.tempDirpath,
                               openMode=False,
                               autoAccept=True)
        otherData = self.createRoadData(role=opts['id'],
                                       kind=opts['__role'],
                                       cachedirpath=opts['cachedir'] )
        otherKeep = salting.SaltKeep(opts=opts,
                                      basedirpath=otherData['basedirpath'],
                                      stackname=otherData['name'])

        self.assertEqual(otherKeep.loadLocalData(), None)
        self.assertEqual(otherKeep.loadAllRemoteData(), {})

        other = self.createRoadStack(data=otherData,
                                     main=None,
                                     ha=("", raeting.RAET_TEST_PORT),
                                     keep=otherKeep)

        console.terse("{0} keep dirpath = {1}\n".format(
                other.name, other.keep.dirpath))
        self.assertTrue(other.keep.dirpath.endswith(os.path.join('other', 'raet', 'other_minion')))
        self.assertEqual(other.ha, ("0.0.0.0", raeting.RAET_TEST_PORT))
        self.assertIs(other.keep.auto,  raeting.AutoMode.once.value)
        self.assertDictEqual(other.keep.loadLocalData(),
                            {
                                'name': otherData['name'],
                                'uid': 1,
                                'ha': ['127.0.0.1', 7531],
                                'iha': None,
                                'natted': None,
                                'fqdn': '1.0.0.127.in-addr.arpa',
                                'dyned': None,
                                'sid': 0,
                                'puid': 1,
                                'aha': ['0.0.0.0', 7531],
                                'role': otherData['role'],
                                'sighex': otherData['sighex'],
                                'prihex': otherData['prihex'],
                            })

        self.join(other, main)
        self.assertEqual(len(main.transactions), 1) # pending
        main.keep.acceptRemote(main.nameRemotes[other.local.name])
        self.service(main, other, duration=1.0)

        self.assertEqual(len(main.transactions), 0)
        remote = next(iter(main.remotes.values()))
        self.assertTrue(remote.joined)
        self.assertEqual(len(other.transactions), 0)
        remote = next(iter(other.remotes.values()))
        self.assertTrue(remote.joined)

        self.allow(other, main)
        self.assertEqual(len(main.transactions), 0)
        remote = next(iter(main.remotes.values()))
        self.assertTrue(remote.allowed)
        self.assertEqual(len(other.transactions), 0)
        remote = next(iter(other.remotes.values()))
        self.assertTrue(remote.allowed)

        for remote in main.remotes.values():
            path = os.path.join(main.keep.remotedirpath,
                    "{0}.{1}.{2}".format(main.keep.prefix, remote.name, main.keep.ext))
            self.assertTrue(os.path.exists(path))


        # now delete a key and see if road keep file is also deleted
        main.keep.saltRaetKey.delete_key(match=other.local.role)
        remote = main.remotes[2]
        path = os.path.join(main.keep.remotedirpath,
                "{0}.{1}.{2}".format(main.keep.prefix, remote.name, main.keep.ext))
        self.assertFalse(os.path.exists(path))

        for stack in [main, other]:
            stack.server.close()
            stack.clearAllKeeps()

    def testBootstrapOpen(self):
        '''
        Bootstap to allowed with open mode on main
        '''
        console.terse("{0}\n".format(self.testBootstrapOpen.__doc__))

        opts = self.createOpts(role='main',
                               kind=kinds.APPL_KIND_NAMES[kinds.applKinds.master],
                               dirpath=self.tempDirpath,
                               openMode=True,
                               autoAccept=True)
        mainData = self.createRoadData(role=opts['id'],
                                       kind=opts['__role'],
                                       cachedirpath=opts['cachedir'] )
        mainKeep = salting.SaltKeep(opts=opts,
                                    basedirpath=mainData['basedirpath'],
                                    stackname=mainData['name'])

        self.assertEqual(mainKeep.loadLocalData(), None)
        self.assertEqual(mainKeep.loadAllRemoteData(), {})

        main = self.createRoadStack(data=mainData,
                                     main=True,
                                     ha=None, #default ha is ("", raeting.RAET_PORT)
                                     keep=mainKeep)

        console.terse("{0}\nkeep dirpath = {1}\n".format(
                main.name, main.keep.dirpath))
        self.assertTrue(main.keep.dirpath.endswith(os.path.join('main', 'raet', 'main_master')))
        self.assertTrue(main.ha, ("0.0.0.0", raeting.RAET_PORT))
        self.assertIs(main.keep.auto, raeting.AutoMode.always.value)
        self.assertDictEqual(main.keep.loadLocalData(), {
                                                         'name': mainData['name'],
                                                         'uid': 1,
                                                         'ha': ['127.0.0.1', 7530],
                                                         'iha': None,
                                                         'natted': None,
                                                         'fqdn': '1.0.0.127.in-addr.arpa',
                                                         'dyned': None,
                                                         'sid': 0,
                                                         'puid': 1,
                                                         'aha': ['0.0.0.0', 7530],
                                                         'role': mainData['role'],
                                                         'sighex': mainData['sighex'],
                                                         'prihex': mainData['prihex'],
                                                         })

        opts = self.createOpts(role='other',
                               kind=kinds.APPL_KIND_NAMES[kinds.applKinds.minion],
                               dirpath=self.tempDirpath,
                               openMode=False,
                               autoAccept=True)
        otherData = self.createRoadData(role=opts['id'],
                                       kind=opts['__role'],
                                       cachedirpath=opts['cachedir'] )
        otherKeep = salting.SaltKeep(opts=opts,
                                      basedirpath=otherData['basedirpath'],
                                      stackname=otherData['name'])

        self.assertEqual(otherKeep.loadLocalData(), None)
        self.assertEqual(otherKeep.loadAllRemoteData(), {})

        other = self.createRoadStack(data=otherData,
                                     main=None,
                                     ha=("", raeting.RAET_TEST_PORT),
                                     keep=otherKeep)

        console.terse("{0} keep dirpath = {1}\n".format(
                other.name, other.keep.dirpath))
        self.assertTrue(other.keep.dirpath.endswith(os.path.join('other', 'raet', 'other_minion')))
        self.assertEqual(other.ha, ("0.0.0.0", raeting.RAET_TEST_PORT))
        self.assertIs(other.keep.auto, raeting.AutoMode.once.value)
        self.assertDictEqual(other.keep.loadLocalData(),
                            {
                                'name': otherData['name'],
                                'uid': 1,
                                'ha': ['127.0.0.1', 7531],
                                'iha': None,
                                'natted': None,
                                'fqdn': '1.0.0.127.in-addr.arpa',
                                'dyned': None,
                                'sid': 0,
                                'puid': 1,
                                'aha': ['0.0.0.0', 7531],
                                'role': otherData['role'],
                                'sighex': otherData['sighex'],
                                'prihex': otherData['prihex'],
                            })

        self.join(other, main)
        self.assertEqual(len(main.transactions), 0)
        remote = next(iter(main.remotes.values()))
        self.assertTrue(remote.joined)
        self.assertEqual(len(other.transactions), 0)
        remote = next(iter(other.remotes.values()))
        self.assertTrue(remote.joined)

        self.allow(other, main)
        self.assertEqual(len(main.transactions), 0)
        remote = next(iter(main.remotes.values()))
        self.assertTrue(remote.allowed)
        self.assertEqual(len(other.transactions), 0)
        remote = next(iter(other.remotes.values()))
        self.assertTrue(remote.allowed)

        for remote in main.remotes.values():
            path = os.path.join(main.keep.remotedirpath,
                    "{0}.{1}.{2}".format(main.keep.prefix, remote.name, main.keep.ext))
            self.assertTrue(os.path.exists(path))


        # now delete a key and see if road keep file is also deleted
        main.keep.saltRaetKey.delete_key(match=other.local.role)
        remote = main.remotes[2]
        path = os.path.join(main.keep.remotedirpath,
                "{0}.{1}.{2}".format(main.keep.prefix, remote.name, main.keep.ext))
        self.assertFalse(os.path.exists(path))

        for stack in [main, other]:
            stack.server.close()
            stack.clearAllKeeps()

    def testBootstrapAuto(self):
        '''
        Bootstap to allowed with auto accept on main
        '''
        console.terse("{0}\n".format(self.testBootstrapAuto.__doc__))

        opts = self.createOpts(role='main',
                               kind=kinds.APPL_KIND_NAMES[kinds.applKinds.master],
                               dirpath=self.tempDirpath,
                               openMode=False,
                               autoAccept=True)
        mainData = self.createRoadData(role=opts['id'],
                                       kind=opts['__role'],
                                       cachedirpath=opts['cachedir'] )
        mainKeep = salting.SaltKeep(opts=opts,
                                    basedirpath=mainData['basedirpath'],
                                    stackname=mainData['name'])

        self.assertEqual(mainKeep.loadLocalData(), None)
        self.assertEqual(mainKeep.loadAllRemoteData(), {})

        main = self.createRoadStack(data=mainData,
                                     main=True,
                                     ha=None, #default ha is ("", raeting.RAET_PORT)
                                     keep=mainKeep)

        console.terse("{0}\nkeep dirpath = {1}\n".format(
                main.name, main.keep.dirpath))
        self.assertTrue(main.keep.dirpath.endswith(os.path.join('main', 'raet', 'main_master')))
        self.assertEqual(main.ha, ("0.0.0.0", raeting.RAET_PORT))
        self.assertIs(main.keep.auto, raeting.AutoMode.once.value)
        self.assertDictEqual(main.keep.loadLocalData(), {
                                                         'name': mainData['name'],
                                                         'uid': 1,
                                                         'ha': ['127.0.0.1', 7530],
                                                         'iha': None,
                                                         'natted': None,
                                                         'fqdn': '1.0.0.127.in-addr.arpa',
                                                         'dyned': None,
                                                         'sid': 0,
                                                         'puid': 1,
                                                         'aha': ['0.0.0.0', 7530],
                                                         'role': mainData['role'],
                                                         'sighex': mainData['sighex'],
                                                         'prihex': mainData['prihex'],
                                                         })

        opts = self.createOpts(role='other',
                               kind=kinds.APPL_KIND_NAMES[kinds.applKinds.minion],
                               dirpath=self.tempDirpath,
                               openMode=False,
                               autoAccept=True)
        otherData = self.createRoadData(role=opts['id'],
                                       kind=opts['__role'],
                                       cachedirpath=opts['cachedir'] )
        otherKeep = salting.SaltKeep(opts=opts,
                                      basedirpath=otherData['basedirpath'],
                                      stackname=otherData['name'])

        self.assertEqual(otherKeep.loadLocalData(), None)
        self.assertEqual(otherKeep.loadAllRemoteData(), {})

        other = self.createRoadStack(data=otherData,
                                     main=None,
                                     ha=("", raeting.RAET_TEST_PORT),
                                     keep=otherKeep)

        console.terse("{0} keep dirpath = {1}\n".format(
                other.name, other.keep.dirpath))
        self.assertTrue(other.keep.dirpath.endswith(os.path.join('other', 'raet', 'other_minion')))
        self.assertEqual(other.ha, ("0.0.0.0", raeting.RAET_TEST_PORT))
        self.assertIs(other.keep.auto, raeting.AutoMode.once.value)
        self.assertDictEqual(other.keep.loadLocalData(),
                            {
                                'name': otherData['name'],
                                'uid': 1,
                                'ha': ['127.0.0.1', 7531],
                                'iha': None,
                                'natted': None,
                                'fqdn': '1.0.0.127.in-addr.arpa',
                                'dyned': None,
                                'sid': 0,
                                'puid': 1,
                                'aha': ['0.0.0.0', 7531],
                                'sighex': otherData['sighex'],
                                'prihex': otherData['prihex'],
                                'role': otherData['role'],
                            })

        self.join(other, main)
        self.assertEqual(len(main.transactions), 0)
        remote = next(iter(main.remotes.values()))
        self.assertTrue(remote.joined)
        self.assertEqual(len(other.transactions), 0)
        remote = next(iter(other.remotes.values()))
        self.assertTrue(remote.joined)

        self.allow(other, main)
        self.assertEqual(len(main.transactions), 0)
        remote = next(iter(main.remotes.values()))
        self.assertTrue(remote.allowed)
        self.assertEqual(len(other.transactions), 0)
        remote = next(iter(other.remotes.values()))
        self.assertTrue(remote.allowed)

        for remote in main.remotes.values():
            path = os.path.join(main.keep.remotedirpath,
                    "{0}.{1}.{2}".format(main.keep.prefix, remote.name, main.keep.ext))
            self.assertTrue(os.path.exists(path))


        # now delete a key and see if road keep file is also deleted
        main.keep.saltRaetKey.delete_key(match=other.local.role)
        remote = main.remotes[2]
        path = os.path.join(main.keep.remotedirpath,
                "{0}.{1}.{2}".format(main.keep.prefix, remote.name, main.keep.ext))
        self.assertFalse(os.path.exists(path))

        for stack in [main, other]:
            stack.server.close()
            stack.clearAllKeeps()

    def testBootstrapRoleNever(self):
        '''
        Bootstap to allowed with multiple remotes using same role with never main
        '''
        console.terse("{0}\n".format(self.testBootstrapRoleNever.__doc__))

        opts = self.createOpts(role='main',
                               kind=kinds.APPL_KIND_NAMES[kinds.applKinds.master],
                               dirpath=self.tempDirpath,
                               openMode=False,
                               autoAccept=False)
        mainData = self.createRoadData(role=opts['id'],
                                       kind=opts['__role'],
                                       cachedirpath=opts['cachedir'] )
        mainKeep = salting.SaltKeep(opts=opts,
                                    basedirpath=mainData['basedirpath'],
                                    stackname=mainData['name'])

        self.assertEqual(mainKeep.loadLocalData(), None)
        self.assertEqual(mainKeep.loadAllRemoteData(), {})

        main = self.createRoadStack(data=mainData,
                                     main=True,
                                     ha=None, #default ha is ("", raeting.RAET_PORT)
                                     keep=mainKeep)

        console.terse("{0}\nkeep dirpath = {1}\n".format(
                main.name, main.keep.dirpath))
        self.assertTrue(main.keep.dirpath.endswith(os.path.join('main', 'raet', 'main_master')))
        self.assertTrue(main.ha, ("0.0.0.0", raeting.RAET_PORT))
        self.assertIs(main.keep.auto, raeting.AutoMode.never.value)
        self.assertDictEqual(main.keep.loadLocalData(), {
                                                         'name': mainData['name'],
                                                         'uid': 1,
                                                         'ha': ['127.0.0.1', 7530],
                                                         'iha': None,
                                                         'natted': None,
                                                         'fqdn': '1.0.0.127.in-addr.arpa',
                                                         'dyned': None,
                                                         'sid': 0,
                                                         'puid': 1,
                                                         'aha': ['0.0.0.0', 7530],
                                                         'role': mainData['role'],
                                                         'sighex': mainData['sighex'],
                                                         'prihex': mainData['prihex'],
                                                         })

        opts = self.createOpts(role='primary',
                               kind=kinds.APPL_KIND_NAMES[kinds.applKinds.minion],
                               dirpath=self.tempDirpath,
                               openMode=False,
                               autoAccept=True)
        other1Data = self.createRoadData(role=opts['id'],
                                       kind=opts['__role'],
                                       cachedirpath=opts['cachedir'] )
        other1Keep = salting.SaltKeep(opts=opts,
                                      basedirpath=other1Data['basedirpath'],
                                      stackname=other1Data['name'])

        self.assertEqual(other1Keep.loadLocalData(), None)
        self.assertEqual(other1Keep.loadAllRemoteData(), {})

        other1 = self.createRoadStack(data=other1Data,
                                     main=None,
                                     ha=("", raeting.RAET_TEST_PORT),
                                     keep=other1Keep)

        console.terse("{0} keep dirpath = {1}\n".format(
                other1.name, other1.keep.dirpath))
        self.assertTrue(other1.keep.dirpath.endswith(os.path.join('primary', 'raet', 'primary_minion')))
        self.assertEqual(other1.ha, ("0.0.0.0", raeting.RAET_TEST_PORT))
        self.assertIs(other1.keep.auto, raeting.AutoMode.once.value)
        self.assertDictEqual(other1.keep.loadLocalData(),
                            {
                                'name': other1Data['name'],
                                'uid': 1,
                                'ha': ['127.0.0.1', 7531],
                                'iha': None,
                                'natted': None,
                                'fqdn': '1.0.0.127.in-addr.arpa',
                                'dyned': None,
                                'sid': 0,
                                'puid': 1,
                                'aha': ['0.0.0.0', 7531],
                                'role': other1Data['role'],
                                'sighex': other1Data['sighex'],
                                'prihex': other1Data['prihex'],
                            })

        self.join(other1, main)
        self.assertEqual(len(main.transactions), 1) # pending
        main.keep.acceptRemote(main.nameRemotes[other1.local.name])
        self.service(main, other1, duration=1.0)

        self.assertEqual(len(main.transactions), 0)
        remote = next(iter(main.remotes.values()))
        self.assertTrue(remote.joined)
        self.assertEqual(len(other1.transactions), 0)
        remote = next(iter(other1.remotes.values()))
        self.assertTrue(remote.joined)

        self.allow(other1, main)
        self.assertEqual(len(main.transactions), 0)
        remote = next(iter(main.remotes.values()))
        self.assertTrue(remote.allowed)
        self.assertEqual(len(other1.transactions), 0)
        remote = next(iter(other1.remotes.values()))
        self.assertTrue(remote.allowed)

        for remote in main.remotes.values():
            path = os.path.join(main.keep.remotedirpath,
                    "{0}.{1}.{2}".format(main.keep.prefix, remote.name, main.keep.ext))
            self.assertTrue(os.path.exists(path))

        # create other2 stack but use same role but different keys as other1
        opts = self.createOpts(role='primary',
                               kind=kinds.APPL_KIND_NAMES[kinds.applKinds.caller],
                               dirpath=self.tempDirpath,
                               openMode=False,
                               autoAccept=True)
        other2Data = self.createRoadData(role=opts['id'],
                                       kind=opts['__role'],
                                       cachedirpath=opts['cachedir'] )
        other2Keep = salting.SaltKeep(opts=opts,
                                      basedirpath=other2Data['basedirpath'],
                                      stackname=other2Data['name'])

        self.assertEqual(other2Keep.loadLocalData(), None)
        self.assertEqual(other2Keep.loadAllRemoteData(), {})

        other2 = self.createRoadStack(data=other2Data,
                                     main=None,
                                     ha=("", 7532),
                                     keep=other2Keep)

        console.terse("{0} keep dirpath = {1}\n".format(
                other2.name, other2.keep.dirpath))
        self.assertTrue(other2.keep.dirpath.endswith(os.path.join('primary', 'raet', 'primary_caller')))
        self.assertEqual(other2.ha, ("0.0.0.0", 7532))
        self.assertIs(other2.keep.auto, raeting.AutoMode.once.value)
        self.assertDictEqual(other2.keep.loadLocalData(),
                            {
                                'name': other2Data['name'],
                                'uid': 1,
                                'ha': ['127.0.0.1', 7532],
                                'iha': None,
                                'natted': None,
                                'fqdn': '1.0.0.127.in-addr.arpa',
                                'dyned': None,
                                'sid': 0,
                                'puid': 1,
                                'aha': ['0.0.0.0', 7532],
                                'sighex': other2Data['sighex'],
                                'prihex': other2Data['prihex'],
                                'role': other2Data['role'],
                            })

        # should not join since role same but keys different
        self.join(other2, main)
        self.assertEqual(len(main.transactions), 0) # rejected since not same keys
        self.assertEqual(len(other2.remotes), 0)
        self.assertEqual(len(main.remotes), 1)
        #main.removeRemote(main.nameRemotes[other2.local.name], clear=True)
        other2.server.close()
        other2.keep.clearAllDir()
        path = os.path.join(main.keep.remotedirpath,
                                "{0}.{1}.{2}".format(main.keep.prefix, other2.local.name, main.keep.ext))
        self.assertFalse(os.path.exists(path))
        other2.keep.clearRoleDir()
        self.assertFalse(os.path.exists(opts['pki_dir']))
        #shutil.rmtree(opts['pki_dir'])

        # recreate other2 stack but use same role and same keys as other1
        opts = self.createOpts(role='primary',
                               kind=kinds.APPL_KIND_NAMES[kinds.applKinds.caller],
                               dirpath=self.tempDirpath,
                               openMode=False,
                               autoAccept=True)
        other2Data = self.createRoadData(role=opts['id'],
                                       kind=opts['__role'],
                                       cachedirpath=opts['cachedir'] )
        other2Data['sighex'] = other1Data['sighex']
        other2Data['prihex'] = other1Data['prihex']
        other2Keep = salting.SaltKeep(opts=opts,
                                      basedirpath=other2Data['basedirpath'],
                                      stackname=other2Data['name'])

        self.assertEqual(other2Keep.loadLocalData(), None)
        self.assertEqual(other2Keep.loadAllRemoteData(), {})

        other2 = self.createRoadStack(data=other2Data,
                                     main=None,
                                     ha=("", 7532),
                                     keep=other2Keep)

        console.terse("{0} keep dirpath = {1}\n".format(
                other2.name, other2.keep.dirpath))
        self.assertTrue(other2.keep.dirpath.endswith(os.path.join('primary', 'raet', 'primary_caller')))
        self.assertEqual(other2.ha, ("0.0.0.0", 7532))
        self.assertIs(other2.keep.auto, raeting.AutoMode.once.value)
        self.assertDictEqual(other2.keep.loadLocalData(),
                            {
                                'name': other2Data['name'],
                                'uid': 1,
                                'ha': ['127.0.0.1', 7532],
                                'iha': None,
                                'natted': None,
                                'fqdn': '1.0.0.127.in-addr.arpa',
                                'dyned': None,
                                'sid': 0,
                                'puid': 1,
                                'aha': ['0.0.0.0', 7532],
                                'role': other2Data['role'],
                                'sighex': other1Data['sighex'],
                                'prihex': other1Data['prihex'],
                            })

        # should join since same role and keys
        self.join(other2, main)

        self.assertEqual(len(main.transactions), 0)
        remote = next(iter(main.remotes.values()))
        self.assertTrue(remote.joined)
        self.assertEqual(len(other2.transactions), 0)
        remote = next(iter(other2.remotes.values()))
        self.assertTrue(remote.joined)

        self.allow(other2, main)
        self.assertEqual(len(main.transactions), 0)
        remote = next(iter(main.remotes.values()))
        self.assertTrue(remote.allowed)
        self.assertEqual(len(other2.transactions), 0)
        remote = next(iter(other2.remotes.values()))
        self.assertTrue(remote.allowed)

        for remote in main.remotes.values():
            path = os.path.join(main.keep.remotedirpath,
                    "{0}.{1}.{2}".format(main.keep.prefix, remote.name, main.keep.ext))
            self.assertTrue(os.path.exists(path))

        # now delete a key and see if both road keep file are also deleted
        main.keep.saltRaetKey.delete_key(match=other1.local.role)
        remote = main.remotes[2]
        path = os.path.join(main.keep.remotedirpath,
                "{0}.{1}.{2}".format(main.keep.prefix, remote.name, main.keep.ext))
        self.assertFalse(os.path.exists(path))
        remote = main.remotes[4]
        path = os.path.join(main.keep.remotedirpath,
                        "{0}.{1}.{2}".format(main.keep.prefix, remote.name, main.keep.ext))
        self.assertFalse(os.path.exists(path))

        for stack in [main, other1, other2]:
            stack.server.close()
            stack.clearAllKeeps()

    def testBootstrapRoleAuto(self):
        '''
        Bootstap to allowed with multiple remotes using same role with auto main
        '''
        console.terse("{0}\n".format(self.testBootstrapRoleAuto.__doc__))

        opts = self.createOpts(role='main',
                               kind=kinds.APPL_KIND_NAMES[kinds.applKinds.master],
                               dirpath=self.tempDirpath,
                               openMode=False,
                               autoAccept=True)
        mainData = self.createRoadData(role=opts['id'],
                                       kind=opts['__role'],
                                       cachedirpath=opts['cachedir'] )
        mainKeep = salting.SaltKeep(opts=opts,
                                    basedirpath=mainData['basedirpath'],
                                    stackname=mainData['name'])

        self.assertEqual(mainKeep.loadLocalData(), None)
        self.assertEqual(mainKeep.loadAllRemoteData(), {})

        main = self.createRoadStack(data=mainData,
                                     main=True,
                                     ha=None, #default ha is ("", raeting.RAET_PORT)
                                     keep=mainKeep)

        console.terse("{0}\nkeep dirpath = {1}\n".format(
                main.name, main.keep.dirpath))
        self.assertTrue(main.keep.dirpath.endswith(os.path.join('main', 'raet', 'main_master')))
        self.assertTrue(main.ha, ("0.0.0.0", raeting.RAET_PORT))
        self.assertIs(main.keep.auto, raeting.AutoMode.once.value)
        self.assertDictEqual(main.keep.loadLocalData(), {
                                                         'name': mainData['name'],
                                                         'uid': 1,
                                                         'ha': ['127.0.0.1', 7530],
                                                         'iha': None,
                                                         'natted': None,
                                                         'fqdn': '1.0.0.127.in-addr.arpa',
                                                         'dyned': None,
                                                         'sid': 0,
                                                         'puid': 1,
                                                         'aha': ['0.0.0.0', 7530],
                                                          'role': mainData['role'],
                                                         'sighex': mainData['sighex'],
                                                         'prihex': mainData['prihex'],
                                                         })

        opts = self.createOpts(role='primary',
                               kind=kinds.APPL_KIND_NAMES[kinds.applKinds.minion],
                               dirpath=self.tempDirpath,
                               openMode=False,
                               autoAccept=True)
        other1Data = self.createRoadData(role=opts['id'],
                                       kind=opts['__role'],
                                       cachedirpath=opts['cachedir'] )
        other1Keep = salting.SaltKeep(opts=opts,
                                      basedirpath=other1Data['basedirpath'],
                                      stackname=other1Data['name'])

        self.assertEqual(other1Keep.loadLocalData(), None)
        self.assertEqual(other1Keep.loadAllRemoteData(), {})

        other1 = self.createRoadStack(data=other1Data,
                                     main=None,
                                     ha=("", raeting.RAET_TEST_PORT),
                                     keep=other1Keep)

        console.terse("{0} keep dirpath = {1}\n".format(
                other1.name, other1.keep.dirpath))
        self.assertTrue(other1.keep.dirpath.endswith(os.path.join('primary', 'raet', 'primary_minion')))
        self.assertEqual(other1.ha, ("0.0.0.0", raeting.RAET_TEST_PORT))
        self.assertIs(other1.keep.auto, raeting.AutoMode.once.value)
        self.assertDictEqual(other1.keep.loadLocalData(),
                            {
                                'name': other1Data['name'],
                                'uid': 1,
                                'ha': ['127.0.0.1', 7531],
                                'iha': None,
                                'natted': None,
                                'fqdn': '1.0.0.127.in-addr.arpa',
                                'dyned': None,
                                'sid': 0,
                                'puid': 1,
                                'aha': ['0.0.0.0', 7531],
                                'role': other1Data['role'],
                                'sighex': other1Data['sighex'],
                                'prihex': other1Data['prihex'],
                            })

        self.join(other1, main)
        self.assertEqual(len(main.transactions), 0)
        remote = next(iter(main.remotes.values()))
        self.assertTrue(remote.joined)
        self.assertEqual(len(other1.transactions), 0)
        remote = next(iter(other1.remotes.values()))
        self.assertTrue(remote.joined)

        self.allow(other1, main)
        self.assertEqual(len(main.transactions), 0)
        remote = next(iter(main.remotes.values()))
        self.assertTrue(remote.allowed)
        self.assertEqual(len(other1.transactions), 0)
        remote = next(iter(other1.remotes.values()))
        self.assertTrue(remote.allowed)

        for remote in main.remotes.values():
            path = os.path.join(main.keep.remotedirpath,
                    "{0}.{1}.{2}".format(main.keep.prefix, remote.name, main.keep.ext))
            self.assertTrue(os.path.exists(path))

        # create other2 stack but use same role and different keys as other1
        opts = self.createOpts(role='primary',
                               kind=kinds.APPL_KIND_NAMES[kinds.applKinds.caller],
                               dirpath=self.tempDirpath,
                               openMode=False,
                               autoAccept=True)
        other2Data = self.createRoadData(role=opts['id'],
                                       kind=opts['__role'],
                                       cachedirpath=opts['cachedir'] )
        other2Data['sighex'] = other1Data['sighex']
        other2Data['prihex'] = other1Data['prihex']

        other2Keep = salting.SaltKeep(opts=opts,
                                      basedirpath=other2Data['basedirpath'],
                                      stackname=other2Data['name'])

        self.assertEqual(other2Keep.loadLocalData(), None)
        self.assertEqual(other2Keep.loadAllRemoteData(), {})

        other2 = self.createRoadStack(data=other2Data,
                                     main=None,
                                     ha=("", 7532),
                                     keep=other2Keep)

        console.terse("{0} keep dirpath = {1}\n".format(
                other2.name, other2.keep.dirpath))
        self.assertTrue(other2.keep.dirpath.endswith(os.path.join('primary', 'raet', 'primary_caller')))
        self.assertEqual(other2.ha, ("0.0.0.0", 7532))
        self.assertIs(other2.keep.auto, raeting.AutoMode.once.value)
        self.assertDictEqual(other2.keep.loadLocalData(),
                            {
                                'name': other2Data['name'],
                                'uid': 1,
                                'ha': ['127.0.0.1', 7532],
                                'iha': None,
                                'natted': None,
                                'fqdn': '1.0.0.127.in-addr.arpa',
                                'dyned': None,
                                'sid': 0,
                                'puid': 1,
                                'aha': ['0.0.0.0', 7532],
                                'role': other2Data['role'],
                                'sighex': other2Data['sighex'],
                                'prihex': other2Data['prihex'],
                            })

        # should join since open mode
        self.join(other2, main)

        self.assertEqual(len(main.transactions), 0)
        remote = next(iter(main.remotes.values()))
        self.assertTrue(remote.joined)
        self.assertEqual(len(other2.transactions), 0)
        remote = next(iter(other2.remotes.values()))
        self.assertTrue(remote.joined)

        self.allow(other2, main)
        self.assertEqual(len(main.transactions), 0)
        remote = next(iter(main.remotes.values()))
        self.assertTrue(remote.allowed)
        self.assertEqual(len(other2.transactions), 0)
        remote = next(iter(other2.remotes.values()))
        self.assertTrue(remote.allowed)

        for remote in main.remotes.values():
            path = os.path.join(main.keep.remotedirpath,
                    "{0}.{1}.{2}".format(main.keep.prefix, remote.name, main.keep.ext))
            self.assertTrue(os.path.exists(path))


        # now delete a key and see if both road keep file are also deleted
        main.keep.saltRaetKey.delete_key(match=other1.local.role)
        remote = main.remotes[2]
        path = os.path.join(main.keep.remotedirpath,
                "{0}.{1}.{2}".format(main.keep.prefix, remote.name, main.keep.ext))
        self.assertFalse(os.path.exists(path))
        remote = main.remotes[3]
        path = os.path.join(main.keep.remotedirpath,
                        "{0}.{1}.{2}".format(main.keep.prefix, remote.name, main.keep.ext))
        self.assertFalse(os.path.exists(path))

        for stack in [main, other1, other2]:
            stack.server.close()
            stack.clearAllKeeps()

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
             'testBootstrapNever',
             'testBootstrapOpen',
             'testBootstrapAuto',
             'testBootstrapRoleNever',
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
