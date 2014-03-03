# -*- coding: utf-8 -*-
'''
Tests to try out packeting. Potentially ephemeral

'''
# pylint: skip-file
# pylint: disable=C0103
import os

from ioflo.base.odicting import odict

from salt.transport.road.raet import (raeting, nacling, estating, keeping)


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
    estate = estating.LocalEstate(eid=1,
                                  sigkey=masterSignKeyHex,
                                  prikey=masterPriKeyHex)

    remote0 = estating.RemoteEstate(eid=2,
                                    ha=('127.0.0.1', 7532),
                                    verkey=minionVerKeyHex,
                                    pubkey=minionPubKeyHex,)

    remote1 = estating.RemoteEstate(eid=3,
                                    ha=('127.0.0.1', 7533),
                                    verkey=minionVerKeyHex,
                                    pubkey=minionPubKeyHex,)

    pond = keeping.RoadKeep(dirpath=os.getcwd())
    safe = keeping.SafeKeep(dirpath=os.getcwd())

    pond.dumpLocalEstate(estate)
    pond.dumpRemoteEstate(remote0)
    pond.dumpRemoteEstate(remote1)

    safe.dumpLocalEstate(estate)
    safe.dumpRemoteEstate(remote0)
    safe.dumpRemoteEstate(remote1)

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
