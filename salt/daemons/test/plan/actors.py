# -*- coding: utf-8 -*-
'''
Test behaviors used by test plans
'''
from __future__ import absolute_import, print_function, unicode_literals
import os
import stat
import time
from collections import deque

# Import ioflo libs
import ioflo.base.deeding
from ioflo.aid.odicting import odict

from ioflo.base.consoling import getConsole
console = getConsole()

from raet import raeting, nacling
from raet.lane.stacking import LaneStack
from raet.lane.yarding import RemoteYard
from raet.road.estating import RemoteEstate
from raet.road.stacking import RoadStack
from raet.stacking import Stack

import salt.utils.stringutils
from salt.daemons import salting
from salt.utils.event import tagify


class DeedTestWrapper(object):
    def assertTrue(self, condition):
        if not condition:
            self.failure.value = 'Fail'
            raise Exception("Test Failed")


def createStack(ip):
    stack = Stack()
    stack.ha = (ip, '1234')
    return stack


class TestOptsSetup(ioflo.base.deeding.Deed):
    '''
    Setup opts share
    '''
    Ioinits = {'opts': salt.utils.stringutils.to_str('.salt.opts')}

    def action(self):
        '''
        Register presence requests
        Iterate over the registered presence yards and fire!
        '''
        pkiDirpath = os.path.join('/tmp', 'raet', 'test', self.role, 'pki')
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

        cacheDirpath = os.path.join('/tmp/raet', 'cache', self.role)
        if not os.path.exists(cacheDirpath):
            os.makedirs(cacheDirpath)

        sockDirpath = os.path.join('/tmp/raet', 'sock', self.role)
        if not os.path.exists(sockDirpath):
            os.makedirs(sockDirpath)

        self.opts.value = dict(
            id=self.role,
            __role=self.role,
            ioflo_period=0.1,
            ioflo_realtime=True,
            ioflo_verbose=2,
            interface="",
            raet_port=self.raet_port,
            transport='raet',
            client_acl=dict(),
            publisher_acl=dict(),
            pki_dir=pkiDirpath,
            sock_dir=sockDirpath,
            cachedir=cacheDirpath,
            open_mode=True,
            auto_accept=True,
            )

        name = "{0}_{1}".format(self.role, self.role)
        basedirpath = os.path.abspath(os.path.join(cacheDirpath, 'raet'))
        keep = salting.SaltKeep(opts=self.opts.value,
                                basedirpath=basedirpath,
                                stackname=name)
        keep.clearLocalData()
        keep.clearLocalRoleData()
        keep.clearAllRemoteData()
        keep.clearAllRemoteRoleData()


class TestOptsSetupMaster(TestOptsSetup):

    def action(self):
        self.role = 'master'
        self.raet_port = raeting.RAET_PORT
        super(TestOptsSetupMaster, self).action()


class TestOptsSetupMinion(TestOptsSetup):

    def action(self):
        self.role = 'minion'
        self.raet_port = raeting.RAET_TEST_PORT
        super(TestOptsSetupMinion, self).action()


def serviceRoads(stacks, duration=1.0):
    '''
    Utility method to service queues for list of stacks. Call from test method.
    '''
    start = time.time()
    while start + duration > time.time():
        for stack in stacks:
            stack.serviceAll()
        if all([not stack.transactions for stack in stacks]):
            console.terse("Service stacks done normally\n")
            break
        time.sleep(0.05)
    for stack in stacks:
        console.terse("Stack {0} remotes: {1}\n".format(stack.name, stack.nameRemotes))
    console.terse("Service stacks exit\n")


def serviceLanes(stacks, duration=1.0):
    '''
    Utility method to service queues for list of stacks. Call from test method.
    '''
    start = time.time()
    while start + duration > time.time():
        for stack in stacks:
            stack.serviceAll()
        if all([not stack.txMsgs for stack in stacks]):
            console.terse("Service stacks done normally\n")
            break
        time.sleep(0.05)
    for stack in stacks:
        console.terse("Stack {0} remotes: {1}\n".format(stack.name, stack.nameRemotes))
    console.terse("Service stacks exit\n")


