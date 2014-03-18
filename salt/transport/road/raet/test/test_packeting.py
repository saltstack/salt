# -*- coding: utf-8 -*-
'''
Tests to try out packeting. Potentially ephemeral

'''
# pylint: skip-file
# pylint: disable=C0103

import os

from ioflo.base.odicting import odict

from salt.transport.road.raet import (raeting, nacling, packeting, keeping,
                                      estating, transacting, stacking)


def test( bk = raeting.bodyKinds.json):
    '''
    Test packeting.
    '''
    data = odict(hk=1, bk=bk)
    body = odict(msg='Hello Raet World', extra='what is this')
    packet0 = packeting.TxPacket(embody=body, data=data, )
    print packet0.body.data
    packet0.pack()
    print packet0.packed
    packet1 = packeting.RxPacket(packed=packet0.packed)
    packet1.parse()
    print packet1.data
    print packet1.body.data

    stuff = []
    for i in range(300):
        stuff.append(str(i).rjust(4, " "))
    stuff = "".join(stuff)
    data.update(bk=raeting.bodyKinds.raw)
    packet0 = packeting.TxPacket(embody=stuff, data=data, )
    try:
        packet0.pack()
    except raeting.PacketError as ex:
        print ex
        print "Need to use tray"

    tray0 = packeting.TxTray(data=data, body=stuff)
    tray0.pack()
    print tray0.packed
    print tray0.packets

    tray1 = packeting.RxTray()
    for packet in tray0.packets:
        tray1.parse(packet)

    print tray1.data
    print tray1.body

    print stuff == tray1.body

    #master stack
    masterName = "master"
    signer = nacling.Signer()
    masterSignKeyHex = signer.keyhex
    masterVerKeyHex = signer.verhex
    privateer = nacling.Privateer()
    masterPriKeyHex = privateer.keyhex
    masterPubKeyHex = privateer.pubhex
    dirpathMaster = os.path.join(os.getcwd(), 'keep', masterName)

    #minion stack
    minionName = "minion"
    signer = nacling.Signer()
    minionSignKeyHex = signer.keyhex
    minionVerKeyHex = signer.verhex
    privateer = nacling.Privateer()
    minionPriKeyHex = privateer.keyhex
    minionPubKeyHex = privateer.pubhex
    dirpathMinion = os.path.join(os.getcwd(), 'keep', minionName)

    keeping.clearAllRoadSafe(dirpathMaster)
    keeping.clearAllRoadSafe(dirpathMinion)

    estate = estating.LocalEstate(  eid=1,
                                    name=masterName,
                                    sigkey=masterSignKeyHex,
                                    prikey=masterPriKeyHex)
    stack0 = stacking.StackUdp(estate=estate,  main=True,  dirpath=dirpathMaster)

    remote1 = estating.RemoteEstate( eid=2,
                                     name=minionName,
                                     ha=("127.0.0.1", raeting.RAET_TEST_PORT),
                                     verkey=minionVerKeyHex,
                                     pubkey=minionPubKeyHex,)
    stack0.addRemote(remote1)


    estate = estating.LocalEstate(   eid=2,
                                     name=minionName,
                                     ha=("", raeting.RAET_TEST_PORT),
                                     sigkey=minionSignKeyHex,
                                     prikey=minionPriKeyHex,)
    stack1 = stacking.StackUdp(estate=estate)

    remote0 = estating.RemoteEstate(  eid=1,
                                      name=masterName,
                                     ha=('127.0.0.1', raeting.RAET_PORT),
                                     verkey=masterVerKeyHex,
                                     pubkey=masterPubKeyHex,)
    stack1.addRemote(remote0)

    remote0.publee = nacling.Publican(key=remote1.privee.pubhex)
    remote1.publee = nacling.Publican(key=remote0.privee.pubhex)

    print  "\n___________Raw Body Test"
    data.update(se=1, de=2, bk=raeting.bodyKinds.raw, fk=raeting.footKinds.nacl)
    tray0 = packeting.TxTray(stack=stack0, data=data, body=stuff)
    tray0.pack()
    print tray0.packed
    print tray0.packets

    tray1 = packeting.RxTray(stack=stack1)
    for packet in tray0.packets:
        tray1.parse(packet)

    print tray1.data
    print tray1.body

    print stuff == tray1.body

    print  "\n_____________    Packed Body Test"
    body = odict(stuff=stuff)
    print body
    data.update(se=1, de=2, bk=bk, fk=raeting.footKinds.nacl)
    tray0 = packeting.TxTray(stack=stack0, data=data, body=body)
    tray0.pack()
    print tray0.packed
    print tray0.packets

    tray1 = packeting.RxTray(stack=stack1)
    for packet in tray0.packets:
        tray1.parse(packet)

    print tray1.data
    print tray1.body

    print body == tray1.body


    print "\n___________    Encrypted Coat Test "
    body = odict(stuff=stuff)
    print body
    data.update(se=1, de=2,
                bk=raeting.bodyKinds.json,
                ck=raeting.coatKinds.nacl,
                fk=raeting.footKinds.nacl)
    tray0 = packeting.TxTray(stack=stack0, data=data, body=body)
    tray0.pack()
    print tray0.packed
    print tray0.packets

    tray1 = packeting.RxTray(stack=stack1)
    for packet in tray0.packets:
        tray1.parse(packet)

    print tray1.data
    print tray1.body

    print body == tray1.body


    stack0.server.close()
    stack1.server.close()


if __name__ == "__main__":
    test()
    test(bk=raeting.bodyKinds.msgpack)
