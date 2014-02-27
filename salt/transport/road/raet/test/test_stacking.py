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
                                     devicing, transacting, stacking)


def test():
    '''
    initially
    master on port 7530 with did of 1
    minion on port 7531 with did of 0
    eventually
    master did of 1
    minion did of 2
    '''
    console.reinit(verbosity=console.Wordage.concise)

    signer = nacling.Signer()
    masterSignKeyHex = signer.keyhex
    privateer = nacling.Privateer()
    masterPriKeyHex = privateer.keyhex

    signer = nacling.Signer()
    minionSignKeyHex = signer.keyhex
    privateer = nacling.Privateer()
    minionPriKeyHex = privateer.keyhex

    #master stack
    device = devicing.LocalDevice(   did=1,
                                     name='master',
                                     sigkey=masterSignKeyHex,
                                     prikey=masterPriKeyHex,)
    stack0 = stacking.StackUdp(device=device)

    #minion stack
    device = devicing.LocalDevice(   did=0,
                                     name='minion1',
                                     ha=("", raeting.RAET_TEST_PORT),
                                     sigkey=minionSignKeyHex,
                                     prikey=minionPriKeyHex,)
    stack1 = stacking.StackUdp(device=device)


    print "\n********* Join Transaction **********"
    stack1.join()

    timer = Timer(duration=0.5)
    while not timer.expired:
        stack1.serviceUdp()
        stack0.serviceUdp()

    stack0.serviceUdpRx()
    stack0.process()

    timer.restart()
    while not timer.expired:
        stack0.serviceUdp()
        stack1.serviceUdp()

    stack1.serviceUdpRx()


    print "{0} did={1}".format(stack0.name, stack0.device.did)
    print "{0} devices=\n{1}".format(stack0.name, stack0.devices)
    print "{0} dids=\n{1}".format(stack0.name, stack0.dids)
    print "{0} transactions=\n{1}".format(stack0.name, stack0.transactions)
    for device in stack0.devices.values():
        print "Remote Device {0} joined= {1}".format(device.did, device.joined)

    print "{0} did={1}".format(stack1.name, stack1.device.did)
    print "{0} devices=\n{1}".format(stack1.name, stack1.devices)
    print "{0} dids=\n{1}".format(stack1.name, stack1.dids)
    print "{0} transactions=\n{1}".format(stack1.name, stack1.transactions)
    for device in stack1.devices.values():
            print "Remote Device {0} joined= {1}".format(device.did, device.joined)


    print "\n********* Allow Transaction **********"

    stack1.allow()
    timer.restart()
    while not timer.expired:
        stack1.serviceUdp()
        stack0.serviceUdp()

    stack0.serviceUdpRx()

    timer.restart()
    while not timer.expired:
        stack0.serviceUdp()
        stack1.serviceUdp()

    stack1.serviceUdpRx()

    timer.restart()
    while not timer.expired:
        stack0.serviceUdp()
        stack1.serviceUdp()

    stack0.serviceUdpRx()

    timer.restart()
    while not timer.expired:
        stack0.serviceUdp()
        stack1.serviceUdp()

    stack1.serviceUdpRx()

    print "{0} did={1}".format(stack0.name, stack0.device.did)
    print "{0} devices=\n{1}".format(stack0.name, stack0.devices)
    print "{0} dids=\n{1}".format(stack0.name, stack0.dids)
    print "{0} transactions=\n{1}".format(stack0.name, stack0.transactions)
    for device in stack0.devices.values():
        print "Remote Device {0} allowed= {1}".format(device.did, device.allowed)

    print "{0} did={1}".format(stack1.name, stack1.device.did)
    print "{0} devices=\n{1}".format(stack1.name, stack1.devices)
    print "{0} dids=\n{1}".format(stack1.name, stack1.dids)
    print "{0} transactions=\n{1}".format(stack1.name, stack1.transactions)
    for device in stack1.devices.values():
            print "Remote Device {0} allowed= {1}".format(device.did, device.allowed)


    print "\n********* Message Transaction Minion to Master **********"
    body = odict(what="This is a message to the master. How are you", extra="And some more.")
    stack1.message(body=body, ddid=1)

    timer.restart()
    while not timer.expired:
        stack1.serviceUdp()
        stack0.serviceUdp()

    stack0.serviceUdpRx()

    timer.restart()
    while not timer.expired:
        stack0.serviceUdp()
        stack1.serviceUdp()

    stack1.serviceUdpRx()

    print "{0} did={1}".format(stack0.name, stack0.device.did)
    print "{0} devices=\n{1}".format(stack0.name, stack0.devices)
    print "{0} dids=\n{1}".format(stack0.name, stack0.dids)
    print "{0} transactions=\n{1}".format(stack0.name, stack0.transactions)
    print "{0} Received Messages =\n{1}".format(stack0.name, stack0.rxMsgs)

    print "{0} did={1}".format(stack1.name, stack1.device.did)
    print "{0} devices=\n{1}".format(stack1.name, stack1.devices)
    print "{0} dids=\n{1}".format(stack1.name, stack1.dids)
    print "{0} transactions=\n{1}".format(stack1.name, stack1.transactions)
    print "{0} Received Messages =\n{1}".format(stack1.name, stack1.rxMsgs)

    print "\n********* Message Transaction Master to Minion **********"
    body = odict(what="This is a message to the minion. Get to Work", extra="Fix the fence.")
    stack0.message(body=body, ddid=2)

    timer.restart()
    while not timer.expired:
        stack0.serviceUdp()
        stack1.serviceUdp()

    stack1.serviceUdpRx()

    timer.restart()
    while not timer.expired:
        stack1.serviceUdp()
        stack0.serviceUdp()

    stack0.serviceUdpRx()

    print "{0} did={1}".format(stack0.name, stack0.device.did)
    print "{0} devices=\n{1}".format(stack0.name, stack0.devices)
    print "{0} dids=\n{1}".format(stack0.name, stack0.dids)
    print "{0} transactions=\n{1}".format(stack0.name, stack0.transactions)
    print "{0} Received Messages =\n{1}".format(stack0.name, stack0.rxMsgs)

    print "{0} did={1}".format(stack1.name, stack1.device.did)
    print "{0} devices=\n{1}".format(stack1.name, stack1.devices)
    print "{0} dids=\n{1}".format(stack1.name, stack1.dids)
    print "{0} transactions=\n{1}".format(stack1.name, stack1.transactions)
    print "{0} Received Messages =\n{1}".format(stack1.name, stack1.rxMsgs)

    print "\n********* Message Transactions Both Ways **********"

    stack1.txMsgs.append((odict(house="Mama mia1", queue="fix me"), None))
    stack1.txMsgs.append((odict(house="Mama mia2", queue="help me"), None))
    stack1.txMsgs.append((odict(house="Mama mia3", queue="stop me"), None))
    stack1.txMsgs.append((odict(house="Mama mia4", queue="run me"), None))

    stack0.txMsgs.append((odict(house="Papa pia1", queue="fix me"), None))
    stack0.txMsgs.append((odict(house="Papa pia2", queue="help me"), None))
    stack0.txMsgs.append((odict(house="Papa pia3", queue="stop me"), None))
    stack0.txMsgs.append((odict(house="Papa pia4", queue="run me"), None))

    #segmented packets
    stuff = []
    for i in range(300):
        stuff.append(str(i).rjust(4, " "))
    stuff = "".join(stuff)

    stack1.txMsgs.append((odict(house="Mama mia1", queue="big stuff", stuff=stuff), None))
    stack0.txMsgs.append((odict(house="Papa pia4", queue="gig stuff", stuff=stuff), None))

    stack1.serviceTxMsg()
    stack0.serviceTxMsg()

    timer.restart()
    while not timer.expired:
        stack1.serviceUdp()
        stack0.serviceUdp()

    stack0.serviceUdpRx()
    stack1.serviceUdpRx()

    timer.restart()
    while not timer.expired:
        stack0.serviceUdp()
        stack1.serviceUdp()

    stack1.serviceUdpRx()
    stack0.serviceUdpRx()


    print "{0} did={1}".format(stack0.name, stack0.device.did)
    print "{0} devices=\n{1}".format(stack0.name, stack0.devices)
    print "{0} transactions=\n{1}".format(stack0.name, stack0.transactions)
    print "{0} Received Messages".format(stack0.name)
    for msg in stack0.rxMsgs:
        print msg
    print
    print "{0} did={1}".format(stack1.name, stack1.device.did)
    print "{0} devices=\n{1}".format(stack1.name, stack1.devices)
    print "{0} transactions=\n{1}".format(stack1.name, stack1.transactions)
    print "{0} Received Messages".format(stack1.name)
    for msg in stack1.rxMsgs:
            print msg


    print "\n********* Message Transactions Both Ways Again **********"

    stack1.txMsg(odict(house="Oh Boy1", queue="Nice"))
    stack1.txMsg(odict(house="Oh Boy2", queue="Mean"))
    stack1.txMsg(odict(house="Oh Boy3", queue="Ugly"))
    stack1.txMsg(odict(house="Oh Boy4", queue="Pretty"))

    stack0.txMsg(odict(house="Yeah Baby1", queue="Good"))
    stack0.txMsg(odict(house="Yeah Baby2", queue="Bad"))
    stack0.txMsg(odict(house="Yeah Baby3", queue="Fast"))
    stack0.txMsg(odict(house="Yeah Baby4", queue="Slow"))

    #segmented packets
    stuff = []
    for i in range(300):
        stuff.append(str(i).rjust(4, " "))
    stuff = "".join(stuff)

    stack1.txMsg(odict(house="Snake eyes", queue="near stuff", stuff=stuff))
    stack0.txMsg(odict(house="Craps", queue="far stuff", stuff=stuff))

    timer.restart(duration=2)
    while not timer.expired:
        stack1.serviceAll()
        stack0.serviceAll()


    print "{0} did={1}".format(stack0.name, stack0.device.did)
    print "{0} devices=\n{1}".format(stack0.name, stack0.devices)
    print "{0} transactions=\n{1}".format(stack0.name, stack0.transactions)
    print "{0} Received Messages".format(stack0.name)
    for msg in stack0.rxMsgs:
        print msg
    print
    print "{0} did={1}".format(stack1.name, stack1.device.did)
    print "{0} devices=\n{1}".format(stack1.name, stack1.devices)
    print "{0} transactions=\n{1}".format(stack1.name, stack1.transactions)
    print "{0} Received Messages".format(stack1.name)
    for msg in stack1.rxMsgs:
            print msg


if __name__ == "__main__":
    test()