class PresenterTestSetup(ioflo.base.deeding.Deed):
    '''
    Setup shares for presence tests
    '''
    Ioinits = {'presence_req': salt.utils.stringutils.to_str('.salt.presence.event_req'),
               'lane_stack': salt.utils.stringutils.to_str('.salt.lane.manor.stack'),
               'event_stack': salt.utils.stringutils.to_str('.salt.test.lane.stack'),
               'alloweds': {'ipath': salt.utils.stringutils.to_str('.salt.var.presence.alloweds'),
                            'ival': odict()},
               'aliveds': {'ipath': salt.utils.stringutils.to_str('.salt.var.presence.aliveds'),
                           'ival': odict()},
               'reapeds': {'ipath': salt.utils.stringutils.to_str('.salt.var.presence.reapeds'),
                           'ival': odict()},
               'availables': {'ipath': salt.utils.stringutils.to_str(
                                            '.salt.var.presence.availables'),
                              'ival': set()}}

    def action(self):

        self.presence_req.value = deque()
        self.availables.value = set()
        self.alloweds.value = odict()
        self.aliveds.value = odict()
        self.reapeds.value = odict()

        # Create event stack
        name = 'event' + nacling.uuid(size=18)
        lanename = self.lane_stack.value.local.lanename
        sock_dir = self.lane_stack.value.local.dirpath
        ryn = 'manor'
        console.terse("Create stack: name = {0}, lanename = {1}, sock_dir = {2}\n".
                      format(name, lanename, sock_dir))
        stack = LaneStack(
            name=name,
            lanename=lanename,
            sockdirpath=sock_dir)
        stack.addRemote(RemoteYard(stack=stack,
                                   lanename=lanename,
                                   name=ryn,
                                   dirpath=sock_dir))
        self.event_stack.value = stack

        route = {'dst': (None, ryn, 'presence_req'),
                 'src': (None, stack.local.name, None)}
        msg = {'route': route}
        stack.transmit(msg, stack.nameRemotes[ryn].uid)
        serviceLanes([stack, self.lane_stack.value])


class PresenterTestCleanup(ioflo.base.deeding.Deed):
    '''
    Clean up after a test
    '''
    Ioinits = {'presence_req': salt.utils.stringutils.to_str('.salt.presence.event_req'),
               'alloweds': {'ipath': salt.utils.stringutils.to_str('.salt.var.presence.alloweds'),
                            'ival': odict()},
               'aliveds': {'ipath': salt.utils.stringutils.to_str('.salt.var.presence.aliveds'),
                           'ival': odict()},
               'reapeds': {'ipath': salt.utils.stringutils.to_str('.salt.var.presence.reapeds'),
                           'ival': odict()},
               'availables': {'ipath': salt.utils.stringutils.to_str(
                                    '.salt.var.presence.availables'),
                              'ival': set()}}

    def action(self):

        self.presence_req.value = deque()
        self.availables.value = set()
        self.alloweds.value = odict()
        self.aliveds.value = odict()
        self.reapeds.value = odict()


