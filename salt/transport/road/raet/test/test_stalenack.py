# -*- coding: utf-8 -*-
'''
Tests to try out stacking. Potentially ephemeral

'''
# pylint: skip-file

import  os

from ioflo.base.odicting import odict
from ioflo.base.aiding import Timer,  StoreTimer
from ioflo.base import storing

from ioflo.base.consoling import getConsole
console = getConsole()

from salt.transport.road.raet import (raeting, nacling, packeting, keeping,
                                     estating, yarding, transacting, stacking)


def test():
    '''
    initially
    master on port 7530 with eid of 1
    minion on port 7531 with eid of 0
    eventually
    master eid of 1
    minion eid of 2
    '''
    console.reinit(verbosity=console.Wordage.concise)

    store = storing.Store(stamp=0.0)

    #master stack
    masterName = "master"
    signer = nacling.Signer()
    masterSignKeyHex = signer.keyhex
    privateer = nacling.Privateer()
    masterPriKeyHex = privateer.keyhex
    dirpathMaster = os.path.join(os.getcwd(), 'keep', masterName)

    #minion0 stack
    minionName0 = "minion0"
    signer = nacling.Signer()
    minionSignKeyHex = signer.keyhex
    privateer = nacling.Privateer()
    minionPriKeyHex = privateer.keyhex
    dirpathMinion0 = os.path.join(os.getcwd(), 'keep', minionName0)

    keeping.clearAllRoadSafe(dirpathMaster)
    keeping.clearAllRoadSafe(dirpathMinion0)

    estate = estating.LocalEstate(   eid=1,
                                     name=masterName,
                                     sigkey=masterSignKeyHex,
                                     prikey=masterPriKeyHex,)
    stack0 = stacking.StackUdp(estate=estate,
                               store=store,
                               auto=True,
                               main=True,
                               dirpath=dirpathMaster)


    estate = estating.LocalEstate(   eid=0,
                                     name=minionName0,
                                     ha=("", raeting.RAET_TEST_PORT),
                                     sigkey=minionSignKeyHex,
                                     prikey=minionPriKeyHex,)
    stack1 = stacking.StackUdp(estate=estate,
                               store=store,
                               dirpath=dirpathMinion0)


    print "\n********* Join Transaction **********"
    stack1.join()
    timer = Timer(duration=2)
    timer.restart(duration=2)
    while not timer.expired:
        stack1.serviceAll()
        stack0.serviceAll()
    for estate in stack0.estates.values():
        print "Remote Estate {0} joined= {1}".format(estate.eid, estate.joined)
    for estate in stack1.estates.values():
        print "Remote Estate {0} joined= {1}".format(estate.eid, estate.joined)

    print "\n********* Allow Transaction **********"
    stack1.allow()
    timer.restart(duration=2)
    while not timer.expired:
        stack1.serviceAll()
        stack0.serviceAll()
        store.advanceStamp(0.1)

    for estate in stack0.estates.values():
        print "Remote Estate {0} allowed= {1}".format(estate.eid, estate.allowed)
    for estate in stack1.estates.values():
        print "Remote Estate {0} allowed= {1}".format(estate.eid, estate.allowed)

    print "\n********* Message Transactions Both Ways **********"
    #stack1.transmit(odict(house="Oh Boy1", queue="Nice"))
    stack0.transmit(odict(house="Yeah Baby1", queue="Good"))

    timer.restart(duration=1)
    while not timer.expired:
        stack0.serviceTx()

    timer.restart(duration=1)
    while not timer.expired:
        stack1.serviceRx()

    print "{0} Received Messages".format(stack1.name)
    for msg in stack1.rxMsgs:
            print msg
    print

    stack0.transactions = odict() #clear transactions

    timer.restart(duration=2)
    while not timer.expired:
        stack1.serviceTx()
        stack0.serviceRx()

    print "{0} Received Messages".format(stack0.name)
    for msg in stack0.rxMsgs:
        print msg
    print

    print "{0} Stats".format(stack0.name)
    for key, val in stack0.stats.items():
        print "   {0}={1}".format(key, val)
    print
    print "{0} Stats".format(stack1.name)
    for key, val in stack1.stats.items():
        print "   {0}={1}".format(key, val)
    print


    stack0.server.close()
    stack1.server.close()

    stack0.clearLocal()
    stack0.clearAllRemote()
    stack1.clearLocal()
    stack1.clearAllRemote()


if __name__ == "__main__":
    test()

