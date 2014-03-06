# -*- coding: utf-8 -*-
'''
Tests to try out stacking. Potentially ephemeral

'''
# pylint: skip-file
from ioflo.base.odicting import odict
from ioflo.base.aiding import Timer

from ioflo.base.consoling import getConsole
console = getConsole()

from salt.transport.road.raet import (raeting, nacling, packeting,
                                     estating, yarding, transacting, stacking)


def testStackUxd(kind=raeting.packKinds.json):
    '''
    initially


    '''
    console.reinit(verbosity=console.Wordage.verbose)

    stacking.StackUxd.Pk = kind

    #lord stack
    #yard0 = yarding.Yard(name='lord')
    stack0 = stacking.StackUxd()

    #serf stack
    #yard1 = yarding.Yard(name='serf', yid=1)
    stack1 = stacking.StackUxd()

    stack0.addRemoteYard(stack1.yard)
    stack1.addRemoteYard(stack0.yard)

    print "{0} yard name={1} ha={2}".format(stack0.name, stack0.yard.name, stack0.yard.ha)
    print "{0} yards=\n{1}".format(stack0.name, stack0.yards)
    print "{0} names=\n{1}".format(stack0.name, stack0.names)

    print "{0} yard name={1} ha={2}".format(stack1.name, stack1.yard.name, stack1.yard.ha)
    print "{0} yards=\n{1}".format(stack1.name, stack1.yards)
    print "{0} names=\n{1}".format(stack1.name, stack1.names)

    print "\n********* UXD Message lord to serf serf to lord **********"
    msg = odict(what="This is a message to the serf. Get to Work", extra="Fix the fence.")
    stack0.transmit(msg=msg)

    msg = odict(what="This is a message to the lord. Let me be", extra="Go away.")
    stack1.transmit(msg=msg)

    timer = Timer(duration=0.5)
    timer.restart()
    while not timer.expired:
        stack0.serviceAll()
        stack1.serviceAll()


    print "{0} Received Messages".format(stack0.name)
    for msg in stack0.rxMsgs:
        print msg
    print

    print "{0} Received Messages".format(stack1.name)
    for msg in stack1.rxMsgs:
        print msg
    print

    print "\n********* Multiple Messages Both Ways **********"

    stack1.transmit(odict(house="Mama mia1", queue="fix me"), None)
    stack1.transmit(odict(house="Mama mia2", queue="help me"), None)
    stack1.transmit(odict(house="Mama mia3", queue="stop me"), None)
    stack1.transmit(odict(house="Mama mia4", queue="run me"), None)

    stack0.transmit(odict(house="Papa pia1", queue="fix me"), None)
    stack0.transmit(odict(house="Papa pia2", queue="help me"), None)
    stack0.transmit(odict(house="Papa pia3", queue="stop me"), None)
    stack0.transmit(odict(house="Papa pia4", queue="run me"), None)

    #big packets
    stuff = []
    for i in range(300):
        stuff.append(str(i).rjust(4, " "))
    stuff = "".join(stuff)

    stack1.transmit(odict(house="Mama mia1", queue="big stuff", stuff=stuff), None)
    stack0.transmit(odict(house="Papa pia4", queue="gig stuff", stuff=stuff), None)

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

    src = ('minion', 'serf', None)
    dst = ('master', None, None)
    route = odict(src=src, dst=dst)
    msg = odict(route=route, stuff="Hey buddy what is up?")
    stack0.transmit(msg)

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

    estate = 'minion1'
    #lord stack yard0
    stack0 = stacking.StackUxd(name='lord', lanename='cherry')

    #serf stack yard1
    stack1 = stacking.StackUxd(name='serf', lanename='cherry')

    print "Yid", yarding.Yard.Yid

    print "\n********* Attempt Auto Accept ************"
    #stack0.addRemoteYard(stack1.yard)
    yard = yarding.Yard( name=stack0.yard.name, prefix='cherry')
    stack1.addRemoteYard(yard)

    print "{0} yard name={1} ha={2}".format(stack0.name, stack0.yard.name, stack0.yard.ha)
    print "{0} yards=\n{1}".format(stack0.name, stack0.yards)
    print "{0} names=\n{1}".format(stack0.name, stack0.names)

    print "{0} yard name={1} ha={2}".format(stack1.name, stack1.yard.name, stack1.yard.ha)
    print "{0} yards=\n{1}".format(stack1.name, stack1.yards)
    print "{0} names=\n{1}".format(stack1.name, stack1.names)

    print "\n********* UXD Message serf to lord **********"
    src = (estate, stack1.yard.name, None)
    dst = (estate, stack0.yard.name, None)
    route = odict(src=src, dst=dst)
    msg = odict(route=route, stuff="Serf to my lord. Feed me!")
    stack1.transmit(msg=msg)

    timer = Timer(duration=0.5)
    timer.restart()
    while not timer.expired:
        stack0.serviceAll()
        stack1.serviceAll()


    print "{0} Received Messages".format(stack0.name)
    for msg in stack0.rxMsgs:
        print msg
    print

    print "{0} Received Messages".format(stack1.name)
    for msg in stack1.rxMsgs:
        print msg
    print

    print "\n********* UXD Message lord to serf **********"
    src = (estate, stack0.yard.name, None)
    dst = (estate, stack1.yard.name, None)
    route = odict(src=src, dst=dst)
    msg = odict(route=route, stuff="Lord to serf. Feed yourself!")
    stack0.transmit(msg=msg)


    timer = Timer(duration=0.5)
    timer.restart()
    while not timer.expired:
        stack0.serviceAll()
        stack1.serviceAll()

    print "{0} Received Messages".format(stack0.name)
    for msg in stack0.rxMsgs:
        print msg
    print

    print "{0} Received Messages".format(stack1.name)
    for msg in stack1.rxMsgs:
        print msg
    print

    print "{0} yard name={1} ha={2}".format(stack0.name, stack0.yard.name, stack0.yard.ha)
    print "{0} yards=\n{1}".format(stack0.name, stack0.yards)
    print "{0} names=\n{1}".format(stack0.name, stack0.names)

    print "{0} yard name={1} ha={2}".format(stack1.name, stack1.yard.name, stack1.yard.ha)
    print "{0} yards=\n{1}".format(stack1.name, stack1.yards)
    print "{0} names=\n{1}".format(stack1.name, stack1.names)



if __name__ == "__main__":
    testStackUxd(raeting.packKinds.json)
    testStackUxd(raeting.packKinds.pack)