class TestPresenceAvailable(ioflo.base.deeding.Deed):
    Ioinits = {'presence_req': salt.utils.stringutils.to_str('.salt.presence.event_req'),
               'event_stack': salt.utils.stringutils.to_str('.salt.test.lane.stack'),
               'aliveds': {'ipath': salt.utils.stringutils.to_str('.salt.var.presence.aliveds'),
                           'ival': odict()},
               'availables': {'ipath': salt.utils.stringutils.to_str(
                                    '.salt.var.presence.availables'),
                              'ival': set()}}

    def action(self):
        '''
        Test Presenter 'available' request (A1, B*)
        '''
        console.terse("{0}\n".format(self.action.__doc__))

        # Prepare
        # add available minions
        self.availables.value.add('alpha')
        self.availables.value.add('beta')
        self.aliveds.value['alpha'] = createStack('1.1.1.1')
        self.aliveds.value['beta'] = createStack('1.2.3.4')
        # add presence request
        testStack = self.event_stack.value
        presenceReq = self.presence_req.value
        ryn = 'manor'
        # general available request format
        presenceReq.append({'route': {'dst': (None, ryn, 'presence_req'),
                                      'src': (None, testStack.local.name, None)},
                            'data': {'state': 'available'}})
        # missing 'data', fallback to available
        presenceReq.append({'route': {'dst': (None, ryn, 'presence_req'),
                                      'src': (None, testStack.local.name, None)}})
        # missing 'state' in 'data', fallback to available
        presenceReq.append({'route': {'dst': (None, ryn, 'presence_req'),
                                      'src': (None, testStack.local.name, None)},
                            'data': {}})
        # requested None state, fallback to available
        presenceReq.append({'route': {'dst': (None, ryn, 'presence_req'),
                                      'src': (None, testStack.local.name, None)},
                            'data': {'state': None}})
        # requested 'present' state that is alias for available
        presenceReq.append({'route': {'dst': (None, ryn, 'presence_req'),
                                      'src': (None, testStack.local.name, None)},
                            'data': {'state': 'present'}})


class TestPresenceAvailableCheck(ioflo.base.deeding.Deed, DeedTestWrapper):
    Ioinits = {'event_stack': salt.utils.stringutils.to_str('.salt.test.lane.stack'),
               'failure': salt.utils.stringutils.to_str('.meta.failure')}

    def action(self):
        testStack = self.event_stack.value
        self.assertTrue(len(testStack.rxMsgs) == 0)
        testStack.serviceAll()
        self.assertTrue(len(testStack.rxMsgs) == 5)

        tag = tagify('present', 'presence')
        while testStack.rxMsgs:
            msg, sender = testStack.rxMsgs.popleft()
            self.assertTrue(msg == {'route': {'src': [None, 'manor', None],
                                              'dst': [None, None, 'event_fire']},
                                    'tag': tag,
                                    'data': {'present': {'alpha': '1.1.1.1',
                                                         'beta': '1.2.3.4'}}})


class TestPresenceJoined(ioflo.base.deeding.Deed):
    Ioinits = {'presence_req': salt.utils.stringutils.to_str('.salt.presence.event_req'),
               'event_stack': salt.utils.stringutils.to_str('.salt.test.lane.stack'),
               'alloweds': {'ipath': salt.utils.stringutils.to_str('.salt.var.presence.alloweds'),
                            'ival': odict()}}

    def action(self):
        '''
        Test Presenter 'joined' request (A2)
        '''
        console.terse("{0}\n".format(self.action.__doc__))

        # Prepare
        # add joined minions
        self.alloweds.value['alpha'] = createStack('1.1.1.1')
        self.alloweds.value['beta'] = createStack('1.2.3.4')
        # add presence request
        testStack = self.event_stack.value
        presenceReq = self.presence_req.value
        ryn = 'manor'
        presenceReq.append({'route': {'dst': (None, ryn, 'presence_req'),
                                      'src': (None, testStack.local.name, None)},
                            'data': {'state': 'joined'}})


class TestPresenceJoinedCheck(ioflo.base.deeding.Deed, DeedTestWrapper):
    Ioinits = {'event_stack': salt.utils.stringutils.to_str('.salt.test.lane.stack'),
               'failure': salt.utils.stringutils.to_str('.meta.failure')}

    def action(self):
        testStack = self.event_stack.value
        self.assertTrue(len(testStack.rxMsgs) == 0)
        testStack.serviceAll()
        self.assertTrue(len(testStack.rxMsgs) == 1)

        tag = tagify('present', 'presence')
        msg, sender = testStack.rxMsgs.popleft()
        self.assertTrue(msg == {'route': {'src': [None, 'manor', None],
                                          'dst': [None, None, 'event_fire']},
                                'tag': tag,
                                'data': {'joined': {'alpha': '1.1.1.1',
                                                    'beta': '1.2.3.4'}}})


