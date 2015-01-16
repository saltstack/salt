# -*- coding: utf-8 -*-
'''
Test behaviors used by test plans
'''
# pylint: disable=W0232

import os
import stat
import time
from collections import deque

# Import ioflo libs
import ioflo.base.deeding
from ioflo.base.odicting import odict

from ioflo.base.consoling import getConsole
console = getConsole()

from raet import nacling
from raet.lane.stacking import LaneStack
from raet.lane.yarding import RemoteYard


class SaltRaetTestOptsSetup(ioflo.base.deeding.Deed):
    '''
    Fire presence events!
    FloScript:

    do salt raet presenter

    '''
    Ioinits = {'opts': '.salt.opts',
               'presence_req': '.salt.presence.event_req',
               'lane_stack': '.salt.lane.manor.stack',
               'event_stack': '.salt.test.lane.stack',
               'aliveds': {'ipath': '.salt.var.presence.aliveds',
                           'ival': odict()},
               'availables': {'ipath': '.salt.var.presence.availables',
                              'ival': set()},
               'is_done': '.is_done'}

    def action(self):
        '''
        Register presence requests
        Iterate over the registered presence yards and fire!
        '''
        pkiDirpath = os.path.join('/tmp', 'raet', 'test', 'master', 'pki')
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

        cacheDirpath = os.path.join('/tmp/raet', 'cache', 'master')
        if not os.path.exists(cacheDirpath):
            os.makedirs(cacheDirpath)

        sockDirpath = os.path.join('/tmp/raet', 'sock', 'master')
        if not os.path.exists(sockDirpath):
            os.makedirs(sockDirpath)

        self.opts.value = dict(
            id='master',
            __role='master',
            ioflo_period=0.1,
            ioflo_realtime=True,
            ioflo_verbose=2,
            interface="",
            raet_port=7530,
            transport='raet',
            client_acl=dict(),
            pki_dir=pkiDirpath,
            sock_dir=sockDirpath,
            cachedir=cacheDirpath,
            open_mode=True,
            auto_accept=True,
            )
        return True

def serviceStacks(stacks, duration=1.0):
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

class SaltRaetPresenterTestSetup(ioflo.base.deeding.Deed):
    '''
    Fire presence events!
    FloScript:

    do salt raet presenter

    '''
    Ioinits = {'opts': '.salt.opts',
               'presence_req': '.salt.presence.event_req',
               'lane_stack': '.salt.lane.manor.stack',
               'event_stack': '.salt.test.lane.stack',
               'alloweds': {'ipath': '.salt.var.presence.alloweds',
                            'ival': odict()},
               'aliveds': {'ipath': '.salt.var.presence.aliveds',
                           'ival': odict()},
               'reapeds': {'ipath': '.salt.var.presence.reapeds',
                           'ival': odict()},
               'availables': {'ipath': '.salt.var.presence.availables',
                              'ival': set()},
               'is_done': '.is_done'}

    def action(self):

        self.presence_req.value = deque()
        self.availables.value = set()
        self.alloweds.value = odict()
        self.aliveds.value = odict()
        self.reapeds.value = odict()

        self.is_done.value = False

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
        serviceStacks([stack, self.lane_stack.value])
        return True

