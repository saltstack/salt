
# -*- coding: utf-8 -*-
'''
Use pycrypto to generate random passwords on the fly.
'''

# Import python libraries
import Crypto.Random
import crypt
import re


def secure_password(length=20):
    '''
    Generate a secure password.
    '''
    pw = ''
    while len(pw) < length:
        pw += re.sub(r'\W', '', Crypto.Random.get_random_bytes(1))
    return pw


def gen_hash(salt=None, password=None):
    '''
    Generate /etc/shadow hash
    '''

    if password is None:
        password = secure_password()

    if salt is None:
        salt = '$6' + secure_password(8)

    return crypt.crypt(password, salt)