class TestPresenceAllowed(ioflo.base.deeding.Deed):
    Ioinits = {'presence_req': salt.utils.stringutils.to_str('.salt.presence.event_req'),
               'event_stack': salt.utils.stringutils.to_str('.salt.test.lane.stack'),
               'alloweds': {'ipath': salt.utils.stringutils.to_str('.salt.var.presence.alloweds'),
                            'ival': odict()}}

    def action(self):
        '''
        Test Presenter 'allowed' request (A3)
        '''
        console.terse("{0}\n".format(self.action.__doc__))

        # Prepare
        # add allowed minions
        self.alloweds.value['alpha'] = createStack('1.1.1.1')
        self.alloweds.value['beta'] = createStack('1.2.3.4')
        # add presence request
        testStack = self.event_stack.value
        presenceReq = self.presence_req.value
        ryn = 'manor'
        presenceReq.append({'route': {'dst': (None, ryn, 'presence_req'),
                                      'src': (None, testStack.local.name, None)},
                            'data': {'state': 'allowed'}})


class TestPresenceAllowedCheck(ioflo.base.deeding.Deed, DeedTestWrapper):
    Ioinits = {'event_stack': salt.utils.stringutils.to_str('.salt.test.lane.stack'),
               'failure': salt.utils.stringutils.to_str('.meta.failure')}

    def action(self):
        testStack = self.event_stack.value
        self.assertTrue(len(testStack.rxMsgs) == 0)
        testStack.serviceAll()
        self.assertTrue(len(testStack.rxMsgs) == 1)

        tag = tagify('present', 'presence')
        msg, sender = testStack.rxMsgs.popleft()
        self.assertTrue(msg == {'route': {'src': [None, 'manor', None],
                                          'dst': [None, None, 'event_fire']},
                                'tag': tag,
                                'data': {'allowed': {'alpha': '1.1.1.1',
                                                     'beta': '1.2.3.4'}}})


class TestPresenceAlived(ioflo.base.deeding.Deed):
    Ioinits = {'presence_req': salt.utils.stringutils.to_str('.salt.presence.event_req'),
               'event_stack': salt.utils.stringutils.to_str('.salt.test.lane.stack'),
               'aliveds': {'ipath': salt.utils.stringutils.to_str('.salt.var.presence.aliveds'),
                            'ival': odict()}}

    def action(self):
        '''
        Test Presenter 'alived' request (A4)
        '''
        console.terse("{0}\n".format(self.action.__doc__))

        # Prepare
        # add alived minions
        self.aliveds.value['alpha'] = createStack('1.1.1.1')
        self.aliveds.value['beta'] = createStack('1.2.3.4')
        # add presence request
        testStack = self.event_stack.value
        presenceReq = self.presence_req.value
        ryn = 'manor'
        presenceReq.append({'route': {'dst': (None, ryn, 'presence_req'),
                                      'src': (None, testStack.local.name, None)},
                            'data': {'state': 'alived'}})


class TestPresenceAlivedCheck(ioflo.base.deeding.Deed, DeedTestWrapper):
    Ioinits = {'event_stack': salt.utils.stringutils.to_str('.salt.test.lane.stack'),
               'failure': salt.utils.stringutils.to_str('.meta.failure')}

    def action(self):
        testStack = self.event_stack.value
        self.assertTrue(len(testStack.rxMsgs) == 0)
        testStack.serviceAll()
        self.assertTrue(len(testStack.rxMsgs) == 1)

        tag = tagify('present', 'presence')
        msg, sender = testStack.rxMsgs.popleft()
        self.assertTrue(msg == {'route': {'src': [None, 'manor', None],
                                          'dst': [None, None, 'event_fire']},
                                'tag': tag,
                                'data': {'alived': {'alpha': '1.1.1.1',
                                                    'beta': '1.2.3.4'}}})


