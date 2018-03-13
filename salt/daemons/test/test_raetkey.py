# -*- coding: utf-8 -*-
'''
Tests to try out salt key.RaetKey Potentially ephemeral

'''
from __future__ import absolute_import, print_function, unicode_literals
# pylint: skip-file
# pylint: disable=C0103
import sys
import salt.utils.stringutils
from salt.ext.six.moves import map
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


def setUpModule():
    console.reinit(verbosity=console.Wordage.concise)


def tearDownModule():
    pass


class BasicTestCase(unittest.TestCase):
    """"""

    def setUp(self):
        self.store = storing.Store(stamp=0.0)
        self.timer = StoreTimer(store=self.store, duration=1.0)

        self.saltDirpath = tempfile.mkdtemp(prefix="salt", suffix="main", dir='/tmp')

        pkiDirpath = os.path.join(self.saltDirpath, 'pki')
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

        self.localFilepath = os.path.join(pkiDirpath, 'local.key')
        if os.path.exists(self.localFilepath):
            mode = os.stat(self.localFilepath).st_mode
            os.chmod(self.localFilepath, mode | stat.S_IWUSR | stat.S_IWUSR)

        self.cacheDirpath = os.path.join(self.saltDirpath, 'cache')
        self.sockDirpath = os.path.join(self.saltDirpath, 'sock')

        self.opts = dict(
                        __role='master',
                        id='master',
                        pki_dir=pkiDirpath,
                        sock_dir=self.sockDirpath,
                        cachedir=self.cacheDirpath,
                        open_mode=False,
                        auto_accept=True,
                        transport='raet',
                        )

        self.mainKeeper = RaetKey(opts=self.opts)
        self.baseDirpath = tempfile.mkdtemp(prefix="salt", suffix="base", dir='/tmp')

    def tearDown(self):
        if os.path.exists(self.saltDirpath):
            shutil.rmtree(self.saltDirpath)

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

    def testAutoAccept(self):
        '''
        Basic function of RaetKey in auto accept mode
        '''
        console.terse("{0}\n".format(self.testAutoAccept.__doc__))
        self.opts['auto_accept'] = True
        self.assertTrue(self.opts['auto_accept'])
        self.assertDictEqual(self.mainKeeper.all_keys(), {'accepted': [],
                                                          'local': [],
                                                          'rejected': [],
                                                          'pending': []})

        localkeys = self.mainKeeper.read_local()
        self.assertDictEqual(localkeys, {})

        main = self.createRoadData(name='main', base=self.baseDirpath)
        self.mainKeeper.write_local(main['prihex'], main['sighex'])
        localkeys = self.mainKeeper.read_local()
        self.assertDictEqual(localkeys,
                             {'priv': salt.utils.stringutils.to_str(main['prihex']),
                              'sign': salt.utils.stringutils.to_str(main['sighex'])})
        allkeys = self.mainKeeper.all_keys()
        self.assertDictEqual(allkeys, {'accepted': [],
                                       'local': [self.localFilepath],
                                       'rejected': [],
                                       'pending': []})

        other1 = self.createRoadData(name='other1', base=self.baseDirpath)
        other2 = self.createRoadData(name='other2', base=self.baseDirpath)

        status = self.mainKeeper.status(other1['name'], other1['pubhex'], other1['verhex'])
        self.assertEqual(status, 'accepted')
        status = self.mainKeeper.status(other2['name'], other2['pubhex'], other2['verhex'])
        self.assertEqual(status, 'accepted')

        allkeys = self.mainKeeper.all_keys()
        self.assertDictEqual(allkeys, {'accepted': ['other1', 'other2'],
                                       'local': [self.localFilepath],
                                       'pending': [],
                                       'rejected': []})

        remotekeys = self.mainKeeper.read_remote(other1['name'])
        self.assertDictEqual(remotekeys, {'minion_id': 'other1',
                                          'pub': salt.utils.stringutils.to_str(other1['pubhex']),
                                          'verify': salt.utils.stringutils.to_str(other1['verhex'])})

        remotekeys = self.mainKeeper.read_remote(other2['name'])
        self.assertDictEqual(remotekeys, {'minion_id': 'other2',
                                          'pub': salt.utils.stringutils.to_str(other2['pubhex']),
                                          'verify': salt.utils.stringutils.to_str(other2['verhex'])})

        listkeys = self.mainKeeper.list_keys()
        self.assertDictEqual(listkeys, {'accepted': ['other1', 'other2'],
                                        'rejected': [],
                                        'pending': []})

        allremotekeys = self.mainKeeper.read_all_remote()
        self.assertDictEqual(allremotekeys,
                             {'other1':
                                  {'verify': salt.utils.stringutils.to_str(other1['verhex']),
                                   'minion_id': 'other1',
                                   'acceptance': 'accepted',
                                   'pub': salt.utils.stringutils.to_str(other1['pubhex']), },
                              'other2':
                                  {'verify': salt.utils.stringutils.to_str(other2['verhex']),
                                   'minion_id': 'other2',
                                   'acceptance': 'accepted',
                                   'pub': salt.utils.stringutils.to_str(other2['pubhex']), }
                              })

    def testManualAccept(self):
        '''
        Basic function of RaetKey in non auto accept mode
        '''
        console.terse("{0}\n".format(self.testAutoAccept.__doc__))
        self.opts['auto_accept'] = False
        self.assertFalse(self.opts['auto_accept'])
        self.assertDictEqual(self.mainKeeper.all_keys(), {'accepted': [],
                                                          'local': [],
                                                          'rejected': [],
                                                          'pending': []})

        localkeys = self.mainKeeper.read_local()
        self.assertDictEqual(localkeys, {})

        main = self.createRoadData(name='main', base=self.baseDirpath)
        self.mainKeeper.write_local(main['prihex'], main['sighex'])
        localkeys = self.mainKeeper.read_local()
        self.assertDictEqual(localkeys,
                             {'priv': salt.utils.stringutils.to_str(main['prihex']),
                              'sign': salt.utils.stringutils.to_str(main['sighex'])})
        allkeys = self.mainKeeper.all_keys()
        self.assertDictEqual(allkeys, {'accepted': [],
                                       'local': [self.localFilepath],
                                       'rejected': [],
                                       'pending': []})

        other1 = self.createRoadData(name='other1', base=self.baseDirpath)
        other2 = self.createRoadData(name='other2', base=self.baseDirpath)

        status = self.mainKeeper.status(other1['name'], other1['pubhex'], other1['verhex'])
        self.assertEqual(status, 'pending')
        status = self.mainKeeper.status(other2['name'], other2['pubhex'], other2['verhex'])
        self.assertEqual(status, 'pending')

        allkeys = self.mainKeeper.all_keys()
        self.assertDictEqual(allkeys, {'accepted': [],
                                       'local': [self.localFilepath],
                                       'pending': ['other1', 'other2'],
                                       'rejected': []})

        remotekeys = self.mainKeeper.read_remote(other1['name'])
        self.assertDictEqual(remotekeys, {})

        remotekeys = self.mainKeeper.read_remote(other2['name'])
        self.assertDictEqual(remotekeys, {})

        listkeys = self.mainKeeper.list_keys()
        self.assertDictEqual(listkeys, {'accepted': [],
                                        'rejected': [],
                                        'pending': ['other1', 'other2']})

        allremotekeys = self.mainKeeper.read_all_remote()
        self.assertDictEqual(allremotekeys,
                             {'other1':
                                  {'verify': salt.utils.stringutils.to_str(other1['verhex']),
                                   'minion_id': 'other1',
                                   'acceptance': 'pending',
                                   'pub': salt.utils.stringutils.to_str(other1['pubhex']),
                                   },
                              'other2':
                                  {'verify': salt.utils.stringutils.to_str(other2['verhex']),
                                   'minion_id': 'other2',
                                   'acceptance': 'pending',
                                   'pub': salt.utils.stringutils.to_str(other2['pubhex']),
                                   }
                              })

        self.mainKeeper.accept_all()

        allkeys = self.mainKeeper.all_keys()
        self.assertDictEqual(allkeys, {'accepted': ['other1', 'other2'],
                                       'local': [self.localFilepath],
                                       'pending': [],
                                       'rejected': []})

        remotekeys = self.mainKeeper.read_remote(other1['name'])
        self.assertDictEqual(remotekeys, {'minion_id': 'other1',
                                          'pub': salt.utils.stringutils.to_str(other1['pubhex']),
                                          'verify': salt.utils.stringutils.to_str(other1['verhex'])})

        remotekeys = self.mainKeeper.read_remote(other2['name'])
        self.assertDictEqual(remotekeys, {'minion_id': 'other2',
                                          'pub': salt.utils.stringutils.to_str(other2['pubhex']),
                                          'verify': salt.utils.stringutils.to_str(other2['verhex'])})

        listkeys = self.mainKeeper.list_keys()
        self.assertDictEqual(listkeys, {'accepted': ['other1', 'other2'],
                                        'rejected': [],
                                        'pending': []})

        allremotekeys = self.mainKeeper.read_all_remote()
        self.assertDictEqual(allremotekeys,
                             {'other1':
                                  {'verify': salt.utils.stringutils.to_str(other1['verhex']),
                                   'minion_id': 'other1',
                                   'acceptance': 'accepted',
                                   'pub': salt.utils.stringutils.to_str(other1['pubhex']),
                                   },
                              'other2':
                                  {'verify': salt.utils.stringutils.to_str(other2['verhex']),
                                   'minion_id': 'other2',
                                   'acceptance': 'accepted',
                                   'pub': salt.utils.stringutils.to_str(other2['pubhex']),
                                   }
                              })

    def testDelete(self):
        '''
        Basic function of RaetKey to delete key
        '''
        console.terse("{0}\n".format(self.testDelete.__doc__))
        self.opts['auto_accept'] = True
        self.assertTrue(self.opts['auto_accept'])
        self.assertDictEqual(self.mainKeeper.all_keys(), {'accepted': [],
                                                          'local': [],
                                                          'rejected': [],
                                                          'pending': []})

        localkeys = self.mainKeeper.read_local()
        self.assertDictEqual(localkeys, {})

        main = self.createRoadData(name='main', base=self.baseDirpath)
        self.mainKeeper.write_local(main['prihex'], main['sighex'])
        localkeys = self.mainKeeper.read_local()
        self.assertDictEqual(localkeys,
                             {'priv': salt.utils.stringutils.to_str(main['prihex']),
                              'sign': salt.utils.stringutils.to_str(main['sighex'])})
        allkeys = self.mainKeeper.all_keys()
        self.assertDictEqual(allkeys, {'accepted': [],
                                       'local': [self.localFilepath],
                                       'rejected': [],
                                       'pending': []})

        other1 = self.createRoadData(name='other1', base=self.baseDirpath)
        other2 = self.createRoadData(name='other2', base=self.baseDirpath)

        status = self.mainKeeper.status(other1['name'], other1['pubhex'], other1['verhex'])
        self.assertEqual(status, 'accepted')
        status = self.mainKeeper.status(other2['name'], other2['pubhex'], other2['verhex'])
        self.assertEqual(status, 'accepted')

        allkeys = self.mainKeeper.all_keys()
        self.assertDictEqual(allkeys, {'accepted': ['other1', 'other2'],
                                       'local': [self.localFilepath],
                                       'pending': [],
                                       'rejected': []})

        remotekeys = self.mainKeeper.read_remote(other1['name'])
        self.assertDictEqual(remotekeys, {'minion_id': 'other1',
                                          'pub': salt.utils.stringutils.to_str(other1['pubhex']),
                                          'verify': salt.utils.stringutils.to_str(other1['verhex']),
                                          })

        remotekeys = self.mainKeeper.read_remote(other2['name'])
        self.assertDictEqual(remotekeys, {'minion_id': 'other2',
                                          'pub': salt.utils.stringutils.to_str(other2['pubhex']),
                                          'verify': salt.utils.stringutils.to_str(other2['verhex']),
                                          })

        listkeys = self.mainKeeper.list_keys()
        self.assertDictEqual(listkeys, {'accepted': ['other1', 'other2'],
                                        'rejected': [],
                                        'pending': []})

        allremotekeys = self.mainKeeper.read_all_remote()
        self.assertDictEqual(allremotekeys,
                             {'other1':
                                  {'verify': salt.utils.stringutils.to_str(other1['verhex']),
                                   'minion_id': 'other1',
                                   'acceptance': 'accepted',
                                   'pub': salt.utils.stringutils.to_str(other1['pubhex'])
                                   },
                              'other2':
                                  {'verify': salt.utils.stringutils.to_str(other2['verhex']),
                                   'minion_id': 'other2',
                                   'acceptance': 'accepted',
                                   'pub': salt.utils.stringutils.to_str(other2['pubhex']),
                                   }
                              })

        self.mainKeeper.delete_key(match=other1['name'])

        allkeys = self.mainKeeper.all_keys()
        self.assertDictEqual(allkeys, {'accepted': ['other2'],
                                       'local': [self.localFilepath],
                                       'pending': [],
                                       'rejected': []})

        remotekeys = self.mainKeeper.read_remote(other1['name'])
        self.assertDictEqual(remotekeys, {})

        remotekeys = self.mainKeeper.read_remote(other2['name'])
        self.assertDictEqual(remotekeys, {'minion_id': 'other2',
                                          'pub': salt.utils.stringutils.to_str(other2['pubhex']),
                                          'verify': salt.utils.stringutils.to_str(other2['verhex'])})

        listkeys = self.mainKeeper.list_keys()
        self.assertDictEqual(listkeys, {'accepted': ['other2'],
                                        'rejected': [],
                                        'pending': []})

        allremotekeys = self.mainKeeper.read_all_remote()
        self.assertDictEqual(allremotekeys,
                             {'other2':
                                  {'verify': salt.utils.stringutils.to_str(other2['verhex']),
                                   'minion_id': 'other2',
                                   'acceptance': 'accepted',
                                   'pub': salt.utils.stringutils.to_str(other2['pubhex']),
                                   }
                              })


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
    tests = []
    names = ['testAutoAccept',
             'testManualAccept',
             'testDelete']

    tests.extend(list(list(map(BasicTestCase, names))))

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
    # console.reinit(verbosity=console.Wordage.concise)

    runAll()  # run all unittests

    # runSome()  #only run some

    # runOne('testDelete')
