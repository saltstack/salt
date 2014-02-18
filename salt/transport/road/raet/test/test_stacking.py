# -*- coding: utf-8 -*-
'''
Tests to try out stacking. Potentially ephemeral

'''
# pylint: skip-file
from ioflo.base.odicting import odict
from ioflo.base.aiding import Timer

from salt.transport.road.raet import (raeting, nacling, packeting,
                                     devicing, transacting, stacking)


def test():

    signer = nacling.Signer()
    masterSignKeyHex = signer.keyhex
    privateer = nacling.Privateer()
    masterPriKeyHex = privateer.keyhex

    signer = nacling.Signer()
    minionSignKeyHex = signer.keyhex
    privateer = nacling.Privateer()
    masterPriKeyHex = privateer.keyhex

    # initially
    # master on port 7530 with did of 1
    # minion on port 7531 with did of 0
    # eventually
    # minion did of 2

    #master stack
    device = devicing.LocalDevice(   did=1,
                                     signkey=masterSignKeyHex,
                                     prikey=masterPriKeyHex,)
    stack0 = stacking.StackUdp(device=device)

    #minion stack
    device = devicing.LocalDevice(   did=0,
                                     ha=("", raeting.RAET_TEST_PORT),
                                     signkey=minionSignKeyHex,
                                     prikey=masterPriKeyHex,)
    stack1 = stacking.StackUdp(device=device)

    stack1.join()

    timer = Timer(duration=0.5)
    while not timer.expired:
        stack1.serviceUdp()
        stack0.serviceUdp()

    while stack0.udpRxes:
        stack0.processUdpRx()

    timer.restart()
    while not timer.expired:
        stack0.serviceUdp()
        stack1.serviceUdp()

    while stack1.udpRxes:
        stack1.processUdpRx()


    print "{0} did={1}".format(stack0.name, stack0.device.did)
    print "{0} devices=\n{1}".format(stack0.name, stack0.devices)
    print "{0} transactions=\n{1}".format(stack0.name, stack0.transactions)
    for device in stack0.devices.values():
        print "Remote Device {0} joined= {1}".format(device.did, device.joined)

    print "{0} did={1}".format(stack1.name, stack1.device.did)
    print "{0} devices=\n{1}".format(stack1.name, stack1.devices)
    print "{0} transactions=\n{1}".format(stack1.name, stack1.transactions)
    for device in stack1.devices.values():
            print "Remote Device {0} joined= {1}".format(device.did, device.joined)

    stack1.endow()
    timer.restart()
    while not timer.expired:
        stack1.serviceUdp()
        stack0.serviceUdp()

    while stack0.udpRxes:
        stack0.processUdpRx()

    timer.restart()
    while not timer.expired:
        stack0.serviceUdp()
        stack1.serviceUdp()

    while stack1.udpRxes:
        stack1.processUdpRx()

    timer.restart()
    while not timer.expired:
        stack0.serviceUdp()
        stack1.serviceUdp()

    while stack0.udpRxes:
        stack0.processUdpRx()

    timer.restart()
    while not timer.expired:
        stack0.serviceUdp()
        stack1.serviceUdp()

    while stack1.udpRxes:
        stack1.processUdpRx()

    print "{0} did={1}".format(stack0.name, stack0.device.did)
    print "{0} devices=\n{1}".format(stack0.name, stack0.devices)
    print "{0} transactions=\n{1}".format(stack0.name, stack0.transactions)
    for device in stack0.devices.values():
        print "Remote Device {0} allowed= {1}".format(device.did, device.allowed)

    print "{0} did={1}".format(stack1.name, stack1.device.did)
    print "{0} devices=\n{1}".format(stack1.name, stack1.devices)
    print "{0} transactions=\n{1}".format(stack1.name, stack1.transactions)
    for device in stack1.devices.values():
            print "Remote Device {0} allowed= {1}".format(device.did, device.allowed)



if __name__ == "__main__":
    test()