class TestPresenceReaped(ioflo.base.deeding.Deed):
    Ioinits = {'presence_req': salt.utils.stringutils.to_str('.salt.presence.event_req'),
               'event_stack': salt.utils.stringutils.to_str('.salt.test.lane.stack'),
               'reapeds': {'ipath': salt.utils.stringutils.to_str('.salt.var.presence.reapeds'),
                           'ival': odict()}}

    def action(self):
        '''
        Test Presenter 'reaped' request (A5)
        '''
        console.terse("{0}\n".format(self.action.__doc__))

        # Prepare
        # add reaped minions
        self.reapeds.value['alpha'] = createStack('1.1.1.1')
        self.reapeds.value['beta'] = createStack('1.2.3.4')
        # add presence request
        testStack = self.event_stack.value
        presenceReq = self.presence_req.value
        ryn = 'manor'
        presenceReq.append({'route': {'dst': (None, ryn, 'presence_req'),
                                      'src': (None, testStack.local.name, None)},
                            'data': {'state': 'reaped'}})


class TestPresenceReapedCheck(ioflo.base.deeding.Deed, DeedTestWrapper):
    Ioinits = {'event_stack': salt.utils.stringutils.to_str('.salt.test.lane.stack'),
               'failure': salt.utils.stringutils.to_str('.meta.failure')}

    def action(self):
        testStack = self.event_stack.value
        self.assertTrue(len(testStack.rxMsgs) == 0)
        testStack.serviceAll()
        self.assertTrue(len(testStack.rxMsgs) == 1)

        tag = tagify('present', 'presence')
        msg, sender = testStack.rxMsgs.popleft()
        self.assertTrue(msg == {'route': {'src': [None, 'manor', None],
                                          'dst': [None, None, 'event_fire']},
                                'tag': tag,
                                'data': {'reaped': {'alpha': '1.1.1.1',
                                                    'beta': '1.2.3.4'}}})


class TestPresenceNoRequest(ioflo.base.deeding.Deed):
    Ioinits = {}

    def action(self):
        '''
        Test Presenter with no requests (C1)
        '''
        console.terse("{0}\n".format(self.action.__doc__))


class TestPresenceNoRequestCheck(ioflo.base.deeding.Deed, DeedTestWrapper):
    Ioinits = {'event_stack': salt.utils.stringutils.to_str('.salt.test.lane.stack'),
               'failure': salt.utils.stringutils.to_str('.meta.failure')}

    def action(self):
        testStack = self.event_stack.value
        self.assertTrue(len(testStack.rxMsgs) == 0)
        testStack.serviceAll()
        self.assertTrue(len(testStack.rxMsgs) == 0)


class TestPresenceUnknownSrc(ioflo.base.deeding.Deed, DeedTestWrapper):
    Ioinits = {'presence_req': salt.utils.stringutils.to_str('.salt.presence.event_req'),
               'event_stack': salt.utils.stringutils.to_str('.salt.test.lane.stack'),
               'failure': salt.utils.stringutils.to_str('.meta.failure')}

    def action(self):
        '''
        Test Presenter handles request from unknown (disconnected) source (C2)
        '''
        console.terse("{0}\n".format(self.action.__doc__))

        # Prepare
        # add presence request
        testStack = self.event_stack.value
        presenceReq = self.presence_req.value
        ryn = 'manor'
        name = 'unknown_name'
        self.assertTrue(name != testStack.local.name)
        presenceReq.append({'route': {'dst': (None, ryn, 'presence_req'),
                                      'src': (None, name, None)}})


class TestPresenceUnknownSrcCheck(ioflo.base.deeding.Deed, DeedTestWrapper):
    Ioinits = {'event_stack': salt.utils.stringutils.to_str('.salt.test.lane.stack'),
               'failure': salt.utils.stringutils.to_str('.meta.failure')}

    def action(self):
        testStack = self.event_stack.value
        self.assertTrue(len(testStack.rxMsgs) == 0)
        testStack.serviceAll()
        self.assertTrue(len(testStack.rxMsgs) == 0)


