# -*- coding: utf-8 -*-
'''
Tests to try out packeting. Potentially ephemeral

'''


from ioflo.base.odicting import odict

from salt.transport.road.raet import (raeting, nacling, packeting,
                                     devicing, transacting, stacking)



def test():
    data = odict(hk=1, bk=raeting.bodyKinds.json)
    body = odict(msg='Hello Raet World', extra='what is this')
    packet1 = packeting.TxPacket(embody=body, data=data, )
    print packet1.body.data
    packet1.pack()
    print packet1.packed

    stuff = []
    for i in range(300):
        stuff.append(str(i).rjust(4, " "))

    stuff = "".join(stuff)

    data.update(bk=raeting.bodyKinds.raw)
    packet1 = packeting.TxPacket(embody=stuff, data=data, )
    packet1.pack()
    print packet1.packed

    rejoin = []
    if packet1.segmented:
        for index, segment in  packet1.segments.items():
            print index, segment.packed
            rejoin.append(segment.body.packed)

    rejoin = "".join(rejoin)
    print stuff == rejoin


    signer = nacling.Signer()
    masterSignKeyHex = signer.keyhex
    privateer = nacling.Privateer()
    masterPriKeyHex = privateer.keyhex

    #master stack
    device = devicing.LocalDevice(   did=1,
                                     signkey=masterSignKeyHex,
                                     prikey=masterPriKeyHex,)
    stack0 = stacking.StackUdp(device=device)

    data.update(fk=raeting.footKinds.nacl)
    packet1 = packeting.TxPacket(stack=stack0, embody=stuff, data=data, )
    packet1.pack()
    print packet1.packed

    rejoin = []
    if packet1.segmented:
        for index, segment in  packet1.segments.items():
            print index, segment.packed
            rejoin.append(segment.body.packed)

    rejoin = "".join(rejoin)
    print stuff == rejoin

    segmentage = None
    if packet1.segmented:
        for segment in packet1.segments.values():
            if segment.segmentive:
                if not segmentage:
                    segmentage = packeting.RxPacket(stack=segment.stack,
                                                    data=segment.data)
                segmentage.parseSegment(segment)
            if segmentage.desegmentable():
                segmentage.desegmentize()
                break

    if segmentage:
        print segmentage.body.packed
        print segmentage.body.data


    #minion stack
    signer = nacling.Signer()
    minionSignKeyHex = signer.keyhex
    privateer = nacling.Privateer()
    minionPriKeyHex = privateer.keyhex

    #minion stack
    device = devicing.LocalDevice(   did=0,
                                     ha=("", raeting.RAET_TEST_PORT),
                                     signkey=minionSignKeyHex,
                                     prikey=minionPriKeyHex,)
    stack1 = stacking.StackUdp(device=device)

    # exchange keys



if __name__ == "__main__":
    test()
