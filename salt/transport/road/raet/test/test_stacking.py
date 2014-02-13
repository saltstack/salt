# -*- coding: utf-8 -*-
'''
Tests to try out stacking. Potentially ephemeral

'''
from ioflo.base.odicting import odict
from salt.transport.road.raet import raeting, packeting, stacking, nacling


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
    device = stacking.LocalDevice(   did=1,
                                     signkey=masterSignKeyHex,
                                     prikey=masterPriKeyHex,)
    stack1 = stacking.StackUdp(device=device)

    #minon stack
    device = stacking.LocalDevice(   did=0,
                                     ha=("", raeting.RAET_TEST_PORT),
                                     signkey=minionSignKeyHex,
                                     prikey=masterPriKeyHex,)
    stack2 = stacking.StackUdp(device=device)

    stack2.join()

    stack2.serviceUdp()
    stack1.serviceUdp()

    while stack1.rxdsUdp:
        stack1.processRxUdp()

    stack1.serviceUdp()
    stack2.serviceUdp()

    while stack2.rxdsUdp:
        stack2.processRxUdp()


    print "{0} did={1}".format(stack1.name, stack1.device.did)
    print "{0} devices=\n{1}".format(stack1.name, stack1.devices)
    print "{0} transaction=\n{1}".format(stack1.name, stack1.transactions)

    print "{0} did={1}".format(stack2.name, stack2.device.did)
    print "{0} devices=\n{1}".format(stack2.name, stack2.devices)
    print "{0} transaction=\n{1}".format(stack2.name, stack2.transactions)



if __name__ == "__main__":
    test()