class TestPresenceAvailableNoMinions(ioflo.base.deeding.Deed):
    Ioinits = {'presence_req': salt.utils.stringutils.to_str('.salt.presence.event_req'),
               'event_stack': salt.utils.stringutils.to_str('.salt.test.lane.stack')}

    def action(self):
        '''
        Test Presenter 'available' request with no minions in the state (D1)
        '''
        console.terse("{0}\n".format(self.action.__doc__))

        # Prepare
        # add presence request
        testStack = self.event_stack.value
        presenceReq = self.presence_req.value
        ryn = 'manor'
        presenceReq.append({'route': {'dst': (None, ryn, 'presence_req'),
                                      'src': (None, testStack.local.name, None)},
                            'data': {'state': 'available'}})


class TestPresenceAvailableNoMinionsCheck(ioflo.base.deeding.Deed, DeedTestWrapper):
    Ioinits = {'event_stack': salt.utils.stringutils.to_str('.salt.test.lane.stack'),
               'failure': salt.utils.stringutils.to_str('.meta.failure')}

    def action(self):
        testStack = self.event_stack.value
        self.assertTrue(len(testStack.rxMsgs) == 0)
        testStack.serviceAll()
        self.assertTrue(len(testStack.rxMsgs) == 1)

        tag = tagify('present', 'presence')
        while testStack.rxMsgs:
            msg, sender = testStack.rxMsgs.popleft()
            self.assertTrue(msg == {'route': {'src': [None, 'manor', None],
                                              'dst': [None, None, 'event_fire']},
                                    'tag': tag,
                                    'data': {'present': {}}})


class TestPresenceAvailableOneMinion(ioflo.base.deeding.Deed):
    Ioinits = {'presence_req': salt.utils.stringutils.to_str('.salt.presence.event_req'),
               'event_stack': salt.utils.stringutils.to_str('.salt.test.lane.stack'),
               'aliveds': {'ipath': salt.utils.stringutils.to_str('.salt.var.presence.aliveds'),
                           'ival': odict()},
               'availables': {'ipath': salt.utils.stringutils.to_str(
                                    '.salt.var.presence.availables'),
                              'ival': set()}}

    def action(self):
        '''
        Test Presenter 'available' request with one minions in the state (D2)
        '''
        console.terse("{0}\n".format(self.action.__doc__))

        # Prepare
        # add available minions
        self.availables.value.add('alpha')
        self.aliveds.value['alpha'] = createStack('1.1.1.1')
        # add presence request
        testStack = self.event_stack.value
        presenceReq = self.presence_req.value
        ryn = 'manor'
        presenceReq.append({'route': {'dst': (None, ryn, 'presence_req'),
                                      'src': (None, testStack.local.name, None)},
                            'data': {'state': 'available'}})


class TestPresenceAvailableOneMinionCheck(ioflo.base.deeding.Deed, DeedTestWrapper):
    Ioinits = {'event_stack': salt.utils.stringutils.to_str('.salt.test.lane.stack'),
               'failure': salt.utils.stringutils.to_str('.meta.failure')}

    def action(self):
        testStack = self.event_stack.value
        self.assertTrue(len(testStack.rxMsgs) == 0)
        testStack.serviceAll()
        self.assertTrue(len(testStack.rxMsgs) == 1)

        tag = tagify('present', 'presence')
        while testStack.rxMsgs:
            msg, sender = testStack.rxMsgs.popleft()
            self.assertTrue(msg == {'route': {'src': [None, 'manor', None],
                                              'dst': [None, None, 'event_fire']},
                                    'tag': tag,
                                    'data': {'present': {'alpha': '1.1.1.1'}}})


