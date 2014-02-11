# -*- coding: utf-8 -*-
'''
Tests to try out stacking. Potentially ephemeral

'''
from ioflo.base.odicting import odict
from salt.transport.road.raet import raeting,  packeting, stacking


def test():

    # master did of 1 on 7530
    # minion did of 2 on 7531

    stack1 = stacking.Stack() #default did of 1
    minion = stacking.Device(did=2, ha=('127.0.0.1', raeting.RAET_TEST_PORT))
    stack1.addRemoteDevice(minion)

    stack2 = stacking.Stack(did=2, ha=("", raeting.RAET_TEST_PORT))
    master = stacking.Device(did=1, ha=('127.0.0.1', raeting.RAET_PORT))
    stack2.addRemoteDevice(master)

    body=odict(msg='Hello Raet World', extra='what is this')
    data = odict(hk=1, bk=1)


    joiner = stacking.Joiner(stack=stack2, rdid=master.did, sid=0, txData=data)
    joiner.start()

    #packet = packeting.RxPacket(packed=joiner.txPacket.packed)
    #packet.parseFore()
    #print packet.data
    #packet.parseBack()
    #print packet.body.data


    stack2.serviceUdp()
    stack1.serviceUdp()

    print stack1.rxdsUdp
    packet = stack1.processRxUdp()

    if packet:
        print packet.data
        print packet.body.data

    else:
        print "Packet dropped"



if __name__ == "__main__":
    test()
