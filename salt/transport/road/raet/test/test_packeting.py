# -*- coding: utf-8 -*-
'''
Tests to try out packeting. Potentially ephemeral

'''
# pylint: skip-file
# pylint: disable=C0103

from ioflo.base.odicting import odict

from salt.transport.road.raet import (raeting, nacling, packeting,
                                      devicing, transacting, stacking)


def test():
    '''
    Test packeting.
    '''
    data = odict(hk=1, bk=raeting.bodyKinds.json)
    body = odict(msg='Hello Raet World', extra='what is this')
    packet0 = packeting.TxPacket(embody=body, data=data, )
    print packet0.body.data
    packet0.pack()
    print packet0.packed

    stuff = []
    for i in range(300):
        stuff.append(str(i).rjust(4, " "))

    stuff = "".join(stuff)

    data.update(bk=raeting.bodyKinds.raw)
    packet0 = packeting.TxPacket(embody=stuff, data=data, )
    packet0.pack()
    print packet0.packed

    rejoin = []
    if packet0.segmented:
        for index, segment in  packet0.segments.items():
            print index, segment.packed
            rejoin.append(segment.body.packed)

    rejoin = "".join(rejoin)
    print stuff == rejoin

    signer = nacling.Signer()
    masterSignKeyHex = signer.keyhex
    masterVerKeyHex = signer.verhex
    privateer = nacling.Privateer()
    masterPriKeyHex = privateer.keyhex
    masterPubKeyHex = privateer.pubhex

    signer = nacling.Signer()
    minionSignKeyHex = signer.keyhex
    minionVerKeyHex = signer.verhex
    privateer = nacling.Privateer()
    minionPriKeyHex = privateer.keyhex
    minionPubKeyHex = privateer.pubhex

    #master stack
    device = devicing.LocalDevice(did=1,
                                  signkey=masterSignKeyHex,
                                  prikey=masterPriKeyHex)
    stack0 = stacking.StackUdp(device=device)

    remote1 = devicing.RemoteDevice(  did=2,
                                     verkey=minionVerKeyHex,
                                     pubkey=minionPubKeyHex,)
    stack0.addRemoteDevice(remote1)

    #minion stack
    device = devicing.LocalDevice(   did=2,
                                     ha=("", raeting.RAET_TEST_PORT),
                                     signkey=minionSignKeyHex,
                                     prikey=minionPriKeyHex,)
    stack1 = stacking.StackUdp(device=device)

    remote0 = devicing.RemoteDevice(  did=1,
                                     ha=('127.0.0.1', raeting.RAET_PORT),
                                     verkey=masterVerKeyHex,
                                     pubkey=masterPubKeyHex,)
    stack1.addRemoteDevice(remote0)

    remote0.publee = nacling.Publican(key=remote1.privee.pubhex)
    remote1.publee = nacling.Publican(key=remote0.privee.pubhex)

    data.update(sd=1, dd=2, bk=raeting.bodyKinds.raw, fk=raeting.footKinds.nacl)
    packet0 = packeting.TxPacket(stack=stack0, embody=stuff, data=data, )
    packet0.pack()
    print packet0.packed

    rejoin = []
    if packet0.segmented:
        for index, segment in  packet0.segments.items():
            print index, segment.packed
            rejoin.append(segment.coat.packed)

    rejoin = "".join(rejoin)
    print stuff == rejoin

    segmentage = None
    if packet0.segmented:
        for segment in packet0.segments.values():
            packet = packeting.RxPacket(stack=stack1, packed=segment.packed)
            packet.parseOuter()
            if packet.segmentive:
                if not segmentage:
                    segmentage = packeting.RxPacket(stack=packet.stack,
                                                    data=packet.data)
                segmentage.parseSegment(packet)
            if segmentage.desegmentable():
                segmentage.desegmentize()
                break
    if segmentage:
        if not stack1.parseInner(segmentage):
            print "*******BAD SEGMENTAGE********"
            return
        print segmentage.body.packed
        print segmentage.body.data
        print segmentage.body.packed == packet0.body.packed

    body = odict(stuff=stuff)
    print body
    data.update(sd=1, dd=2, bk=raeting.bodyKinds.json, fk=raeting.footKinds.nacl)
    packet0 = packeting.TxPacket(stack=stack0, embody=body, data=data, )
    packet0.pack()
    print packet0.packed

    segmentage = None
    if packet0.segmented:
        for segment in packet0.segments.values():
            packet = packeting.RxPacket(stack=stack1, packed=segment.packed)
            packet.parseOuter()
            if packet.segmentive:
                if not segmentage:
                    segmentage = packeting.RxPacket(stack=packet.stack,
                                                    data=packet.data)
                segmentage.parseSegment(packet)
            if segmentage.desegmentable():
                segmentage.desegmentize()
                break
    if segmentage:
        if not stack1.parseInner(segmentage):
            print "*******BAD SEGMENTAGE********"
            return
        print segmentage.body.packed
        print segmentage.body.data
        print segmentage.body.packed == packet0.body.packed

    body = odict(stuff=stuff)
    print body
    data.update(sd=1, dd=2,
                bk=raeting.bodyKinds.json,
                ck=raeting.coatKinds.nacl,
                fk=raeting.footKinds.nacl)
    packet0 = packeting.TxPacket(stack=stack0, embody=body, data=data, )
    packet0.pack()
    print "Body"
    print packet0.body.size,  packet0.body.packed
    print "Coat"
    print packet0.coat.size,  packet0.coat.packed
    print "Head"
    print packet0.head.size,  packet0.head.packed
    print "Foot"
    print packet0.foot.size,  packet0.foot.packed
    print "Packet"
    print packet0.size, packet0.packed

    segmentage = None
    if packet0.segmented:
        for segment in packet0.segments.values():
            packet = packeting.RxPacket(stack=stack1, packed=segment.packed)
            packet.parseOuter()
            if packet.segmentive:
                if not segmentage:
                    segmentage = packeting.RxPacket(stack=packet.stack,
                                                    data=packet.data)
                segmentage.parseSegment(packet)
            if segmentage.desegmentable():
                segmentage.desegmentize()
                break
    if segmentage:
        if not stack1.parseInner(segmentage):
            print "*******BAD SEGMENTAGE********"
        print segmentage.body.packed
        print segmentage.body.data
        print segmentage.body.packed == packet0.body.packed

if __name__ == "__main__":
    test()
