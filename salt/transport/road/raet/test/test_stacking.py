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
    stack1 = stacking.Stack(device=device)

    #minon stack
    device = stacking.LocalDevice(   did=0,
                                     ha=("", raeting.RAET_TEST_PORT),
                                     signkey=minionSignKeyHex,
                                     prikey=masterPriKeyHex,)
    stack2 = stacking.Stack(device=device)

    master = stacking.RemoteDevice(did=0, ha=('127.0.0.1', raeting.RAET_PORT))
    stack2.addRemoteDevice(master)
    # minion doesn't yet know master did

    data = odict(hk=1, bk=1)
    joiner = stacking.Joiner(stack=stack2, sid=0, txData=data)
    joiner.join()

    stack2.serviceUdp()
    stack1.serviceUdp()

    packet = stack1.processRxUdp()
    if packet:
        print packet.data
        print packet.body.data
    else:
        print "Join Packet dropped"
        return

    if packet.data['pk'] == raeting.packetKinds.join and packet.data['si'] == 0:

        data = odict(hk=1, bk=1)
        acceptor = stacking.Acceptor(stack=stack1, sid=0, txData=data)
        acceptor.pend(data=packet.data, body=packet.body.data)

        stack1.devices[acceptor.rdid].accepted = True
        acceptor.accept()

    stack1.serviceUdp()
    stack2.serviceUdp()

    while True:
        packet = stack2.processRxUdp()
        if not packet:
            break

        print packet.data
        print packet.body.data

        if packet.data['pk'] == raeting.packetKinds.accept and packet.data['si'] == 0:
            joiner.accept(packet.data, packet.body.data)

            print stack2.device.did
            print stack2.devices

        if packet.data['pk'] == raeting.packetKinds.acceptAck and packet.data['si'] == 0:
            joiner.pend(packet.data)


if __name__ == "__main__":
    test()
