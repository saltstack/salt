# -*- coding: utf-8 -*-
'''
Tests to try out packeting. Potentially ephemeral

'''
# pylint: skip-file
# pylint: disable=C0103

from ioflo.base.odicting import odict

from salt.transport.road.raet import (raeting, nacling, devicing, keeping)


def test():
    '''
    Test keeping.
    '''

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
                                  sigkey=masterSignKeyHex,
                                  prikey=masterPriKeyHex)

    remote1 = devicing.RemoteDevice(  did=2,
                                     verkey=minionVerKeyHex,
                                     pubkey=minionPubKeyHex,)

    remote0 = devicing.RemoteDevice(  did=1,
                                     ha=('127.0.0.1', raeting.RAET_PORT),
                                     verkey=masterVerKeyHex,
                                     pubkey=masterPubKeyHex,)


if __name__ == "__main__":
    test()
