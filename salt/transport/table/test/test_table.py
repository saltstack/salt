# -*- coding: utf-8 -*-
'''
Tests to try out table. Potentially ephemeral

'''

# Import Salt Libs
from salt.transport import table


def test_table():
    bob_pub = table.Public()
    print bob_pub.backend
    print bob_pub.sec_backend
    print bob_pub.keydata
    print bob_pub.public
    print bob_pub.secret


if __name__ == "__main__":
    test_table()
