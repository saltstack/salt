# -*- coding: utf-8 -*-
'''
Tests to try out table. Potentially ephemeral

'''


import json
from salt.transport import table


def test_table():

    bob_pub = table.Public()
    print json.dumps(bob_pub.keydata, indent=2)

    #print bob_pub.backend
    #print bob_pub.sec_backend
    #print bob_pub.public
    #print bob_pub.secret

    signed = bob_pub.sign("What have we here.")
    print type(signed)
    print len(signed.message)
    print len(signed.signature)
    print type(signed.signature)
    print signed.message
    print signed.signature
    print signed

    signature = bob_pub.signature("What have we here.")
    print signature
    print signature == signed.signature


if __name__ == "__main__":
    test_table()
