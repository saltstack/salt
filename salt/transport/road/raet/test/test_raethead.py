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


def test( hk = raeting.headKinds.raet):
    '''
    Test packeting.
    '''
    data = odict(hk=hk, bk=raeting.bodyKinds.json)
    body = odict(msg='Hello Raet World', extra='what is this')
    packet0 = packeting.TxPacket(embody=body, data=data, )
    print packet0.body.data
    packet0.pack()
    print packet0.packed
    packet1 = packeting.RxPacket(packed=packet0.packed)
    packet1.parse()
    print packet1.data
    print packet1.body.data




if __name__ == "__main__":
    test()
