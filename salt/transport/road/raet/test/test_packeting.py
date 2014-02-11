# -*- coding: utf-8 -*-
'''
Tests to try out packeting. Potentially ephemeral

'''

from salt.transport.road.raet import packeting
from ioflo.base.odicting import odict


def test():
    data = odict(hk=1, bk=1, bf=1, cf=1)
    body = odict(msg='Hello Raet World', extra='what is this')
    packet1 = packeting.Packet(data=data, body=body)
    print packet1.body.data
    print packet1.pack()

    packet2 = packeting.Packet()
    packet2.parse(packet1.packed)
    print packet2.body.data

    packet3 = packeting.Packet(raw=packet1.packed)
    print packet3.body.data

    packet1.parse(packet1.packed)
    print packet1.body.data
    print packet1.pack()


if __name__ == "__main__":
    test()
