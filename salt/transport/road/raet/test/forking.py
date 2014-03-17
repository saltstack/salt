# -*- coding: utf-8 -*-
'''
Test basic uxd stacking and yarding with multiprocesses
'''
import multiprocessing
import time

from salt.transport.road.raet import stacking
from salt.transport.road.raet import yarding

ESTATE = 'minion1'


def fudal():
    '''
    Make a single process raet uxd stack
    '''
    lord_stack = stacking.StackUxd(name='lord', lanename='execute', yid=0, dirpath='/tmp')
    serf_stack = stacking.StackUxd(name='serf', lanename='execute', yid=1, dirpath='/tmp')
    lord_yard = yarding.Yard(yid=0, prefix='execute', dirpath='/tmp')
    #serf_yard = yarding.Yard(name=serf_stack.yard.name, prefix='execute')
    serf_stack.addRemoteYard(lord_yard)
    #print 'stack: {0}\nyid: {1}\nname: {2}\nha: {3}\ndirpath: {4}'.format(lord_stack.yard.stack, lord_stack.yard.yid, lord_stack.yard.name, lord_stack.yard.ha, lord_stack.yard.dirpath)
    #lord_stack.addRemoteYard(serf_yard)

    src = (ESTATE, serf_stack.yard.name, None)
    dst = (ESTATE, lord_stack.yard.name, None)

    route = {'src': src, 'dst': dst}
    msg = {'route': route, 'stuff': 'Serf to Lord, I am not a couch'}

    serf_stack.transmit(msg=msg)

    serf_stack.serviceAll()
    lord_stack.serviceAll()
    #print lord_stack.rxMsgs


def lord(serfs=5):
    '''
    Make a lord that can spawn serfs
    '''
    lord_yid = 0
    dirpath = '/tmp'
    lord_stack = stacking.StackUxd(name='lord', lanename='execute', yid=lord_yid, dirpath=dirpath)
    lord_stack.serviceAll()
    for serf_id in range(1, serfs + 1):
        serf_yard = yarding.Yard(yid=serf_id, prefix='execute', dirpath=dirpath)
        lord_stack.addRemoteYard(serf_yard)
        proc = multiprocessing.Process(target=serf, args=(lord_stack.yard.name, lord_yid, serf_id, dirpath))
        proc.start()

    while True:
        lord_stack.serviceAll()
        print 'serviced lord stack'
        print lord_stack.rxMsgs
        while lord_stack.rxMsgs:
            rxmsg = lord_stack.rxMsgs.popleft()
            print rxmsg
            src = (ESTATE, lord_stack.yard.name, None)
            dst = (ESTATE, rxmsg['route']['src'][1], None)
            route = {'src': src, 'dst': dst}
            msg = {'route': route, 'stuff': 'Master to Serf {0}, you stay'.format(rxmsg['route']['src'][1])}
            lord_stack.transmit(msg)
        print lord_stack.yards
        time.sleep(1)


def serf(lord_name, lord_yid, id_, dirpath):
    '''
    Call to spawn a serf and start sending messages
    '''
    serf_stack = stacking.StackUxd(
            name='serf{0}'.format(id_),
            lanename='execute',
            yid=id_,
            dirpath=dirpath)
    lord_yard = yarding.Yard(yid=lord_yid, prefix='execute', dirpath=dirpath)
    serf_stack.addRemoteYard(lord_yard)
    src = (ESTATE, serf_stack.yard.name, None)
    dst = (ESTATE, lord_name, None)
    route = {'src': src, 'dst': dst}
    msg = {'route': route, 'stuff': 'Serf {0} to Lord, I am not a couch'.format(id_)}
    while True:
        serf_stack.transmit(msg=msg)
        serf_stack.serviceAll()
        print 'serf messages transmitted'
        while serf_stack.rxMsgs:
            print serf_stack.rxMsgs.popleft()
        time.sleep(1)

if __name__ == '__main__':
    lord()
    #fudal()