class TestPresenceAvailableUnknownIp(ioflo.base.deeding.Deed):
    Ioinits = {'presence_req': salt.utils.stringutils.to_str('.salt.presence.event_req'),
               'event_stack': salt.utils.stringutils.to_str('.salt.test.lane.stack'),
               'aliveds': {'ipath': salt.utils.stringutils.to_str('.salt.var.presence.aliveds'),
                           'ival': odict()},
               'availables': {'ipath': salt.utils.stringutils.to_str(
                                    '.salt.var.presence.availables'),
                              'ival': set()}}

    def action(self):
        '''
        Test Presenter 'available' request with one minions in the state (D3)
        '''
        console.terse("{0}\n".format(self.action.__doc__))

        # Prepare
        # add available minions
        self.availables.value.add('alpha')
        self.availables.value.add('beta')
        self.availables.value.add('gamma')
        self.aliveds.value['alpha'] = createStack('1.1.1.1')
        self.aliveds.value['delta'] = createStack('1.2.3.4')
        # add presence request
        testStack = self.event_stack.value
        presenceReq = self.presence_req.value
        ryn = 'manor'
        presenceReq.append({'route': {'dst': (None, ryn, 'presence_req'),
                                      'src': (None, testStack.local.name, None)},
                            'data': {'state': 'available'}})


class TestPresenceAvailableUnknownIpCheck(ioflo.base.deeding.Deed, DeedTestWrapper):
    Ioinits = {'event_stack': salt.utils.stringutils.to_str('.salt.test.lane.stack'),
               'failure': salt.utils.stringutils.to_str('.meta.failure')}

    def action(self):
        testStack = self.event_stack.value
        self.assertTrue(len(testStack.rxMsgs) == 0)
        testStack.serviceAll()
        self.assertTrue(len(testStack.rxMsgs) == 1)

        tag = tagify('present', 'presence')
        while testStack.rxMsgs:
            msg, sender = testStack.rxMsgs.popleft()
            self.assertTrue(msg == {'route': {'src': [None, 'manor', None],
                                              'dst': [None, None, 'event_fire']},
                                    'tag': tag,
                                    'data': {'present': {'alpha': '1.1.1.1',
                                                         'beta': None,
                                                         'gamma': None}}})


class TestPresenceAllowedNoMinions(ioflo.base.deeding.Deed):
    Ioinits = {'presence_req': salt.utils.stringutils.to_str('.salt.presence.event_req'),
               'event_stack': salt.utils.stringutils.to_str('.salt.test.lane.stack')}

    def action(self):
        '''
        Test Presenter 'allowed' request with no minions in the state (D4)
        '''
        console.terse("{0}\n".format(self.action.__doc__))

        # Prepare
        # add presence request
        testStack = self.event_stack.value
        presenceReq = self.presence_req.value
        ryn = 'manor'
        presenceReq.append({'route': {'dst': (None, ryn, 'presence_req'),
                                      'src': (None, testStack.local.name, None)},
                            'data': {'state': 'allowed'}})


class TestPresenceAllowedNoMinionsCheck(ioflo.base.deeding.Deed, DeedTestWrapper):
    Ioinits = {'event_stack': salt.utils.stringutils.to_str('.salt.test.lane.stack'),
               'failure': salt.utils.stringutils.to_str('.meta.failure')}

    def action(self):
        testStack = self.event_stack.value
        self.assertTrue(len(testStack.rxMsgs) == 0)
        testStack.serviceAll()
        self.assertTrue(len(testStack.rxMsgs) == 1)

        tag = tagify('present', 'presence')
        msg, sender = testStack.rxMsgs.popleft()
        self.assertTrue(msg == {'route': {'src': [None, 'manor', None],
                                          'dst': [None, None, 'event_fire']},
                                'tag': tag,
                                'data': {'allowed': {}}})


class TestPresenceAllowedOneMinion(ioflo.base.deeding.Deed):
    Ioinits = {'presence_req': salt.utils.stringutils.to_str('.salt.presence.event_req'),
               'event_stack': salt.utils.stringutils.to_str('.salt.test.lane.stack'),
               'alloweds': {'ipath': salt.utils.stringutils.to_str('.salt.var.presence.alloweds'),
                            'ival': odict()}}

    def action(self):
        '''
        Test Presenter 'allowed' request with one minion in the state (D5)
        '''
        console.terse("{0}\n".format(self.action.__doc__))

        # Prepare
        # add allowed minion
        self.alloweds.value['alpha'] = createStack('1.1.1.1')
        # add presence request
        testStack = self.event_stack.value
        presenceReq = self.presence_req.value
        ryn = 'manor'
        presenceReq.append({'route': {'dst': (None, ryn, 'presence_req'),
                                      'src': (None, testStack.local.name, None)},
                            'data': {'state': 'allowed'}})


