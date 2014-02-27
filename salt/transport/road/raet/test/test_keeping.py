# -*- coding: utf-8 -*-
'''
Tests to try out packeting. Potentially ephemeral

'''
# pylint: skip-file
# pylint: disable=C0103
import os

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

    remote0 = devicing.RemoteDevice(did=2,
                                    ha=('127.0.0.1', 7532),
                                    verkey=minionVerKeyHex,
                                    pubkey=minionPubKeyHex,)

    remote1 = devicing.RemoteDevice(did=3,
                                    ha=('127.0.0.1', 7533),
                                    verkey=minionVerKeyHex,
                                    pubkey=minionPubKeyHex,)

    pond = keeping.RoadKeep(dirpath=os.getcwd())
    safe = keeping.SafeKeep(dirpath=os.getcwd())

    pond.dumpLocalDevice(device)
    pond.dumpRemoteDevice(remote0)
    pond.dumpRemoteDevice(remote1)

    safe.dumpLocalDevice(device)
    safe.dumpRemoteDevice(remote0)
    safe.dumpRemoteDevice(remote1)

    data = pond.loadLocalData()
    print data

    data = pond.loadAllRemoteData()
    print data

    data = safe.loadLocalData()
    print data

    data = safe.loadAllRemoteData()
    print data




if __name__ == "__main__":
    test()
