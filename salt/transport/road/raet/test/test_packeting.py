# -*- coding: utf-8 -*-
'''
Tests to try out packeting. Potentially ephemeral

'''


from ioflo.base.odicting import odict

from salt.transport.road.raet import raeting
from salt.transport.road.raet import packeting



def test():
    data = odict(hk=1, bk=raeting.bodyKinds.json)
    body = odict(msg='Hello Raet World', extra='what is this')
    packet1 = packeting.TxPacket(embody=body, data=data, )
    print packet1.body.data
    packet1.pack()
    print packet1.packed

    stuff =  "".rjust(1200, '\x00')
    data.update(bk=raeting.bodyKinds.raw)
    packet1 = packeting.TxPacket(embody=stuff, data=data, )
    #print packet1.body.data
    packet1.pack()
    print packet1.packed

    if packet1.segments:
        for index, segment in  packet1.segments.items():
            print index, segment.packed


if __name__ == "__main__":
    test()