class TestPresenceAllowedOneMinionCheck(ioflo.base.deeding.Deed, DeedTestWrapper):
    Ioinits = {'event_stack': salt.utils.stringutils.to_str('.salt.test.lane.stack'),
               'failure': salt.utils.stringutils.to_str('.meta.failure')}

    def action(self):
        testStack = self.event_stack.value
        self.assertTrue(len(testStack.rxMsgs) == 0)
        testStack.serviceAll()
        self.assertTrue(len(testStack.rxMsgs) == 1)

        tag = tagify('present', 'presence')
        msg, sender = testStack.rxMsgs.popleft()
        self.assertTrue(msg == {'route': {'src': [None, 'manor', None],
                                          'dst': [None, None, 'event_fire']},
                                'tag': tag,
                                'data': {'allowed': {'alpha': '1.1.1.1'}}})


class StatsMasterTestSetup(ioflo.base.deeding.Deed):
    '''
    Setup shares for stats tests
    '''
    Ioinits = {'stats_req': salt.utils.stringutils.to_str('.salt.stats.event_req'),
               'lane_stack': salt.utils.stringutils.to_str('.salt.lane.manor.stack'),
               'road_stack': salt.utils.stringutils.to_str('.salt.road.manor.stack'),
               'event_stack': salt.utils.stringutils.to_str('.salt.test.lane.stack')}

    def action(self):

        self.stats_req.value = deque()

        # Create event stack
        name = 'event' + nacling.uuid(size=18)
        lanename = self.lane_stack.value.local.lanename
        sock_dir = self.lane_stack.value.local.dirpath
        ryn = 'manor'
        console.terse("Create stack: name = {0}, lanename = {1}, sock_dir = {2}\n".
                      format(name, lanename, sock_dir))
        stack = LaneStack(
            name=name,
            lanename=lanename,
            sockdirpath=sock_dir)
        stack.addRemote(RemoteYard(stack=stack,
                                   lanename=lanename,
                                   name=ryn,
                                   dirpath=sock_dir))
        self.event_stack.value = stack

        route = {'dst': (None, ryn, 'stats_req'),
                 'src': (None, stack.local.name, None)}
        msg = {'route': route}
        stack.transmit(msg, stack.nameRemotes[ryn].uid)
        serviceLanes([stack, self.lane_stack.value])


class StatsMinionTestSetup(ioflo.base.deeding.Deed):
    '''
    Setup shares for stats tests
    '''
    Ioinits = {'stats_req': salt.utils.stringutils.to_str('.salt.stats.event_req'),
               'lane_stack': salt.utils.stringutils.to_str('.salt.lane.manor.stack'),
               'road_stack': salt.utils.stringutils.to_str('.salt.road.manor.stack'),
               'event_stack': salt.utils.stringutils.to_str('.salt.test.road.stack')}

    def action(self):

        self.stats_req.value = deque()

        minionStack = self.road_stack.value

        # Create Master Stack
        self.store.stamp = 0.0
        masterStack = RoadStack(store=self.store,
                                name='master',
                                ha=('', raeting.RAET_PORT),
                                role='master',
                                main=True,
                                cleanremote=True,
                                period=3.0,
                                offset=0.5)
        self.event_stack.value = masterStack

        minionRemoteMaster = RemoteEstate(stack=minionStack,
                                          fuid=0,
                                          sid=0,
                                          ha=masterStack.local.ha)
        minionStack.addRemote(minionRemoteMaster)

        # Make life easier
        masterStack.keep.auto = raeting.AutoMode.always.value
        minionStack.keep.auto = raeting.AutoMode.always.value

        minionStack.join(minionRemoteMaster.uid)
        serviceRoads([minionStack, masterStack])
        minionStack.allow(minionRemoteMaster.uid)
        serviceRoads([minionStack, masterStack])
