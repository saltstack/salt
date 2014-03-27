# -*- coding: utf-8 -*-
'''
Tests to try out stacking. Potentially ephemeral

'''
# pylint: skip-file

import  os
import  time

from ioflo.base.odicting import odict
from ioflo.base.aiding import Timer, StoreTimer
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
    masterDirpath = os.path.join(os.getcwd(), 'keep', masterName)

    #minion0 stack
    minionName0 = "minion0"
    signer = nacling.Signer()
    minionSignKeyHex = signer.keyhex
    privateer = nacling.Privateer()
    minionPriKeyHex = privateer.keyhex
    m0Dirpath = os.path.join(os.getcwd(), 'keep', minionName0)

    keeping.clearAllRoadSafe(masterDirpath)
    keeping.clearAllRoadSafe(m0Dirpath)


    estate = estating.LocalEstate(  eid=1,
                                    name=masterName,
                                    sigkey=masterSignKeyHex,
                                    prikey=masterPriKeyHex,)
    stack0 = stacking.StackUdp(name=masterName,
                               estate=estate,
                               store=store,
                               main=True,
                               dirpath=masterDirpath)


    estate = estating.LocalEstate(  eid=0,
                                    name=minionName0,
                                    ha=("", raeting.RAET_TEST_PORT),
                                    sigkey=minionSignKeyHex,
                                    prikey=minionPriKeyHex,)
    stack1 = stacking.StackUdp(name=minionName0,
                               estate=estate,
                               store=store,
                               dirpath=m0Dirpath)


    print "\n********* Join Transaction **********"
    stack1.join()
    #timer = StoreTimer(store=store, duration=3.0)
    while store.stamp < 2.0:
        stack1.serviceAll()
        stack0.serviceAll()
        if store.stamp >= 0.3:
            for estate in stack0.estates.values():
                if estate.acceptance == raeting.acceptances.pending:
                    stack0.safe.acceptRemoteEstate(estate)
        store.advanceStamp(0.1)
        time.sleep(0.1)

    for estate in stack0.estates.values():
        print "Remote Estate {0} joined= {1}".format(estate.eid, estate.joined)
    for estate in stack1.estates.values():
        print "Remote Estate {0} joined= {1}".format(estate.eid, estate.joined)


    print "{0} eid={1}".format(stack0.name, stack0.estate.eid)
    print "{0} estates=\n{1}".format(stack0.name, stack0.estates)
    print "{0} transactions=\n{1}".format(stack0.name, stack0.transactions)
    print "{0} eid={1}".format(stack1.name, stack1.estate.eid)
    print "{0} estates=\n{1}".format(stack1.name, stack1.estates)
    print "{0} transactions=\n{1}".format(stack1.name, stack1.transactions)


    print "Road {0}".format(stack0.name)
    print stack0.road.loadLocalData()
    print stack0.road.loadAllRemoteData()
    print "Safe {0}".format(stack0.name)
    print stack0.safe.loadLocalData()
    print stack0.safe.loadAllRemoteData()
    print

    print "Road {0}".format(stack1.name)
    print stack1.road.loadLocalData()
    print stack1.road.loadAllRemoteData()
    print "Safe {0}".format(stack1.name)
    print stack1.safe.loadLocalData()
    print stack1.safe.loadAllRemoteData()
    print


    print "\n********* Allow Transaction **********"
    if not stack1.estates.values()[0].joined:
        return
    stack1.allow()
    #timer = StoreTimer(store=store, duration=3.0)
    while store.stamp < 4.0:
        stack1.serviceAll()
        stack0.serviceAll()
        store.advanceStamp(0.1)
        time.sleep(0.1)

    for estate in stack0.estates.values():
        print "Remote Estate {0} allowed= {1}".format(estate.eid, estate.allowed)
    for estate in stack1.estates.values():
        print "Remote Estate {0} allowed= {1}".format(estate.eid, estate.allowed)


    print "{0} eid={1}".format(stack0.name, stack0.estate.eid)
    print "{0} estates=\n{1}".format(stack0.name, stack0.estates)
    print "{0} transactions=\n{1}".format(stack0.name, stack0.transactions)
    print "{0} eid={1}".format(stack1.name, stack1.estate.eid)
    print "{0} estates=\n{1}".format(stack1.name, stack1.estates)
    print "{0} transactions=\n{1}".format(stack1.name, stack1.transactions)

    #while stack1.transactions or stack0.transactions:
        #stack1.serviceAll()
        #stack0.serviceAll()
        #store.advanceStamp(0.1)

    print "{0} Stats".format(stack0.name)
    for key, val in stack0.stats.items():
        print "   {0}={1}".format(key, val)
    print
    print "{0} Stats".format(stack1.name)
    for key, val in stack1.stats.items():
        print "   {0}={1}".format(key, val)
    print

    print "\n********* Message Transactions Both Ways Again **********"

    #stack1.transmit(odict(house="Oh Boy1", queue="Nice"))
    #stack1.transmit(odict(house="Oh Boy2", queue="Mean"))
    #stack1.transmit(odict(house="Oh Boy3", queue="Ugly"))
    #stack1.transmit(odict(house="Oh Boy4", queue="Pretty"))

    #stack0.transmit(odict(house="Yeah Baby1", queue="Good"))
    #stack0.transmit(odict(house="Yeah Baby2", queue="Bad"))
    #stack0.transmit(odict(house="Yeah Baby3", queue="Fast"))
    #stack0.transmit(odict(house="Yeah Baby4", queue="Slow"))

    #segmented packets
    stuff = []
    for i in range(300):
        stuff.append(str(i).rjust(10, " "))
    stuff = "".join(stuff)

    stack1.transmit(odict(house="Snake eyes", queue="near stuff", stuff=stuff))
    stack0.transmit(odict(house="Craps", queue="far stuff", stuff=stuff))

    #timer.restart(duration=3)
    while  store.stamp < 8.0: #not timer.expired
        stack1.serviceAll()
        stack0.serviceAll()
        store.advanceStamp(0.1)
        time.sleep(0.1)


    print "{0} eid={1}".format(stack0.name, stack0.estate.eid)
    print "{0} estates=\n{1}".format(stack0.name, stack0.estates)
    print "{0} transactions=\n{1}".format(stack0.name, stack0.transactions)
    print "{0} Received Messages".format(stack0.name)
    for msg in stack0.rxMsgs:
        print msg
    print "{0} Stats".format(stack0.name)
    for key, val in stack0.stats.items():
        print "   {0}={1}".format(key, val)
    print
    print "{0} eid={1}".format(stack1.name, stack1.estate.eid)
    print "{0} estates=\n{1}".format(stack1.name, stack1.estates)
    print "{0} transactions=\n{1}".format(stack1.name, stack1.transactions)
    print "{0} Received Messages".format(stack1.name)
    for msg in stack1.rxMsgs:
            print msg
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
