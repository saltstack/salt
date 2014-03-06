# -*- coding: utf-8 -*-
'''
Tests to try out stacking. Potentially ephemeral

'''
# pylint: skip-file

import  os

from ioflo.base.odicting import odict
from ioflo.base.aiding import Timer

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

    #master stack
    masterName = "master"
    signer = nacling.Signer()
    masterSignKeyHex = signer.keyhex
    privateer = nacling.Privateer()
    masterPriKeyHex = privateer.keyhex

    dirpathMaster = os.path.join(os.getcwd(), 'keep', masterName)
    road = keeping.RoadKeep(dirpath=dirpathMaster)
    road.clearLocalData()
    road.clearAllRemoteData()
    safe = keeping.SafeKeep(dirpath=dirpathMaster)
    safe.clearLocalData()
    safe.clearAllRemoteData()
    estate = estating.LocalEstate(   eid=1,
                                     name=masterName,
                                     sigkey=masterSignKeyHex,
                                     prikey=masterPriKeyHex,)
    stack0 = stacking.StackUdp(estate=estate, main=True,  dirpath=dirpathMaster)

    #minion0 stack
    minionName0 = "minion0"
    signer = nacling.Signer()
    minionSignKeyHex = signer.keyhex
    privateer = nacling.Privateer()
    minionPriKeyHex = privateer.keyhex

    dirpathMinion0 = os.path.join(os.getcwd(), 'keep', minionName0)
    road = keeping.RoadKeep(dirpath=dirpathMinion0)
    road.clearLocalData()
    road.clearAllRemoteData()
    safe = keeping.SafeKeep(dirpath=dirpathMinion0)
    safe.clearLocalData()
    safe.clearAllRemoteData()
    estate = estating.LocalEstate(   eid=0,
                                     name=minionName0,
                                     ha=("", raeting.RAET_TEST_PORT),
                                     sigkey=minionSignKeyHex,
                                     prikey=minionPriKeyHex,)
    stack1 = stacking.StackUdp(estate=estate,  dirpath=dirpathMinion0)

    #minion1 stack
    minionName1 = "minion1"
    signer = nacling.Signer()
    minionSignKeyHex = signer.keyhex
    privateer = nacling.Privateer()
    minionPriKeyHex = privateer.keyhex

    dirpathMinion1 = os.path.join(os.getcwd(), 'keep', minionName1)
    road = keeping.RoadKeep(dirpath=dirpathMinion1)
    road.clearLocalData()
    road.clearAllRemoteData()
    safe = keeping.SafeKeep(dirpath=dirpathMinion1)
    safe.clearLocalData()
    safe.clearAllRemoteData()
    estate = estating.LocalEstate(   eid=0,
                                     name=minionName1,
                                     ha=("", 7532),
                                     sigkey=minionSignKeyHex,
                                     prikey=minionPriKeyHex,)
    stack2 = stacking.StackUdp(estate=estate,  dirpath=dirpathMinion1)

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
    for estate in stack0.estates.values():
        print "Remote Estate {0} allowed= {1}".format(estate.eid, estate.allowed)
    for estate in stack1.estates.values():
        print "Remote Estate {0} allowed= {1}".format(estate.eid, estate.allowed)

    print "\n********* Message Transactions Both Ways **********"
    stack1.transmit(odict(house="Oh Boy1", queue="Nice"))
    stack1.transmit(odict(house="Oh Boy2", queue="Mean"))
    stack1.transmit(odict(house="Oh Boy3", queue="Ugly"))
    stack1.transmit(odict(house="Oh Boy4", queue="Pretty"))

    stack0.transmit(odict(house="Yeah Baby1", queue="Good"))
    stack0.transmit(odict(house="Yeah Baby2", queue="Bad"))
    stack0.transmit(odict(house="Yeah Baby3", queue="Fast"))
    stack0.transmit(odict(house="Yeah Baby4", queue="Slow"))

    #segmented packets
    stuff = []
    for i in range(300):
        stuff.append(str(i).rjust(4, " "))
    stuff = "".join(stuff)

    stack1.transmit(odict(house="Snake eyes", queue="near stuff", stuff=stuff))
    stack0.transmit(odict(house="Craps", queue="far stuff", stuff=stuff))

    timer.restart(duration=2)
    while not timer.expired:
        stack1.serviceAll()
        stack0.serviceAll()

    print "{0} Received Messages".format(stack0.name)
    for msg in stack0.rxMsgs:
        print msg
    print
    print "{0} Received Messages".format(stack1.name)
    for msg in stack1.rxMsgs:
            print msg
    print

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

    stack0.serverUdp.close()
    stack1.serverUdp.close()
    stack2.serverUdp.close()

    #estate0 = stack0.loadLocal()
    #print estate0.name, estate0.eid, estate0.sid, estate0.ha, estate0.signer, estate0.priver
    #estate1 = stack1.loadLocal()
    #print estate1.name, estate1.eid, estate1.sid, estate1.ha, estate1.signer, estate1.priver

    #master stack
    stack0 = stacking.StackUdp(dirpath=dirpathMaster,  main=True)

    #minion0 stack
    stack1 = stacking.StackUdp(dirpath=dirpathMinion0)

    #minion1 stack
    stack2 = stacking.StackUdp(dirpath=dirpathMinion1)

    print "\n********* Join Transaction **********"
    stack1.join()
    stack2.join()
    timer = Timer(duration=2)
    timer.restart(duration=2)
    while not timer.expired:
        stack1.serviceAll()
        stack2.serviceAll()
        stack0.serviceAll()
    for estate in stack0.estates.values():
        print "{0} Remote Estate {1} joined= {2}".format(
            stack0.name, estate.eid, estate.joined)
    for estate in stack1.estates.values():
        print "{0} Remote Estate {1} joined= {2}".format(
            stack1.name, estate.eid, estate.joined)
    for estate in stack2.estates.values():
        print "{0} Remote Estate {1} joined= {2}".format(
            stack2.name, estate.eid, estate.joined)

    print "\n********* Allow Transaction **********"
    stack1.allow()
    stack2.allow()
    timer.restart(duration=2)
    while not timer.expired:
        stack1.serviceAll()
        stack2.serviceAll()
        stack0.serviceAll()
    for estate in stack0.estates.values():
        print "{0} Remote Estate {1} allowed= {2}".format(
            stack1.name, estate.eid, estate.allowed)
    for estate in stack1.estates.values():
        print "{0} Remote Estate {1} allowed= {2}".format(
            stack1.name, estate.eid, estate.allowed)
    for estate in stack2.estates.values():
        print "{0} Remote Estate {1} allowed= {2}".format(
            stack2.name, estate.eid, estate.allowed)

    print "\n********* Message Transactions Both Ways **********"
    #console.reinit(verbosity=console.Wordage.verbose)

    stack1.transmit(odict(house="Oh Boy1", queue="Nice"))
    stack1.transmit(odict(house="Oh Boy2", queue="Mean"))
    stack1.transmit(odict(house="Oh Boy3", queue="Ugly"))
    stack1.transmit(odict(house="Oh Boy4", queue="Pretty"))

    stack2.transmit(odict(house="Really 1", queue="blue"))
    stack2.transmit(odict(house="Really 2", queue="green"))
    stack2.transmit(odict(house="Really 3", queue="red"))
    stack2.transmit(odict(house="Really 4", queue="yello"))

    stack0.transmit(odict(house="Yeah Baby1", queue="Good"))
    stack0.transmit(odict(house="Yeah Baby2", queue="Bad"))
    stack0.transmit(odict(house="Yeah Baby3", queue="Fast"))
    stack0.transmit(odict(house="Yeah Baby4", queue="Slow"))

    stack0.transmit(odict(house="Yeah Momma 1", queue="host"), stack2.estate.eid)
    stack0.transmit(odict(house="Yeah Momma 1", queue="cold"),  stack2.estate.eid)
    stack0.transmit(odict(house="Yeah Momma 1", queue="boiling"),  stack2.estate.eid)
    stack0.transmit(odict(house="Yeah Momma 1", queue="tepid"),  stack2.estate.eid)

    # segmented packets
    stuff = []
    for i in range(300):
        stuff.append(str(i).rjust(4, " "))
    stuff = "".join(stuff)

    stack1.transmit(odict(house="Snake eyes", queue="near stuff", stuff=stuff))
    stack0.transmit(odict(house="Craps", queue="far stuff", stuff=stuff))
    stack2.transmit(odict(house="Lucky duck", queue="medium stuff", stuff=stuff))
    stack0.transmit(odict(house="Boogle", queue="hight stuff", stuff=stuff), stack2.estate.eid)

    timer.restart(duration=4)
    while not timer.expired:
        stack1.serviceAll()
        stack2.serviceAll()
        stack0.serviceAll()

    print "{0} Received Messages".format(stack0.name)
    for msg in stack0.rxMsgs:
        print msg
    print
    print "{0} Received Messages".format(stack1.name)
    for msg in stack1.rxMsgs:
            print msg
    print
    print "{0} Received Messages".format(stack2.name)
    for msg in stack2.rxMsgs:
            print msg
    print


    print "{0} eid={1}".format(stack0.name, stack0.estate.eid)
    print "{0} estates=\n{1}".format(stack0.name, stack0.estates)
    print "{0} transactions=\n{1}".format(stack0.name, stack0.transactions)
    print "{0} eid={1}".format(stack1.name, stack1.estate.eid)
    print "{0} estates=\n{1}".format(stack1.name, stack1.estates)
    print "{0} transactions=\n{1}".format(stack1.name, stack1.transactions)
    print "{0} eid={1}".format(stack2.name, stack2.estate.eid)
    print "{0} estates=\n{1}".format(stack2.name, stack2.estates)
    print "{0} transactions=\n{1}".format(stack2.name, stack2.transactions)

    stack0.serverUdp.close()
    stack1.serverUdp.close()
    stack2.serverUdp.close()

    #stack0.clearLocal()
    #stack0.clearAllRemote()
    stack1.clearLocal()
    stack1.clearAllRemote()
    stack2.clearLocal()
    stack2.clearAllRemote()


if __name__ == "__main__":
    test()

